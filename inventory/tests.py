from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from catalog.models import Brand, Category, Product, ProductVariant
from .models import InventoryBalance, StockAdjustment, StockMovement, StockTransfer, Warehouse
from .services import (
    InsufficientStock,
    adjust_stock,
    get_default_warehouse,
    issue_reserved_stock,
    post_movement,
    release_reserved_stock,
    reserve_stock,
    transfer_stock,
)


class InventoryServiceTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Audio", slug="audio")
        self.brand = Brand.objects.create(name="Test Brand", slug="test-brand")
        self.product = Product.objects.create(
            public_id="inventory-test",
            name="Inventory Test Product",
            slug="inventory-test-product",
            category=self.category,
            brand=self.brand,
            regular_price=1000,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            name="Default",
            sku="INV-001",
            stock_quantity=10,
            low_stock_alert=3,
            is_default=True,
            is_active=True,
        )
        self.main = get_default_warehouse()

    def test_new_variant_bootstraps_opening_balance_and_movement(self):
        balance = InventoryBalance.objects.get(warehouse=self.main, variant=self.variant)
        self.assertEqual(balance.on_hand, 10)
        self.assertEqual(balance.reserved_quantity, 0)
        self.assertEqual(balance.available_quantity, 10)
        movement = StockMovement.objects.get(variant=self.variant, movement_type=StockMovement.Type.OPENING)
        self.assertEqual(movement.quantity_delta, 10)
        self.assertEqual(movement.quantity_after, 10)

    def test_purchase_and_sale_movements_update_balance_and_cache(self):
        post_movement(
            warehouse=self.main,
            variant=self.variant,
            movement_type=StockMovement.Type.PURCHASE_IN,
            quantity_delta=5,
            reference_type="purchase",
            reference_no="PO-1",
        )
        post_movement(
            warehouse=self.main,
            variant=self.variant,
            movement_type=StockMovement.Type.SALE_OUT,
            quantity_delta=-4,
            reference_type="order",
            reference_no="ORD-1",
        )
        balance = InventoryBalance.objects.get(warehouse=self.main, variant=self.variant)
        self.variant.refresh_from_db()
        self.assertEqual(balance.on_hand, 11)
        self.assertEqual(self.variant.stock_quantity, 11)

    def test_negative_stock_is_blocked(self):
        with self.assertRaises(InsufficientStock):
            post_movement(
                warehouse=self.main,
                variant=self.variant,
                movement_type=StockMovement.Type.SALE_OUT,
                quantity_delta=-11,
            )
        self.assertEqual(InventoryBalance.objects.get(warehouse=self.main, variant=self.variant).on_hand, 10)

    def test_reserve_release_and_issue_reserved_stock(self):
        reserve_stock(warehouse=self.main, variant=self.variant, quantity=4, reference_no="ORD-R")
        balance = InventoryBalance.objects.get(warehouse=self.main, variant=self.variant)
        self.variant.refresh_from_db()
        self.assertEqual(balance.reserved_quantity, 4)
        self.assertEqual(balance.available_quantity, 6)
        self.assertEqual(self.variant.stock_quantity, 6)

        release_reserved_stock(warehouse=self.main, variant=self.variant, quantity=1, reference_no="ORD-R")
        issue_reserved_stock(warehouse=self.main, variant=self.variant, quantity=3, reference_no="ORD-R")
        balance.refresh_from_db()
        self.variant.refresh_from_db()
        self.assertEqual(balance.on_hand, 7)
        self.assertEqual(balance.reserved_quantity, 0)
        self.assertEqual(self.variant.stock_quantity, 7)

    def test_adjustment_posts_audited_difference(self):
        adjustment = adjust_stock(
            warehouse=self.main,
            variant=self.variant,
            actual_quantity=7,
            reason="Physical count",
            note="Shelf count",
            actor="QA",
        )
        self.assertEqual(adjustment.system_quantity, 10)
        self.assertEqual(adjustment.actual_quantity, 7)
        self.assertEqual(adjustment.difference, -3)
        self.assertTrue(StockAdjustment.objects.filter(pk=adjustment.pk).exists())
        movement = StockMovement.objects.get(reference_no=adjustment.reference_no)
        self.assertEqual(movement.movement_type, StockMovement.Type.ADJUSTMENT_OUT)
        self.assertEqual(movement.quantity_after, 7)

    def test_adjustment_cannot_drop_below_reserved(self):
        reserve_stock(warehouse=self.main, variant=self.variant, quantity=6)
        with self.assertRaises(ValidationError):
            adjust_stock(
                warehouse=self.main,
                variant=self.variant,
                actual_quantity=5,
                reason="Bad count",
            )

    def test_transfer_posts_paired_movements_atomically(self):
        shop = Warehouse.objects.create(name="Shop Floor", code="SHOP", is_active=True)
        transfer = transfer_stock(
            from_warehouse=self.main,
            to_warehouse=shop,
            items=[(self.variant, 4)],
            note="Restock shop",
            actor="QA",
        )
        source = InventoryBalance.objects.get(warehouse=self.main, variant=self.variant)
        destination = InventoryBalance.objects.get(warehouse=shop, variant=self.variant)
        self.variant.refresh_from_db()
        self.assertEqual(source.on_hand, 6)
        self.assertEqual(destination.on_hand, 4)
        self.assertEqual(self.variant.stock_quantity, 10)
        self.assertTrue(StockTransfer.objects.filter(pk=transfer.pk).exists())
        movement_types = set(StockMovement.objects.filter(reference_no=transfer.transfer_no).values_list("movement_type", flat=True))
        self.assertEqual(movement_types, {StockMovement.Type.TRANSFER_OUT, StockMovement.Type.TRANSFER_IN})

    def test_transfer_rejects_reserved_or_unavailable_stock(self):
        shop = Warehouse.objects.create(name="Shop Floor", code="SHOP2", is_active=True)
        reserve_stock(warehouse=self.main, variant=self.variant, quantity=8)
        with self.assertRaises(InsufficientStock):
            transfer_stock(from_warehouse=self.main, to_warehouse=shop, items=[(self.variant, 3)])
        self.assertFalse(StockTransfer.objects.exists())

    def test_catalog_stock_edit_is_reconciled_into_inventory_ledger(self):
        self.variant.stock_quantity = 6
        self.variant.save(update_fields=["stock_quantity", "updated_at"])
        balance = InventoryBalance.objects.get(warehouse=self.main, variant=self.variant)
        self.variant.refresh_from_db()
        self.assertEqual(balance.available_quantity, 6)
        self.assertEqual(self.variant.stock_quantity, 6)
        self.assertTrue(
            StockMovement.objects.filter(reference_type="catalog-compat", quantity_delta=-4).exists()
        )

    def test_movement_is_immutable(self):
        movement = StockMovement.objects.filter(variant=self.variant).first()
        movement.note = "tamper"
        with self.assertRaises(ValidationError):
            movement.save()
        with self.assertRaises(ValidationError):
            movement.delete()

    def test_low_stock_property_uses_available_stock(self):
        balance = InventoryBalance.objects.get(warehouse=self.main, variant=self.variant)
        balance.low_stock_threshold = 4
        balance.save(update_fields=["low_stock_threshold", "updated_at"])
        reserve_stock(warehouse=self.main, variant=self.variant, quantity=6)
        balance.refresh_from_db()
        self.assertTrue(balance.is_low_stock)
        self.assertEqual(balance.available_quantity, 4)


class InventoryDashboardTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Phones", slug="phones")
        brand = Brand.objects.create(name="Phone Brand", slug="phone-brand")
        product = Product.objects.create(
            public_id="phone-test",
            name="Phone Test",
            slug="phone-test",
            category=category,
            brand=brand,
            regular_price=20000,
        )
        self.variant = ProductVariant.objects.create(
            product=product,
            name="128GB",
            sku="PHONE-128",
            stock_quantity=5,
            is_default=True,
            is_active=True,
        )
        self.main = get_default_warehouse()

    def test_inventory_pages_render(self):
        for route in (
            "backoffice:inventory",
            "backoffice:warehouses",
            "backoffice:warehouse_add",
            "backoffice:stock_adjustment",
            "backoffice:stock_transfer",
            "backoffice:inventory_movements",
            "backoffice:inventory_low_stock",
        ):
            response = self.client.get(reverse(route))
            self.assertEqual(response.status_code, 200, route)

    def test_warehouse_form_creates_database_record(self):
        response = self.client.post(
            reverse("backoffice:warehouse_add"),
            {
                "name": "Outlet",
                "code": "out01",
                "address": "Dhaka",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Warehouse.objects.filter(code="OUT01").exists())

    def test_threshold_update(self):
        balance = InventoryBalance.objects.get(warehouse=self.main, variant=self.variant)
        response = self.client.post(
            reverse("backoffice:inventory"),
            {
                "action": "set_threshold",
                "balance_id": balance.pk,
                "low_stock_threshold": 9,
            },
        )
        self.assertEqual(response.status_code, 302)
        balance.refresh_from_db()
        self.assertEqual(balance.low_stock_threshold, 9)

    def test_adjustment_view_posts_stock(self):
        response = self.client.post(
            reverse("backoffice:stock_adjustment"),
            {
                "warehouse": self.main.pk,
                "variant": self.variant.pk,
                "actual_quantity": 8,
                "reason": "Count correction",
                "note": "QA",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(InventoryBalance.objects.get(warehouse=self.main, variant=self.variant).on_hand, 8)

    def test_transfer_view_posts_multiple_rows(self):
        outlet = Warehouse.objects.create(name="Outlet Two", code="OUT02", is_active=True)
        post = {
            "from_warehouse": self.main.pk,
            "to_warehouse": outlet.pk,
            "note": "Move units",
            "items-TOTAL_FORMS": "5",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-variant": self.variant.pk,
            "items-0-quantity": "2",
        }
        for index in range(1, 5):
            post[f"items-{index}-variant"] = ""
            post[f"items-{index}-quantity"] = ""
        response = self.client.post(reverse("backoffice:stock_transfer"), post)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(InventoryBalance.objects.get(warehouse=outlet, variant=self.variant).on_hand, 2)
