import hashlib
import hmac
import json
import os
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from catalog.models import Brand, Category, Product, ProductVariant
from customers.models import Customer, CustomerGroup
from inventory.models import InventoryBalance, Warehouse
from sales.models import SalesOrder
from sales.services import save_sales_order
from shipping.models import CourierProvider, Shipment
from storefront.checkout_services import checkout_success_url

from .delivery import DeliveryError, process_outbound
from .models import IntegrationSettings, Notification, NotificationRead, OutboundMessage
from .services import enqueue_integration_failure, enqueue_order_event, enqueue_shipping_event, get_integration_settings, mark_all_notifications_read, mark_notification_read, public_tracking_config, unread_notifications_for


class IntegrationBase(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(name="Integration Warehouse", code="INT-MAIN", is_default=True, is_active=True)
        category = Category.objects.create(name="Integration Phones", slug="integration-phones")
        brand = Brand.objects.create(name="Integration Brand", slug="integration-brand")
        product = Product.objects.create(public_id="integration-phone", name="Integration Phone", slug="integration-phone", category=category, brand=brand, regular_price=Decimal("100.00"), status=Product.Status.ACTIVE)
        self.variant = ProductVariant.objects.create(product=product, name="Black", sku="INT-PHONE-BLK", stock_quantity=10, is_default=True, is_active=True)
        balance, _ = InventoryBalance.objects.get_or_create(warehouse=self.warehouse, variant=self.variant, defaults={"on_hand": 10, "reserved_quantity": 0, "low_stock_threshold": 5})
        balance.on_hand, balance.reserved_quantity, balance.low_stock_threshold = 10, 0, 5
        balance.save(update_fields=["on_hand", "reserved_quantity", "low_stock_threshold", "updated_at"])
        group = CustomerGroup.objects.get(code="RETAIL")
        self.customer = Customer.objects.create(name="Integration Customer", phone="01711111111", email="buyer@example.com", group=group, address="Road 1", city="Dhaka", district="Dhaka")
        self.order = save_sales_order(
            header_data={"customer": self.customer, "warehouse": self.warehouse, "channel": SalesOrder.Channel.ONLINE, "status": SalesOrder.Status.PENDING, "order_date": date(2026, 9, 8), "shipping_name": self.customer.name, "shipping_phone": self.customer.phone, "shipping_email": self.customer.email, "shipping_address": self.customer.address, "shipping_city": self.customer.city, "shipping_district": self.customer.district, "shipping_postal_code": "1200", "discount_amount": Decimal("0.00"), "shipping_charge": Decimal("60.00"), "amount_paid": Decimal("0.00"), "notes": "Integration test"},
            item_rows=[{"variant": self.variant, "quantity": 1, "unit_price": Decimal("100.00"), "discount_amount": Decimal("0.00")}],
            actor="Integration Test",
        )
        Notification.objects.all().delete()
        OutboundMessage.objects.all().delete()


class IntegrationServiceTests(IntegrationBase):
    def test_singleton_and_public_tracking_config_never_expose_secrets(self):
        config = get_integration_settings()
        config.meta_pixel_enabled, config.meta_pixel_id = True, "123456"
        config.ga4_enabled, config.ga4_measurement_id = True, "G-TEST123"
        config.save()
        public = public_tracking_config()
        self.assertEqual(public["meta_pixel_id"], "123456")
        self.assertEqual(public["ga4_measurement_id"], "G-TEST123")
        self.assertNotIn("secret", " ".join(public.keys()).lower())
        self.assertEqual(IntegrationSettings.objects.count(), 1)

    def test_notification_read_is_per_user(self):
        users = get_user_model()
        first = users.objects.create_user(username="first", password="Testpass123!")
        second = users.objects.create_user(username="second", password="Testpass123!")
        notification = Notification.objects.create(kind=Notification.Kind.ORDER, title="Order", message="Created")
        mark_notification_read(notification, first)
        self.assertEqual(unread_notifications_for(first).count(), 0)
        self.assertEqual(unread_notifications_for(second).count(), 1)
        self.assertTrue(NotificationRead.objects.filter(notification=notification, user=first).exists())

    def test_mark_all_read_is_idempotent(self):
        user = get_user_model().objects.create_user(username="reader", password="Testpass123!")
        for index in range(3):
            Notification.objects.create(kind=Notification.Kind.ORDER, title=f"N{index}", message="x")
        self.assertEqual(mark_all_notifications_read(user), 3)
        self.assertEqual(mark_all_notifications_read(user), 0)

    def test_order_created_enqueues_meta_and_ga_purchase_with_stable_identity(self):
        config = get_integration_settings()
        config.email_enabled = False
        config.meta_pixel_enabled, config.meta_pixel_id, config.meta_capi_enabled = True, "999", True
        config.ga4_enabled, config.ga4_measurement_id, config.ga4_server_enabled = True, "G-TEST", True
        config.save()
        enqueue_order_event(self.order, "created")
        meta = OutboundMessage.objects.get(channel=OutboundMessage.Channel.META_CAPI)
        ga4 = OutboundMessage.objects.get(channel=OutboundMessage.Channel.GA4)
        self.assertEqual(meta.payload["event"]["event_id"], f"tb-purchase-{self.order.order_number}")
        self.assertEqual(ga4.payload["events"][0]["params"]["transaction_id"], self.order.order_number)
        self.assertNotIn(self.customer.email, json.dumps(meta.payload))

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_outbox_email_delivery_marks_sent(self):
        message = OutboundMessage.objects.create(channel=OutboundMessage.Channel.EMAIL, event_type="test", recipient="buyer@example.com", subject="Hello", body="Queued delivery", idempotency_key="email:test:1")
        result = process_outbound(limit=10)
        message.refresh_from_db()
        self.assertEqual((result["sent"], message.status, len(mail.outbox)), (1, OutboundMessage.Status.SENT, 1))

    def test_failed_delivery_is_retryable_and_creates_alert(self):
        message = OutboundMessage.objects.create(channel=OutboundMessage.Channel.SMS, event_type="test", recipient="+8801711111111", body="Test", payload={"url": "https://example.invalid/sms"}, idempotency_key="sms:test:1")
        with patch("integrations.delivery.deliver_message", side_effect=DeliveryError("provider down")):
            result = process_outbound(limit=10)
        message.refresh_from_db()
        self.assertEqual(result["failed"], 1)
        self.assertEqual(message.status, OutboundMessage.Status.FAILED)
        alert = Notification.objects.get(kind=Notification.Kind.INTEGRATION)
        self.assertIn("provider down", alert.message)
        self.assertEqual(alert.link, reverse("integration_admin:integration_settings"))

    def test_courier_booking_uses_environment_configuration_without_secret_value(self):
        config = get_integration_settings()
        config.courier_api_enabled, config.notify_shipping_events = True, False
        config.save()
        courier = CourierProvider.objects.create(code="FAST", name="Fast Courier", api_enabled=True, is_active=True)
        shipment = Shipment.objects.create(order=self.order, courier=courier, cod_expected=Decimal("0.00"))
        secret = "super-secret-provider-token"
        with patch.dict(os.environ, {"COURIER_FAST_API_BASE_URL": "https://courier.example/api", "COURIER_FAST_CREATE_PATH": "/orders", "COURIER_FAST_API_TOKEN": secret}, clear=False):
            enqueue_shipping_event(shipment, "created")
        outbound = OutboundMessage.objects.get(channel=OutboundMessage.Channel.COURIER)
        self.assertEqual(outbound.payload["api_base_url"], "https://courier.example/api")
        self.assertEqual(outbound.payload["token_env"], "COURIER_FAST_API_TOKEN")
        self.assertNotIn(secret, json.dumps(outbound.payload))

    def test_failure_alert_helper_is_deduplicated_per_attempt(self):
        message = OutboundMessage.objects.create(channel=OutboundMessage.Channel.GA4, event_type="purchase", idempotency_key="ga4:test", attempts=1)
        enqueue_integration_failure(message, "bad gateway")
        enqueue_integration_failure(message, "bad gateway")
        self.assertEqual(Notification.objects.filter(kind=Notification.Kind.INTEGRATION).count(), 1)


class CourierWebhookTests(IntegrationBase):
    def test_invalid_signature_is_rejected(self):
        courier = CourierProvider.objects.create(code="HOOK", name="Hook Courier", api_enabled=True, is_active=True)
        with patch.dict(os.environ, {"COURIER_HOOK_WEBHOOK_SECRET": "topsecret"}, clear=False):
            response = self.client.post(reverse("integrations:courier_webhook", args=[courier.code]), data=json.dumps({"tracking_id": "ABC"}), content_type="application/json", HTTP_X_TECHBARI_SIGNATURE="wrong")
        self.assertEqual(response.status_code, 401)

    def test_valid_signature_can_update_tracking_location(self):
        courier = CourierProvider.objects.create(code="SIGNED", name="Signed Courier", api_enabled=True, is_active=True)
        shipment = Shipment.objects.create(order=self.order, courier=courier, tracking_id="TRK-1", courier_reference="REF-1")
        payload = json.dumps({"tracking_id": "TRK-1", "reference": "REF-1", "location": "Dhaka Hub", "note": "Scanned"}).encode()
        signature = hmac.new(b"topsecret", payload, hashlib.sha256).hexdigest()
        with patch.dict(os.environ, {"COURIER_SIGNED_WEBHOOK_SECRET": "topsecret"}, clear=False):
            response = self.client.post(reverse("integrations:courier_webhook", args=[courier.code]), data=payload, content_type="application/json", HTTP_X_TECHBARI_SIGNATURE=f"sha256={signature}")
        self.assertEqual(response.status_code, 200)
        shipment.refresh_from_db()
        self.assertEqual(shipment.last_location, "Dhaka Hub")


@override_settings(STAFF_AUTH_ENABLED=True)
class IntegrationPermissionTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.admin = users.objects.create_superuser(username="intadmin", email="admin@example.com", password="Testpass123!")
        self.cashier = users.objects.create_user(username="intcashier", password="Testpass123!", is_staff=True)
        self.cashier.groups.add(Group.objects.get(name="Cashier"))

    def test_admin_can_manage_integrations(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("integration_admin:integration_settings")).status_code, 200)

    def test_cashier_can_view_notifications_but_cannot_manage_integrations(self):
        self.client.force_login(self.cashier)
        self.assertEqual(self.client.get(reverse("backoffice:notifications")).status_code, 200)
        self.assertEqual(self.client.get(reverse("integration_admin:integration_settings")).status_code, 403)
        self.assertEqual(self.client.post(reverse("integration_admin:integration_process")).status_code, 403)


class StorefrontTrackingTests(IntegrationBase):
    def test_checkout_confirmation_contains_purchase_tracking_data(self):
        config = get_integration_settings()
        config.meta_pixel_enabled, config.meta_pixel_id = True, "123"
        config.ga4_enabled, config.ga4_measurement_id = True, "G-TEST"
        config.save()
        response = self.client.get(checkout_success_url(self.order))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="purchase-tracking-data"')
        self.assertContains(response, f"tb-purchase-{self.order.order_number}")
        self.assertContains(response, 'id="tracking-integrations"')
