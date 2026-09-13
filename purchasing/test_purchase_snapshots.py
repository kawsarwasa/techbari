from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from catalog.models import (
    Brand,
    Category,
    Product,
    ProductOption,
    ProductOptionValue,
    ProductVariant,
    ProductVariantOptionValue,
)
from inventory.models import Warehouse
from purchasing.models import PurchaseOrder, PurchaseOrderItem, Supplier


class PurchaseItemSnapshotTests(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(
            name="Purchase Warehouse",
            code="PUR-WH",
            is_default=True,
            is_active=True,
        )
        category = Category.objects.create(name="Phones", slug="purchase-phones")
        brand = Brand.objects.create(name="Snapshot Brand", slug="snapshot-brand")
        self.product = Product.objects.create(
            public_id="snapshot-phone",
            name="Snapshot Phone",
            slug="snapshot-phone",
            category=category,
            brand=brand,
            regular_price=Decimal("1000.00"),
        )
        color = ProductOption.objects.create(product=self.product, name="Color", sort_order=0)
        storage = ProductOption.objects.create(product=self.product, name="Storage", sort_order=1)
        self.black = ProductOptionValue.objects.create(option=color, value="Black")
        self.gb256 = ProductOptionValue.objects.create(option=storage, value="256GB")
        self.variant = ProductVariant.objects.create(
            product=self.product,
            name="Black / 256GB",
            sku="SNAP-BLK-256",
            stock_quantity=0,
            is_default=True,
            is_active=True,
        )
        ProductVariantOptionValue.objects.create(variant=self.variant, option=color, value=self.black)
        ProductVariantOptionValue.objects.create(variant=self.variant, option=storage, value=self.gb256)
        self.supplier = Supplier.objects.create(code="SUP-SNAPSHOT", name="Snapshot Supplier")
        self.purchase = PurchaseOrder.objects.create(
            po_number="PO-SNAPSHOT-001",
            supplier=self.supplier,
            warehouse=self.warehouse,
            status=PurchaseOrder.Status.ORDERED,
            purchase_date=timezone.localdate(),
        )

    def test_purchase_item_keeps_original_product_variant_and_sku_snapshots(self):
        item = PurchaseOrderItem.objects.create(
            purchase=self.purchase,
            variant=self.variant,
            ordered_quantity=2,
            unit_cost=Decimal("700.00"),
        )
        self.assertEqual(item.product_snapshot, "Snapshot Phone")
        self.assertEqual(item.variant_snapshot, "Black / 256GB")
        self.assertEqual(item.sku_snapshot, "SNAP-BLK-256")

        self.product.name = "Renamed Phone"
        self.product.save(update_fields=["name", "updated_at"])
        self.black.value = "Midnight"
        self.black.save(update_fields=["value", "updated_at"])
        self.variant.sku = "SNAP-MID-256"
        self.variant.name = "Midnight / 256GB"
        self.variant.save(update_fields=["sku", "name", "updated_at"])

        item.refresh_from_db()
        self.assertEqual(item.product_snapshot, "Snapshot Phone")
        self.assertEqual(item.variant_snapshot, "Black / 256GB")
        self.assertEqual(item.sku_snapshot, "SNAP-BLK-256")
        self.assertEqual(item.line_total, Decimal("1400.00"))
