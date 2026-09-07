from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from catalog.models import Brand, Category, Product, ProductVariant
from customers.models import Customer, CustomerGroup
from inventory.models import InventoryBalance, StockMovement, Warehouse
from payments.models import PaymentTransaction
from payments.services import capture_sales_payment
from sales.models import SalesOrder
from sales.services import save_sales_order, transition_order
from serial_tracking.models import SerializedUnit

from .models import SalesReturn, SalesReturnEvent, SalesReturnItem
from .services import (
    ReturnError,
    approve_sales_return,
    complete_sales_return,
    create_sales_return,
    receive_sales_return,
)


class ReturnsBase(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(name="Returns Warehouse", code="RET-MAIN", is_default=True, is_active=True)
        self.category = Category.objects.create(name="Return Phones", slug="return-phones")
        self.brand = Brand.objects.create(name="Return Brand", slug="return-brand")
        self.product = Product.objects.create(
            public_id="return-phone",
            name="Return Phone",
            slug="return-phone",
            category=self.category,
            brand=self.brand,
            regular_price=Decimal("100.00"),
            status=Product.Status.ACTIVE,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            name="Black",
            sku="RET-PHONE-BLK",
            stock_quantity=10,
            is_default=True,
            is_active=True,
        )
        balance, _ = InventoryBalance.objects.get_or_create(
            warehouse=self.warehouse,
            variant=self.variant,
            defaults={"on_hand": 10, "reserved_quantity": 0, "low_stock_threshold": 2},
        )
        balance.on_hand = 10
        balance.reserved_quantity = 0
        balance.save(update_fields=["on_hand", "reserved_quantity", "updated_at"])
        ProductVariant.objects.filter(pk=self.variant.pk).update(stock_quantity=10)

        self.group = CustomerGroup.objects.get(code="RETAIL")
        self.customer = Customer.objects.create(
            name="Return Customer",
            phone="01790000001",
            email="return@example.com",
            group=self.group,
            address="Road 10",
            city="Dhaka",
            district="Dhaka",
        )

    def create_completed_order(self, quantity=2):
        order = save_sales_order(
            header_data={
                "order_number": "",
                "customer": self.customer,
                "warehouse": self.warehouse,
                "channel": SalesOrder.Channel.ONLINE,
                "status": SalesOrder.Status.PENDING,
                "order_date": date(2026, 9, 7),
                "shipping_name": "",
                "shipping_phone": "",
                "shipping_email": "",
                "shipping_address": "",
                "shipping_city": "",
                "shipping_district": "",
                "shipping_postal_code": "",
                "discount_amount": Decimal("0.00"),
                "shipping_charge": Decimal("0.00"),
                "amount_paid": Decimal("0.00"),
                "notes": "Returns test",
            },
            item_rows=[{
                "variant": self.variant,
                "quantity": quantity,
                "unit_price": Decimal("100.00"),
                "discount_amount": Decimal("0.00"),
            }],
            actor="Test",
        )
        transition_order(order=order, new_status=SalesOrder.Status.CONFIRMED, actor="Test")
        transition_order(order=order, new_status=SalesOrder.Status.COMPLETED, actor="Test")
        order.refresh_from_db()
        return order

    def open_return(self, order, *, quantity=1, credit=Decimal("100.00"), disposition=SalesReturnItem.Disposition.RESTOCK, serialized_unit=None, resolution=SalesReturn.Resolution.REFUND):
        return create_sales_return(
            order=order,
            warehouse=self.warehouse,
            source=SalesReturn.Source.CUSTOMER,
            resolution=resolution,
            reason_category=SalesReturn.Reason.DEFECTIVE,
            requested_date=date(2026, 9, 7),
            item_rows=[{
                "order_item_id": order.items.get().pk,
                "quantity": quantity,
                "refund_amount": credit,
                "condition": SalesReturnItem.Condition.DEFECTIVE,
                "disposition": disposition,
                "serialized_unit_id": serialized_unit.pk if serialized_unit else "",
                "note": "Return item test",
            }],
            actor="Test",
        )

    def complete_return(self, sales_return):
        approve_sales_return(sales_return=sales_return, actor="Test")
        sales_return.refresh_from_db()
        receive_sales_return(sales_return=sales_return, actor="Test")
        sales_return.refresh_from_db()
        return complete_sales_return(sales_return=sales_return, actor="Test")


class ReturnServiceTests(ReturnsBase):
    def test_completed_restock_return_posts_inventory_credit_and_cash_refund(self):
        order = self.create_completed_order(quantity=2)
        payment = capture_sales_payment(order=order, amount=Decimal("200.00"), method="cash", actor="Test")
        sales_return = self.open_return(order)
        self.complete_return(sales_return)

        order.refresh_from_db()
        sales_return.refresh_from_db()
        balance = InventoryBalance.objects.get(warehouse=self.warehouse, variant=self.variant)
        self.assertEqual(sales_return.status, SalesReturn.Status.COMPLETED)
        self.assertEqual(balance.on_hand, 9)
        self.assertEqual(order.return_credit_amount, Decimal("100.00"))
        self.assertEqual(order.payable_total, Decimal("100.00"))
        self.assertEqual(order.amount_paid, Decimal("100.00"))
        self.assertEqual(order.outstanding_amount, Decimal("0.00"))
        self.assertEqual(sales_return.refunded_total, Decimal("100.00"))
        refund = PaymentTransaction.objects.get(parent_transaction=payment, kind=PaymentTransaction.Kind.REFUND)
        self.assertEqual(refund.amount, Decimal("100.00"))
        self.assertEqual(self.customer.total_spent, Decimal("100.00"))
        self.assertTrue(StockMovement.objects.filter(reference_no=sales_return.return_no, movement_type=StockMovement.Type.RETURN_IN).exists())

    def test_partial_payment_return_credit_reduces_due_without_unnecessary_cash_refund(self):
        order = self.create_completed_order(quantity=2)
        capture_sales_payment(order=order, amount=Decimal("100.00"), method="cash", actor="Test")
        sales_return = self.open_return(order)
        self.complete_return(sales_return)
        order.refresh_from_db()
        sales_return.refresh_from_db()
        self.assertEqual(order.payable_total, Decimal("100.00"))
        self.assertEqual(order.amount_paid, Decimal("100.00"))
        self.assertEqual(order.outstanding_amount, Decimal("0.00"))
        self.assertEqual(sales_return.refunded_total, Decimal("0.00"))
        self.assertFalse(PaymentTransaction.objects.filter(sales_order=order, kind=PaymentTransaction.Kind.REFUND).exists())

    def test_active_returns_cannot_exceed_issued_quantity_or_line_credit(self):
        order = self.create_completed_order(quantity=2)
        self.open_return(order, quantity=1, credit=Decimal("100.00"))
        with self.assertRaises(ReturnError):
            self.open_return(order, quantity=2, credit=Decimal("100.00"))
        with self.assertRaises(ReturnError):
            self.open_return(order, quantity=1, credit=Decimal("101.00"))

    def test_damaged_no_refund_return_does_not_inflate_sellable_inventory(self):
        order = self.create_completed_order(quantity=1)
        sales_return = self.open_return(
            order,
            quantity=1,
            credit=Decimal("0.00"),
            disposition=SalesReturnItem.Disposition.DAMAGED,
            resolution=SalesReturn.Resolution.NO_REFUND,
        )
        self.complete_return(sales_return)
        balance = InventoryBalance.objects.get(warehouse=self.warehouse, variant=self.variant)
        order.refresh_from_db()
        self.assertEqual(balance.on_hand, 9)
        self.assertEqual(order.return_credit_amount, Decimal("0.00"))
        self.assertEqual(sales_return.items.get().restocked_quantity, 0)

    def test_serialized_return_updates_exact_unit_and_inventory_once(self):
        order = self.create_completed_order(quantity=1)
        unit = SerializedUnit.objects.create(
            variant=self.variant,
            warehouse=self.warehouse,
            serial_number="RET-SERIAL-001",
            status=SerializedUnit.Status.SOLD,
            sales_reference=order.order_number,
            customer_reference=self.customer.customer_no,
            sold_at=date(2026, 9, 7),
        )
        sales_return = self.open_return(order, serialized_unit=unit)
        self.complete_return(sales_return)
        unit.refresh_from_db()
        balance = InventoryBalance.objects.get(warehouse=self.warehouse, variant=self.variant)
        self.assertEqual(unit.status, SerializedUnit.Status.RETURNED)
        self.assertEqual(balance.on_hand, 10)
        with self.assertRaises(ReturnError):
            complete_sales_return(sales_return=sales_return, actor="Test")

    def test_refund_can_allocate_across_multiple_original_payments(self):
        order = self.create_completed_order(quantity=2)
        first = capture_sales_payment(order=order, amount=Decimal("60.00"), method="cash", actor="Test")
        second = capture_sales_payment(order=order, amount=Decimal("140.00"), method="cash", actor="Test")
        sales_return = self.open_return(order, quantity=1, credit=Decimal("100.00"))
        self.complete_return(sales_return)
        links = list(sales_return.refunds.order_by("id"))
        self.assertEqual(len(links), 2)
        self.assertEqual(links[0].source_payment_id, first.pk)
        self.assertEqual(links[0].amount, Decimal("60.00"))
        self.assertEqual(links[1].source_payment_id, second.pk)
        self.assertEqual(links[1].amount, Decimal("40.00"))

    def test_return_event_history_is_immutable(self):
        order = self.create_completed_order(quantity=1)
        sales_return = self.open_return(order)
        event = SalesReturnEvent.objects.filter(sales_return=sales_return).first()
        event.note = "tamper"
        with self.assertRaises(ValidationError):
            event.save()


class ReturnDashboardTests(ReturnsBase):
    def test_return_pages_render_real_database_data(self):
        order = self.create_completed_order(quantity=1)
        sales_return = self.open_return(order)
        response = self.client.get(reverse("backoffice:returns"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, sales_return.return_no)
        response = self.client.get(reverse("backoffice:return_detail", args=[sales_return.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, order.order_number)
        response = self.client.get(reverse("backoffice:return_add") + f"?order={order.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Return Phone")

    def test_dashboard_can_create_approve_receive_and_complete_return(self):
        order = self.create_completed_order(quantity=1)
        capture_sales_payment(order=order, amount=Decimal("100.00"), method="cash", actor="Test")
        item = order.items.get()
        response = self.client.post(reverse("backoffice:return_add"), {
            "order": order.pk,
            "warehouse": self.warehouse.pk,
            "source": SalesReturn.Source.CUSTOMER,
            "resolution": SalesReturn.Resolution.REFUND,
            "reason_category": SalesReturn.Reason.DEFECTIVE,
            "requested_date": "2026-09-07",
            "source_reference": "",
            "refund_reference": "",
            "customer_note": "Customer says defective",
            "internal_note": "Inspect first",
            f"include_{item.pk}": "1",
            f"quantity_{item.pk}": "1",
            f"refund_amount_{item.pk}": "100.00",
            f"condition_{item.pk}": SalesReturnItem.Condition.DEFECTIVE,
            f"disposition_{item.pk}": SalesReturnItem.Disposition.RESTOCK,
            f"serialized_unit_{item.pk}": "",
            f"item_note_{item.pk}": "Accepted",
        })
        self.assertEqual(response.status_code, 302)
        sales_return = SalesReturn.objects.get(order=order)
        self.client.post(reverse("backoffice:return_approve", args=[sales_return.pk]), {"note": "Approved"})
        sales_return.refresh_from_db()
        self.assertEqual(sales_return.status, SalesReturn.Status.APPROVED)
        self.client.post(reverse("backoffice:return_receive", args=[sales_return.pk]), {"note": "Received"})
        sales_return.refresh_from_db()
        self.assertEqual(sales_return.status, SalesReturn.Status.RECEIVED)
        response = self.client.post(reverse("backoffice:return_complete", args=[sales_return.pk]), {"note": "Complete"})
        self.assertEqual(response.status_code, 302)
        sales_return.refresh_from_db()
        self.assertEqual(sales_return.status, SalesReturn.Status.COMPLETED)
