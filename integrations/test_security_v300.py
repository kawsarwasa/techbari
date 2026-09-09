import hashlib
import hmac
import json
import os
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from catalog.models import Brand, Category, Product, ProductVariant
from customers.models import Customer, CustomerGroup
from inventory.models import InventoryBalance, Warehouse
from sales.models import SalesOrder
from sales.services import save_sales_order
from shipping.models import CourierProvider, Shipment

from .models import CourierWebhookReceipt


class CourierWebhookSecurityV300Tests(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(name="Webhook Warehouse", code="WEBHOOK", is_default=True, is_active=True)
        category = Category.objects.create(name="Webhook Category", slug="webhook-category")
        brand = Brand.objects.create(name="Webhook Brand", slug="webhook-brand")
        product = Product.objects.create(public_id="webhook-product", name="Webhook Product", slug="webhook-product", category=category, brand=brand, regular_price=Decimal("100.00"), status=Product.Status.ACTIVE)
        variant = ProductVariant.objects.create(product=product, name="Default", sku="WEBHOOK-SKU", stock_quantity=5, is_default=True, is_active=True)
        balance, _ = InventoryBalance.objects.get_or_create(warehouse=self.warehouse, variant=variant, defaults={"on_hand": 5, "reserved_quantity": 0, "low_stock_threshold": 1})
        balance.on_hand = 5
        balance.reserved_quantity = 0
        balance.save(update_fields=["on_hand", "reserved_quantity", "updated_at"])
        group = CustomerGroup.objects.get(code="RETAIL")
        customer = Customer.objects.create(name="Webhook Customer", phone="01711112222", email="webhook@example.com", group=group, address="Dhaka")
        order = save_sales_order(
            header_data={
                "customer": customer,
                "warehouse": self.warehouse,
                "channel": SalesOrder.Channel.ONLINE,
                "status": SalesOrder.Status.PENDING,
                "order_date": date(2026, 9, 9),
                "shipping_name": customer.name,
                "shipping_phone": customer.phone,
                "shipping_email": customer.email,
                "shipping_address": customer.address,
                "shipping_city": "Dhaka",
                "shipping_district": "Dhaka",
                "shipping_postal_code": "1200",
                "discount_amount": Decimal("0.00"),
                "shipping_charge": Decimal("60.00"),
                "amount_paid": Decimal("0.00"),
            },
            item_rows=[{"variant": variant, "quantity": 1, "unit_price": Decimal("100.00"), "discount_amount": Decimal("0.00")}],
            actor="Webhook Test",
        )
        self.courier = CourierProvider.objects.create(code="SECURE", name="Secure Courier", api_enabled=True, is_active=True)
        self.shipment = Shipment.objects.create(order=order, courier=self.courier, tracking_id="SEC-1", courier_reference="REF-1")
        self.url = reverse("integrations:courier_webhook", args=[self.courier.code])
        self.secret = "v3-webhook-secret"

    def _payload(self):
        return json.dumps({"tracking_id": "SEC-1", "reference": "REF-1", "location": "Dhaka Hub", "note": "Arrived"}, separators=(",", ":")).encode("utf-8")

    @override_settings(COURIER_WEBHOOK_REQUIRE_TIMESTAMP=True, COURIER_WEBHOOK_MAX_SKEW_SECONDS=300)
    def test_timestamp_is_required_when_production_mode_enables_it(self):
        body = self._payload()
        signature = hmac.new(self.secret.encode(), body, hashlib.sha256).hexdigest()
        with patch.dict(os.environ, {"COURIER_SECURE_WEBHOOK_SECRET": self.secret}, clear=False):
            response = self.client.post(self.url, data=body, content_type="application/json", HTTP_X_TECHBARI_SIGNATURE=f"sha256={signature}")
        self.assertEqual(response.status_code, 401)

    @override_settings(COURIER_WEBHOOK_REQUIRE_TIMESTAMP=True, COURIER_WEBHOOK_MAX_SKEW_SECONDS=60)
    def test_stale_timestamp_is_rejected(self):
        body = self._payload()
        timestamp = str(int(timezone.now().timestamp()) - 3600)
        signed = timestamp.encode() + b"." + body
        signature = hmac.new(self.secret.encode(), signed, hashlib.sha256).hexdigest()
        with patch.dict(os.environ, {"COURIER_SECURE_WEBHOOK_SECRET": self.secret}, clear=False):
            response = self.client.post(self.url, data=body, content_type="application/json", HTTP_X_TECHBARI_TIMESTAMP=timestamp, HTTP_X_TECHBARI_SIGNATURE=f"sha256={signature}")
        self.assertEqual(response.status_code, 401)

    @override_settings(COURIER_WEBHOOK_REQUIRE_TIMESTAMP=True, COURIER_WEBHOOK_MAX_SKEW_SECONDS=300)
    def test_valid_timestamped_webhook_is_replay_safe(self):
        body = self._payload()
        timestamp = str(int(timezone.now().timestamp()))
        signed = timestamp.encode() + b"." + body
        signature = hmac.new(self.secret.encode(), signed, hashlib.sha256).hexdigest()
        headers = {"HTTP_X_TECHBARI_TIMESTAMP": timestamp, "HTTP_X_TECHBARI_SIGNATURE": f"sha256={signature}"}
        with patch.dict(os.environ, {"COURIER_SECURE_WEBHOOK_SECRET": self.secret}, clear=False):
            first = self.client.post(self.url, data=body, content_type="application/json", **headers)
            second = self.client.post(self.url, data=body, content_type="application/json", **headers)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json().get("duplicate"))
        self.assertEqual(CourierWebhookReceipt.objects.count(), 1)
        self.shipment.refresh_from_db()
        self.assertEqual(self.shipment.last_location, "Dhaka Hub")

    @override_settings(COURIER_WEBHOOK_MAX_BYTES=32)
    def test_oversized_webhook_is_rejected_before_processing(self):
        body = b"{" + b"x" * 100 + b"}"
        with patch.dict(os.environ, {"COURIER_SECURE_WEBHOOK_SECRET": self.secret}, clear=False):
            response = self.client.post(self.url, data=body, content_type="application/json")
        self.assertEqual(response.status_code, 413)
