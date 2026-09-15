from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from customers.models import Customer, CustomerGroup
from inventory.models import Warehouse
from payments.models import PaymentTransaction
from sales.models import SalesOrder
from shipping.models import CourierProvider, Shipment

from .models import Notification


@override_settings(STAFF_AUTH_ENABLED=True)
class NotificationSafetyTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="notification-safety-admin",
            email="admin@example.com",
            password="Testpass123!",
        )
        self.client.force_login(self.admin)
        self.warehouse = Warehouse.objects.create(
            name="Notification Safety Warehouse",
            code="NOTIF-SAFE",
            is_default=True,
            is_active=True,
        )
        group, _ = CustomerGroup.objects.get_or_create(
            code="NOTIF-SAFE",
            defaults={"name": "Notification Safety"},
        )
        self.customer = Customer.objects.create(
            name="Notification Safety Customer",
            phone="01700000091",
            email="notify-safety@example.com",
            group=group,
        )
        self.order = SalesOrder.objects.create(
            customer=self.customer,
            warehouse=self.warehouse,
            channel=SalesOrder.Channel.ONLINE,
            status=SalesOrder.Status.PENDING,
            shipping_name=self.customer.name,
            shipping_phone=self.customer.phone,
            shipping_email=self.customer.email,
            grand_total=Decimal("100.00"),
        )
        Notification.objects.all().delete()

    def test_stale_order_notification_shows_unavailable_instead_of_open(self):
        Notification.objects.create(
            kind=Notification.Kind.ORDER,
            severity=Notification.Severity.INFO,
            title="Old order",
            message="Deleted order notification",
            link=reverse("backoffice:order_detail_id", args=[999999]),
            reference_type="sales_order",
            reference_id="TB-MISSING-ORDER",
        )
        response = self.client.get(reverse("backoffice:notifications"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unavailable")
        self.assertNotContains(response, reverse("backoffice:order_detail_id", args=[999999]))

    def test_safe_notification_open_redirects_missing_target_back_to_notifications(self):
        notification = Notification.objects.create(
            kind=Notification.Kind.ORDER,
            severity=Notification.Severity.INFO,
            title="Old order",
            message="Deleted order notification",
            link=reverse("backoffice:order_detail_id", args=[999999]),
            reference_type="sales_order",
            reference_id="TB-MISSING-ORDER",
        )
        response = self.client.get(reverse("integration_admin:notifications", args=[notification.pk]))
        self.assertRedirects(response, reverse("backoffice:notifications"), fetch_redirect_response=False)

    def test_safe_notification_open_redirects_valid_target_to_detail(self):
        target = reverse("backoffice:order_detail_id", args=[self.order.pk])
        notification = Notification.objects.create(
            kind=Notification.Kind.ORDER,
            severity=Notification.Severity.INFO,
            title="Current order",
            message="Valid order notification",
            link=target,
            reference_type="sales_order",
            reference_id=self.order.order_number,
        )
        response = self.client.get(reverse("integration_admin:notifications", args=[notification.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, target)

    def test_order_delete_removes_related_notifications(self):
        notification = Notification.objects.create(
            kind=Notification.Kind.ORDER,
            title="Order",
            message="Order",
            reference_type="sales_order",
            reference_id=self.order.order_number,
        )
        self.order.delete()
        self.assertFalse(Notification.objects.filter(pk=notification.pk).exists())

    def test_payment_delete_removes_related_notifications(self):
        payment = PaymentTransaction.objects.create(
            sales_order=self.order,
            kind=PaymentTransaction.Kind.SALE_PAYMENT,
            direction=PaymentTransaction.Direction.IN,
            method="cash",
            status=PaymentTransaction.Status.COMPLETED,
            amount=Decimal("10.00"),
        )
        notification = Notification.objects.create(
            kind=Notification.Kind.PAYMENT,
            title="Payment",
            message="Payment",
            reference_type="payment",
            reference_id=payment.transaction_no,
        )
        payment.delete()
        self.assertFalse(Notification.objects.filter(pk=notification.pk).exists())

    def test_shipment_delete_removes_related_notifications(self):
        courier = CourierProvider.objects.create(code="SAFE", name="Safety Courier", is_active=True)
        shipment = Shipment.objects.create(order=self.order, courier=courier)
        notification = Notification.objects.create(
            kind=Notification.Kind.SHIPPING,
            title="Shipment",
            message="Shipment",
            reference_type="shipment",
            reference_id=shipment.shipment_no,
        )
        shipment.delete()
        self.assertFalse(Notification.objects.filter(pk=notification.pk).exists())

    def test_stock_notification_keeps_generic_safe_link_available(self):
        notification = Notification.objects.create(
            kind=Notification.Kind.STOCK,
            severity=Notification.Severity.WARNING,
            title="Low stock",
            message="Stock alert",
            link=reverse("backoffice:inventory_low_stock"),
            reference_type="inventory_balance",
            reference_id="999999",
        )
        response = self.client.get(reverse("integration_admin:notifications", args=[notification.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("backoffice:inventory_low_stock"))

    @override_settings(DEBUG=False)
    def test_missing_dashboard_record_uses_branded_404(self):
        response = self.client.get(reverse("backoffice:order_detail_id", args=[999999]))
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "This page isn’t available", status_code=404)
        self.assertContains(response, "Back to Dashboard", status_code=404)
