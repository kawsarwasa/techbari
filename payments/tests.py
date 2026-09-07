from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from inventory.models import Warehouse
from purchasing.models import PurchaseOrder, PurchasePayment, Supplier
from sales.models import SalesOrder
from sales.services import update_order_payment

from .models import PaymentEvent, PaymentMethodConfig, PaymentTransaction
from .services import (
    PaymentError,
    capture_sales_payment,
    reconcile_payment,
    refund_sales_payment,
    reverse_sales_payment,
)


class PaymentBase(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(name="Payment Warehouse", code="PAY-WH", is_default=True, is_active=True)
        self.order = SalesOrder.objects.create(
            order_number="TB-PAY-001",
            warehouse=self.warehouse,
            channel=SalesOrder.Channel.MANUAL,
            status=SalesOrder.Status.CONFIRMED,
            order_date=date(2026, 9, 7),
            shipping_name="Payment Customer",
            shipping_phone="01700000000",
            subtotal=Decimal("200.00"),
            grand_total=Decimal("200.00"),
        )


class PaymentServiceTests(PaymentBase):
    def test_default_payment_methods_are_seeded(self):
        methods = set(PaymentMethodConfig.objects.values_list("method", flat=True))
        self.assertTrue({"cash", "bank", "card", "bkash", "nagad", "other"}.issubset(methods))

    def test_partial_and_multiple_payments_sync_order(self):
        first = capture_sales_payment(order=self.order, amount="50.00", method="cash", actor="Test")
        second = capture_sales_payment(order=self.order, amount="150.00", method="bkash", reference="BK123", actor="Test")
        self.order.refresh_from_db()
        self.assertEqual(first.kind, PaymentTransaction.Kind.SALE_PAYMENT)
        self.assertEqual(second.provider_reference, "BK123")
        self.assertEqual(self.order.amount_paid, Decimal("200.00"))
        self.assertEqual(self.order.payment_status, SalesOrder.PaymentStatus.PAID)
        self.assertEqual(self.order.payment_transactions.filter(kind=PaymentTransaction.Kind.SALE_PAYMENT).count(), 2)

    def test_overpayment_and_missing_non_cash_reference_are_blocked(self):
        with self.assertRaises(PaymentError):
            capture_sales_payment(order=self.order, amount="201.00", method="cash", actor="Test")
        with self.assertRaises(PaymentError):
            capture_sales_payment(order=self.order, amount="20.00", method="card", actor="Test")
        self.assertEqual(PaymentTransaction.objects.count(), 0)

    def test_refund_updates_order_paid_amount_and_status(self):
        payment = capture_sales_payment(order=self.order, amount="200.00", method="cash", actor="Test")
        refund = refund_sales_payment(payment=payment, amount="75.00", actor="Test", note="Partial return")
        self.order.refresh_from_db()
        self.assertEqual(refund.kind, PaymentTransaction.Kind.REFUND)
        self.assertEqual(refund.direction, PaymentTransaction.Direction.OUT)
        self.assertEqual(self.order.amount_paid, Decimal("125.00"))
        self.assertEqual(self.order.payment_status, SalesOrder.PaymentStatus.PARTIAL)
        with self.assertRaises(PaymentError):
            refund_sales_payment(payment=payment, amount="126.00", actor="Test")

    def test_full_reversal_and_reconciliation_rules(self):
        payment = capture_sales_payment(order=self.order, amount="100.00", method="cash", actor="Test")
        reversal = reverse_sales_payment(payment=payment, actor="Test", note="Wrong entry")
        payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(payment.status, PaymentTransaction.Status.REVERSED)
        self.assertEqual(reversal.kind, PaymentTransaction.Kind.REVERSAL)
        self.assertEqual(self.order.amount_paid, Decimal("0.00"))
        self.assertEqual(self.order.payment_status, SalesOrder.PaymentStatus.REFUNDED)

        payment2 = capture_sales_payment(order=self.order, amount="50.00", method="cash", actor="Test")
        reconcile_payment(payment=payment2, actor="Test")
        payment2.refresh_from_db()
        self.assertEqual(payment2.reconciliation_status, PaymentTransaction.ReconciliationStatus.RECONCILED)
        with self.assertRaises(PaymentError):
            reverse_sales_payment(payment=payment2, actor="Test")

    def test_payment_events_are_immutable(self):
        payment = capture_sales_payment(order=self.order, amount="20.00", method="cash", actor="Test")
        event = payment.events.first()
        event.note = "tamper"
        with self.assertRaises(ValidationError):
            event.save()
        with self.assertRaises(ValidationError):
            event.delete()

    def test_legacy_sales_amount_updates_are_mirrored_to_ledger(self):
        update_order_payment(order=self.order, amount_paid=Decimal("80.00"), actor="Legacy")
        self.order.refresh_from_db()
        self.assertEqual(self.order.amount_paid, Decimal("80.00"))
        self.assertEqual(self.order.payment_transactions.filter(kind=PaymentTransaction.Kind.SALE_PAYMENT).count(), 1)
        update_order_payment(order=self.order, amount_paid=Decimal("30.00"), actor="Legacy")
        self.order.refresh_from_db()
        self.assertEqual(self.order.amount_paid, Decimal("30.00"))
        self.assertEqual(self.order.payment_transactions.filter(kind=PaymentTransaction.Kind.REFUND).count(), 1)

    def test_supplier_payment_is_mirrored_to_central_ledger(self):
        supplier = Supplier.objects.create(code="PAY-SUP", name="Payment Supplier")
        purchase = PurchaseOrder.objects.create(
            po_number="PO-PAY-001",
            supplier=supplier,
            warehouse=self.warehouse,
            status=PurchaseOrder.Status.ORDERED,
            purchase_date=date(2026, 9, 7),
        )
        purchase_payment = PurchasePayment.objects.create(
            payment_no="PAY-PUR-001",
            purchase=purchase,
            supplier=supplier,
            amount=Decimal("40.00"),
            method=PurchasePayment.Method.BANK,
            reference="BANK-1",
            payment_date=date(2026, 9, 7),
            actor="Test",
        )
        ledger = PaymentTransaction.objects.get(purchase_payment=purchase_payment)
        self.assertEqual(ledger.kind, PaymentTransaction.Kind.SUPPLIER_PAYMENT)
        self.assertEqual(ledger.direction, PaymentTransaction.Direction.OUT)
        self.assertEqual(ledger.amount, Decimal("40.00"))


class PaymentDashboardTests(PaymentBase):
    def test_payment_pages_render_real_transactions(self):
        payment = capture_sales_payment(order=self.order, amount="50.00", method="cash", actor="Test")
        response = self.client.get(reverse("backoffice:payments"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, payment.transaction_no)
        response = self.client.get(reverse("backoffice:payment_detail", args=[payment.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Payment Audit Trail")
        self.assertEqual(self.client.get(reverse("backoffice:payment_methods")).status_code, 200)
        self.assertEqual(self.client.get(reverse("backoffice:payment_add") + f"?order={self.order.pk}").status_code, 200)

    def test_dashboard_can_record_refund_and_reconcile(self):
        response = self.client.post(reverse("backoffice:payment_add"), {
            "sales_order": self.order.pk,
            "amount": "100.00",
            "method": "bkash",
            "reference": "BK-DASH-1",
            "transaction_date": "2026-09-07",
            "note": "Dashboard payment",
        })
        self.assertEqual(response.status_code, 302)
        payment = PaymentTransaction.objects.get(kind=PaymentTransaction.Kind.SALE_PAYMENT)
        self.assertEqual(self.client.post(reverse("backoffice:payment_refund", args=[payment.pk]), {"amount": "25.00", "reference": "BK-REF-1", "note": "Partial refund"}).status_code, 302)
        self.assertEqual(self.client.post(reverse("backoffice:payment_reconcile", args=[payment.pk]), {"reconciliation_status": "reconciled", "note": "Matched statement"}).status_code, 302)
        payment.refresh_from_db()
        self.assertEqual(payment.reconciliation_status, PaymentTransaction.ReconciliationStatus.RECONCILED)
        self.order.refresh_from_db()
        self.assertEqual(self.order.amount_paid, Decimal("75.00"))
