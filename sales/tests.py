from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from catalog.models import Brand, Category, Product, ProductVariant
from customers.models import Customer, CustomerGroup
from customers.services import CustomerError, delete_customer
from inventory.models import InventoryBalance, Warehouse

from .models import SalesOrder, SalesOrderHistory
from .services import (
    SalesOrderError,
    save_sales_order,
    transition_order,
    update_order_payment,
)


class SalesBase(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(name="Main Sales Warehouse", code="SALE-MAIN", is_default=True, is_active=True)
        self.category = Category.objects.create(name="Sales Phones", slug="sales-phones")
        self.brand = Brand.objects.create(name="Sales Brand", slug="sales-brand")
        self.product = Product.objects.create(
            public_id="sales-phone",
            name="Sales Phone",
            slug="sales-phone",
            category=self.category,
            brand=self.brand,
            regular_price=Decimal("100.00"),
            status=Product.Status.ACTIVE,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            name="Black",
            sku="SALE-PHONE-BLK",
            stock_quantity=10,
            is_default=True,
            is_active=True,
        )
        # Keep the fixture explicit: Sales tests must exercise the selected warehouse,
        # regardless of legacy stock-cache/bootstrap behavior used by Catalog tests.
        balance, _ = InventoryBalance.objects.get_or_create(
            warehouse=self.warehouse,
            variant=self.variant,
            defaults={"on_hand": 10, "reserved_quantity": 0, "low_stock_threshold": 5},
        )
        balance.on_hand = 10
        balance.reserved_quantity = 0
        balance.save(update_fields=["on_hand", "reserved_quantity", "updated_at"])
        ProductVariant.objects.filter(pk=self.variant.pk).update(stock_quantity=10)
        self.variant.refresh_from_db()

        self.group = CustomerGroup.objects.get(code="RETAIL")
        self.customer = Customer.objects.create(
            name="Sales Customer",
            phone="01755555555",
            email="sales@example.com",
            group=self.group,
            address="Road 1",
            city="Dhaka",
            district="Dhaka",
        )

    def header(self, status=SalesOrder.Status.PENDING, paid=Decimal("0.00")):
        return {
            "order_number": "",
            "customer": self.customer,
            "warehouse": self.warehouse,
            "channel": SalesOrder.Channel.ONLINE,
            "status": status,
            "order_date": date(2026, 9, 7),
            "shipping_name": "",
            "shipping_phone": "",
            "shipping_email": "",
            "shipping_address": "",
            "shipping_city": "",
            "shipping_district": "",
            "shipping_postal_code": "",
            "discount_amount": Decimal("10.00"),
            "shipping_charge": Decimal("20.00"),
            "amount_paid": paid,
            "notes": "Sales test",
        }

    def rows(self, quantity=2, unit_price=Decimal("100.00"), line_discount=Decimal("5.00")):
        return [{
            "variant": self.variant,
            "quantity": quantity,
            "unit_price": unit_price,
            "discount_amount": line_discount,
        }]

    def create_order(self, status=SalesOrder.Status.PENDING, quantity=2):
        return save_sales_order(header_data=self.header(status=status), item_rows=self.rows(quantity=quantity), actor="Test")


class SalesOrderServiceTests(SalesBase):
    def test_pending_order_reserves_inventory_and_calculates_totals(self):
        order = self.create_order()
        balance = InventoryBalance.objects.get(warehouse=self.warehouse, variant=self.variant)
        item = order.items.get()
        self.assertEqual(order.subtotal, Decimal("195.00"))
        self.assertEqual(order.grand_total, Decimal("205.00"))
        self.assertEqual(order.payment_status, SalesOrder.PaymentStatus.UNPAID)
        self.assertEqual(balance.on_hand, 10)
        self.assertEqual(balance.reserved_quantity, 2)
        self.assertEqual(item.reserved_quantity, 2)
        self.assertEqual(item.issued_quantity, 0)
        self.assertEqual(order.shipping_name, self.customer.name)
        self.assertEqual(order.shipping_phone, self.customer.phone)

    def test_confirm_process_complete_deducts_reserved_inventory(self):
        order = self.create_order()
        transition_order(order=order, new_status=SalesOrder.Status.CONFIRMED, actor="Test")
        transition_order(order=order, new_status=SalesOrder.Status.PROCESSING, actor="Test")
        transition_order(order=order, new_status=SalesOrder.Status.COMPLETED, actor="Test")
        order.refresh_from_db()
        item = order.items.get()
        balance = InventoryBalance.objects.get(warehouse=self.warehouse, variant=self.variant)
        self.assertEqual(order.status, SalesOrder.Status.COMPLETED)
        self.assertEqual(balance.on_hand, 8)
        self.assertEqual(balance.reserved_quantity, 0)
        self.assertEqual(item.issued_quantity, 2)
        self.assertEqual(item.reserved_quantity, 0)
        self.assertEqual(self.customer.completed_order_count, 1)
        self.assertEqual(self.customer.total_spent, Decimal("205.00"))
        self.assertEqual(self.customer.due_balance, Decimal("205.00"))

    def test_repeat_customer_tracking_after_two_completed_orders(self):
        first = self.create_order(quantity=1)
        transition_order(order=first, new_status=SalesOrder.Status.CONFIRMED, actor="Test")
        transition_order(order=first, new_status=SalesOrder.Status.COMPLETED, actor="Test")
        second = self.create_order(quantity=1)
        transition_order(order=second, new_status=SalesOrder.Status.CONFIRMED, actor="Test")
        transition_order(order=second, new_status=SalesOrder.Status.COMPLETED, actor="Test")
        self.assertEqual(self.customer.completed_order_count, 2)
        self.assertTrue(self.customer.repeat_customer)

    def test_cancel_releases_reservation_without_deducting_stock(self):
        order = self.create_order(quantity=3)
        transition_order(order=order, new_status=SalesOrder.Status.CANCELLED, actor="Test")
        balance = InventoryBalance.objects.get(warehouse=self.warehouse, variant=self.variant)
        order.refresh_from_db()
        self.assertEqual(order.status, SalesOrder.Status.CANCELLED)
        self.assertEqual(balance.on_hand, 10)
        self.assertEqual(balance.reserved_quantity, 0)

    def test_overselling_rolls_back_entire_order(self):
        with self.assertRaises(SalesOrderError):
            self.create_order(quantity=11)
        self.assertEqual(SalesOrder.objects.count(), 0)
        balance = InventoryBalance.objects.get(warehouse=self.warehouse, variant=self.variant)
        self.assertEqual(balance.on_hand, 10)
        self.assertEqual(balance.reserved_quantity, 0)

    def test_edit_pending_order_rebalances_reservation_atomically(self):
        order = self.create_order(quantity=2)
        order = save_sales_order(header_data=self.header(status=SalesOrder.Status.PENDING), item_rows=self.rows(quantity=4), order=order, actor="Test")
        balance = InventoryBalance.objects.get(warehouse=self.warehouse, variant=self.variant)
        item = order.items.get()
        self.assertEqual(balance.reserved_quantity, 4)
        self.assertEqual(item.reserved_quantity, 4)
        self.assertEqual(item.quantity, 4)

    def test_invalid_transition_is_blocked(self):
        order = self.create_order()
        with self.assertRaises(SalesOrderError):
            transition_order(order=order, new_status=SalesOrder.Status.PROCESSING, actor="Test")

    def test_payment_status_and_customer_due_update(self):
        order = self.create_order()
        update_order_payment(order=order, amount_paid=Decimal("100.00"), actor="Test")
        order.refresh_from_db()
        self.assertEqual(order.payment_status, SalesOrder.PaymentStatus.PARTIAL)
        self.assertEqual(order.outstanding_amount, Decimal("105.00"))
        self.assertEqual(self.customer.due_balance, Decimal("105.00"))
        update_order_payment(order=order, amount_paid=order.grand_total, actor="Test")
        order.refresh_from_db()
        self.assertEqual(order.payment_status, SalesOrder.PaymentStatus.PAID)
        self.assertEqual(self.customer.due_balance, Decimal("0.00"))

    def test_customer_with_order_history_cannot_be_deleted(self):
        self.create_order(status=SalesOrder.Status.DRAFT)
        with self.assertRaises(CustomerError):
            delete_customer(customer=self.customer)

    def test_history_is_immutable_and_status_transitions_are_recorded(self):
        order = self.create_order()
        transition_order(order=order, new_status=SalesOrder.Status.CONFIRMED, actor="Test")
        history = SalesOrderHistory.objects.filter(order=order, event=SalesOrderHistory.Event.STATUS).first()
        self.assertEqual(history.previous_status, SalesOrder.Status.PENDING)
        self.assertEqual(history.new_status, SalesOrder.Status.CONFIRMED)
        history.note = "tamper"
        with self.assertRaises(Exception):
            history.save()


class SalesOrderDashboardTests(SalesBase):
    def test_sales_pages_render_from_database(self):
        order = self.create_order()
        response = self.client.get(reverse("backoffice:orders"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, order.order_number)
        response = self.client.get(reverse("backoffice:order_detail_id", args=[order.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sales Phone")
        response = self.client.get(reverse("backoffice:order_add") + f"?id={order.pk}")
        self.assertEqual(response.status_code, 200)

    def test_order_form_and_lifecycle_actions_post_real_transactions(self):
        response = self.client.post(reverse("backoffice:order_add"), {
            "order_number": "TB-WEB-001",
            "customer": self.customer.pk,
            "warehouse": self.warehouse.pk,
            "channel": SalesOrder.Channel.ONLINE,
            "status": SalesOrder.Status.PENDING,
            "order_date": "2026-09-07",
            "shipping_name": "",
            "shipping_phone": "",
            "shipping_email": "",
            "shipping_address": "",
            "shipping_city": "",
            "shipping_district": "",
            "shipping_postal_code": "",
            "discount_amount": "0.00",
            "shipping_charge": "0.00",
            "amount_paid": "0.00",
            "notes": "Web order",
            "variant_id": [str(self.variant.pk)],
            "quantity": ["2"],
            "unit_price": ["100.00"],
            "line_discount": ["0.00"],
        })
        self.assertEqual(response.status_code, 302)
        order = SalesOrder.objects.get(order_number="TB-WEB-001")
        self.assertEqual(order.status, SalesOrder.Status.PENDING)
        self.assertEqual(InventoryBalance.objects.get(warehouse=self.warehouse, variant=self.variant).reserved_quantity, 2)

        self.assertEqual(self.client.post(reverse("backoffice:order_confirm", args=[order.pk])).status_code, 302)
        self.assertEqual(self.client.post(reverse("backoffice:order_process", args=[order.pk])).status_code, 302)
        self.assertEqual(self.client.post(reverse("backoffice:order_complete", args=[order.pk])).status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, SalesOrder.Status.COMPLETED)
        balance = InventoryBalance.objects.get(warehouse=self.warehouse, variant=self.variant)
        self.assertEqual(balance.on_hand, 8)
        self.assertEqual(balance.reserved_quantity, 0)

        response = self.client.post(reverse("backoffice:order_payment", args=[order.pk]), {"amount_paid": "200.00", "note": "Paid"})
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, SalesOrder.PaymentStatus.PAID)
        self.assertEqual(self.customer.order_count, 1)

    def test_cancel_action_releases_stock(self):
        order = self.create_order(quantity=2)
        response = self.client.post(reverse("backoffice:order_cancel", args=[order.pk]), {"note": "Customer cancelled"})
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        balance = InventoryBalance.objects.get(warehouse=self.warehouse, variant=self.variant)
        self.assertEqual(order.status, SalesOrder.Status.CANCELLED)
        self.assertEqual(balance.reserved_quantity, 0)
        self.assertEqual(balance.on_hand, 10)
