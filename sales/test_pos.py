from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from catalog.models import Brand, Category, Product, ProductVariant
from inventory.models import InventoryBalance, Warehouse

from .models import SalesOrder
from .pos_services import POSError, complete_pos_sale, hold_pos_order


class POSSystemTests(TestCase):
    def setUp(self):
        Warehouse.objects.filter(is_default=True).update(is_default=False)
        self.warehouse = Warehouse.objects.create(name="POS Shop", code="POS-SHOP", is_active=True, is_default=True)
        self.category = Category.objects.create(name="POS Audio", slug="pos-audio")
        self.brand = Brand.objects.create(name="POS Brand", slug="pos-brand")
        self.product = Product.objects.create(
            public_id="pos-product",
            name="POS Product",
            slug="pos-product",
            category=self.category,
            brand=self.brand,
            regular_price=Decimal("100.00"),
            status=Product.Status.ACTIVE,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            name="Black",
            sku="POS-BLK",
            barcode="123456789",
            stock_quantity=5,
            is_default=True,
            is_active=True,
        )

    def items(self, quantity=2):
        return [{"variant_id": self.variant.pk, "qty": quantity}]

    def test_hold_uses_draft_pos_order_without_reserving_stock(self):
        order = hold_pos_order(warehouse_id=self.warehouse.pk, items=self.items(), discount_amount="10")
        balance = InventoryBalance.objects.get(warehouse=self.warehouse, variant=self.variant)
        self.assertEqual(order.channel, SalesOrder.Channel.POS)
        self.assertEqual(order.status, SalesOrder.Status.DRAFT)
        self.assertEqual(order.grand_total, Decimal("190.00"))
        self.assertEqual(balance.reserved_quantity, 0)
        self.assertEqual(balance.on_hand, 5)

    def test_cash_pos_sale_completes_and_issues_inventory(self):
        order = complete_pos_sale(
            warehouse_id=self.warehouse.pk,
            items=self.items(),
            payment_method="cash",
            tendered_amount="250",
        )
        balance = InventoryBalance.objects.get(warehouse=self.warehouse, variant=self.variant)
        self.assertEqual(order.status, SalesOrder.Status.COMPLETED)
        self.assertEqual(order.payment_status, SalesOrder.PaymentStatus.PAID)
        self.assertEqual(order.payment_method, SalesOrder.PaymentMethod.CASH)
        self.assertEqual(order.amount_paid, Decimal("200.00"))
        self.assertEqual(order.change_amount, Decimal("50.00"))
        self.assertEqual(balance.on_hand, 3)
        self.assertEqual(balance.reserved_quantity, 0)
        self.assertEqual(order.items.get().issued_quantity, 2)

    def test_held_order_can_resume_into_completed_sale(self):
        held = hold_pos_order(warehouse_id=self.warehouse.pk, items=self.items(1))
        order = complete_pos_sale(
            warehouse_id=self.warehouse.pk,
            items=self.items(1),
            order_id=held.pk,
            payment_method="bkash",
            payment_reference="TXN-123",
            tendered_amount="100",
        )
        self.assertEqual(order.pk, held.pk)
        self.assertEqual(order.status, SalesOrder.Status.COMPLETED)
        self.assertEqual(order.payment_reference, "TXN-123")

    def test_pos_blocks_oversell_and_missing_non_cash_reference(self):
        with self.assertRaises(POSError):
            complete_pos_sale(warehouse_id=self.warehouse.pk, items=self.items(6), payment_method="cash", tendered_amount="600")
        with self.assertRaises(POSError):
            complete_pos_sale(warehouse_id=self.warehouse.pk, items=self.items(1), payment_method="card", tendered_amount="100")
        self.assertFalse(SalesOrder.objects.filter(channel=SalesOrder.Channel.POS).exists())

    def test_real_pos_dashboard_and_receipt_routes(self):
        response = self.client.get(reverse("backoffice:pos"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-pos-real="1"')
        self.assertContains(response, "POS-BLK")
        order = complete_pos_sale(warehouse_id=self.warehouse.pk, items=self.items(1), payment_method="cash", tendered_amount="100")
        receipt = self.client.get(reverse("backoffice:pos_receipt", args=[order.pk]))
        self.assertEqual(receipt.status_code, 200)
        self.assertContains(receipt, order.order_number)
