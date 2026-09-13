from django.test import RequestFactory, TestCase

from backoffice import variant_views
from catalog.models import (
    Brand,
    Category,
    Product,
    ProductVariant,
    ProductVariantValue,
    VariantAttribute,
    VariantAttributeValue,
)
from catalog.variant_forms import StructuredProductVariantForm
from catalog.variant_services import generate_variant_combinations
from inventory.models import Warehouse


class StructuredVariantTests(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(
            name="Main Warehouse",
            code="MAIN-TEST",
            is_default=True,
            is_active=True,
        )
        self.category = Category.objects.create(name="Phones", slug="phones")
        self.brand = Brand.objects.create(name="Demo Brand", slug="demo-brand")
        self.product = Product.objects.create(
            public_id="demo-phone",
            name="Demo Phone",
            slug="demo-phone",
            category=self.category,
            brand=self.brand,
            regular_price="1000.00",
            sale_price="900.00",
        )
        self.color = VariantAttribute.objects.create(
            name="Color",
            code="color",
            display_type=VariantAttribute.DisplayType.SWATCH,
            sort_order=0,
        )
        self.storage = VariantAttribute.objects.create(
            name="Storage",
            code="storage",
            display_type=VariantAttribute.DisplayType.BUTTON,
            sort_order=1,
        )
        self.black = VariantAttributeValue.objects.create(
            attribute=self.color,
            value="Black",
            code="black",
            symbol="⚫",
        )
        self.blue = VariantAttributeValue.objects.create(
            attribute=self.color,
            value="Blue",
            code="blue",
            symbol="🔵",
            sort_order=1,
        )
        self.gb128 = VariantAttributeValue.objects.create(
            attribute=self.storage,
            value="128GB",
            code="128gb",
        )
        self.gb256 = VariantAttributeValue.objects.create(
            attribute=self.storage,
            value="256GB",
            code="256gb",
            sort_order=1,
        )
        # Establish the product's structured attribute set with one existing SKU.
        self.seed_variant = ProductVariant.objects.create(
            product=self.product,
            name="Blue / 256GB",
            sku="DEMO-BLUE-256",
            stock_quantity=0,
            is_default=True,
            is_active=True,
        )
        ProductVariantValue.objects.create(variant=self.seed_variant, value=self.blue)
        ProductVariantValue.objects.create(variant=self.seed_variant, value=self.gb256)

    def _form(self, *, sku, color=None, storage=None, is_default=False):
        selected = [color or self.black, storage or self.gb128]
        return StructuredProductVariantForm(
            data={
                "product": str(self.product.pk),
                "name": "",
                "sku": sku,
                "barcode": "",
                "symbol": "",
                "regular_price_override": "",
                "price_override": "",
                "stock_quantity": "0",
                "low_stock_alert": "5",
                "is_default": "on" if is_default else "",
                "is_active": "on",
                "attribute_values": [str(value.pk) for value in selected],
            },
            product_id=self.product.pk,
        )

    def test_structured_form_generates_stable_combination_name(self):
        form = self._form(sku="DEMO-BLK-128")
        self.assertTrue(form.is_valid(), form.errors.as_json())
        variant = form.save()

        self.assertEqual(variant.name, "Black / 128GB")
        self.assertEqual(variant.display_name, "Black / 128GB")
        self.assertEqual(variant.symbol, "⚫")
        self.assertEqual(variant.variant_values.count(), 2)

    def test_structured_form_rejects_duplicate_combination(self):
        first = self._form(sku="DEMO-BLK-128-A")
        self.assertTrue(first.is_valid(), first.errors.as_json())
        first.save()

        duplicate = self._form(sku="DEMO-BLK-128-B")
        self.assertFalse(duplicate.is_valid())
        self.assertIn("attribute_values", duplicate.errors)

    def test_structured_form_requires_one_value_per_product_attribute(self):
        form = StructuredProductVariantForm(
            data={
                "product": str(self.product.pk),
                "name": "",
                "sku": "DEMO-INCOMPLETE",
                "stock_quantity": "0",
                "low_stock_alert": "5",
                "is_active": "on",
                "attribute_values": [str(self.black.pk)],
            },
            product_id=self.product.pk,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("attribute_values", form.errors)
        self.assertIn("Storage", str(form.errors["attribute_values"]))

    def test_global_value_rename_keeps_variant_identity(self):
        variant_id = self.seed_variant.pk
        sku = self.seed_variant.sku
        self.blue.value = "Deep Blue"
        self.blue.save(update_fields=["value", "updated_at"])
        self.seed_variant.refresh_from_db()
        self.assertEqual(self.seed_variant.pk, variant_id)
        self.assertEqual(self.seed_variant.sku, sku)
        self.assertEqual(self.seed_variant.display_name, "Deep Blue / 256GB")


class VariantGenerationTests(TestCase):
    def setUp(self):
        Warehouse.objects.create(name="Builder Warehouse", code="BUILD-WH", is_default=True, is_active=True)
        category = Category.objects.create(name="Builder Phones", slug="builder-phones")
        brand = Brand.objects.create(name="Builder Brand", slug="builder-brand")
        self.product = Product.objects.create(
            public_id="builder-phone",
            name="Builder Phone",
            slug="builder-phone",
            category=category,
            brand=brand,
            regular_price="2000.00",
        )
        color = VariantAttribute.objects.create(name="Builder Color", code="builder-color", sort_order=0)
        storage = VariantAttribute.objects.create(name="Builder Storage", code="builder-storage", sort_order=1)
        region = VariantAttribute.objects.create(name="Builder Region", code="builder-region", sort_order=2)
        self.values = [
            VariantAttributeValue.objects.create(attribute=color, value="Black", code="black", sort_order=0),
            VariantAttributeValue.objects.create(attribute=color, value="Silver", code="silver", sort_order=1),
            VariantAttributeValue.objects.create(attribute=storage, value="128GB", code="128gb", sort_order=0),
            VariantAttributeValue.objects.create(attribute=storage, value="256GB", code="256gb", sort_order=1),
            VariantAttributeValue.objects.create(attribute=region, value="USA", code="usa", sort_order=0),
            VariantAttributeValue.objects.create(attribute=region, value="Japan", code="japan", sort_order=1),
        ]

    def test_generator_creates_cartesian_product_without_duplicates(self):
        result = generate_variant_combinations(
            product=self.product,
            value_ids=[value.pk for value in self.values],
        )
        self.assertEqual(result["total_requested"], 8)
        self.assertEqual(result["created"], 8)
        self.assertEqual(self.product.variants.count(), 8)
        self.assertEqual(self.product.variants.filter(is_default=True, is_active=True).count(), 1)
        self.assertTrue(all(variant.variant_values.count() == 3 for variant in self.product.variants.all()))

        again = generate_variant_combinations(
            product=self.product,
            value_ids=[value.pk for value in self.values],
        )
        self.assertEqual(again["created"], 0)
        self.assertEqual(again["skipped"], 8)
        self.assertEqual(self.product.variants.count(), 8)


class VariantDeletionSafetyTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.warehouse = Warehouse.objects.create(
            name="Safety Warehouse",
            code="SAFE-WH",
            is_default=True,
            is_active=True,
        )
        category = Category.objects.create(name="Accessories", slug="accessories")
        brand = Brand.objects.create(name="Safety Brand", slug="safety-brand")
        self.product = Product.objects.create(
            public_id="safe-item",
            name="Safe Item",
            slug="safe-item",
            category=category,
            brand=brand,
            regular_price="100.00",
        )
        self.used_variant = ProductVariant.objects.create(
            product=self.product,
            name="Black",
            sku="SAFE-BLACK",
            stock_quantity=5,
            is_default=True,
            is_active=True,
        )
        self.other_variant = ProductVariant.objects.create(
            product=self.product,
            name="Blue",
            sku="SAFE-BLUE",
            stock_quantity=0,
            is_default=False,
            is_active=True,
        )

    def test_business_linked_variant_is_deactivated_not_deleted(self):
        request = self.factory.post(
            "/dashboard/variants/",
            {"action": "delete", "variant_id": str(self.used_variant.pk)},
        )
        response = variant_views.variants(request)

        self.assertEqual(response.status_code, 302)
        self.used_variant.refresh_from_db()
        self.other_variant.refresh_from_db()
        self.assertFalse(self.used_variant.is_active)
        self.assertFalse(self.used_variant.is_default)
        self.assertTrue(self.other_variant.is_active)
        self.assertTrue(self.other_variant.is_default)

    def test_last_active_variant_cannot_be_deactivated(self):
        self.other_variant.is_active = False
        self.other_variant.save(update_fields=["is_active", "updated_at"])

        request = self.factory.post(
            "/dashboard/variants/",
            {"action": "delete", "variant_id": str(self.used_variant.pk)},
        )
        response = variant_views.variants(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn("error=last-active-variant", response.url)
        self.used_variant.refresh_from_db()
        self.assertTrue(self.used_variant.is_active)
