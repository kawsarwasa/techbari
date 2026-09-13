from django.test import RequestFactory, TestCase

from backoffice import variant_views
from catalog.models import (
    Brand,
    Category,
    Product,
    ProductOption,
    ProductOptionValue,
    ProductVariant,
)
from catalog.variant_forms import StructuredProductVariantForm
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
        self.color = ProductOption.objects.create(product=self.product, name="Color", sort_order=0)
        self.storage = ProductOption.objects.create(product=self.product, name="Storage", sort_order=1)
        self.black = ProductOptionValue.objects.create(option=self.color, value="Black", symbol="⚫")
        self.blue = ProductOptionValue.objects.create(option=self.color, value="Blue", symbol="🔵", sort_order=1)
        self.gb128 = ProductOptionValue.objects.create(option=self.storage, value="128GB")
        self.gb256 = ProductOptionValue.objects.create(option=self.storage, value="256GB", sort_order=1)

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
                "option_values": [str(value.pk) for value in selected],
            },
            product_id=self.product.pk,
        )

    def test_structured_form_generates_stable_combination_name(self):
        form = self._form(sku="DEMO-BLK-128", is_default=True)
        self.assertTrue(form.is_valid(), form.errors.as_json())
        variant = form.save()

        self.assertEqual(variant.name, "Black / 128GB")
        self.assertEqual(variant.display_name, "Black / 128GB")
        self.assertEqual(variant.symbol, "⚫")
        self.assertEqual(variant.option_selections.count(), 2)

    def test_structured_form_rejects_duplicate_combination(self):
        first = self._form(sku="DEMO-BLK-128-A", is_default=True)
        self.assertTrue(first.is_valid(), first.errors.as_json())
        first.save()

        duplicate = self._form(sku="DEMO-BLK-128-B")
        self.assertFalse(duplicate.is_valid())
        self.assertIn("option_values", duplicate.errors)

    def test_structured_form_requires_one_value_per_option(self):
        form = StructuredProductVariantForm(
            data={
                "product": str(self.product.pk),
                "name": "",
                "sku": "DEMO-INCOMPLETE",
                "stock_quantity": "0",
                "low_stock_alert": "5",
                "is_active": "on",
                "option_values": [str(self.black.pk)],
            },
            product_id=self.product.pk,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("option_values", form.errors)
        self.assertIn("Storage", str(form.errors["option_values"]))


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
