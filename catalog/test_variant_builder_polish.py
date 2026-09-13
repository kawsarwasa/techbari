from django.test import RequestFactory, TestCase

from backoffice import variant_builder_views
from catalog.models import Brand, Category, Product, ProductVariant, VariantAttribute, VariantAttributeValue
from catalog.variant_services import VariantGenerationError, generate_variant_combinations
from inventory.models import Warehouse


class VariantBuilderPreviewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        Warehouse.objects.create(
            name="Variant Builder Warehouse",
            code="VB-WH",
            is_default=True,
            is_active=True,
        )
        category = Category.objects.create(name="Builder Test Phones", slug="builder-test-phones")
        brand = Brand.objects.create(name="Builder Test Brand", slug="builder-test-brand")
        self.product = Product.objects.create(
            public_id="preview-phone",
            name="Preview Phone",
            slug="preview-phone",
            category=category,
            brand=brand,
            regular_price="1000.00",
            sale_price="900.00",
        )
        self.color = VariantAttribute.objects.create(name="Preview Color", code="preview-color", sort_order=0)
        self.storage = VariantAttribute.objects.create(name="Preview Storage", code="preview-storage", sort_order=1)
        self.black = VariantAttributeValue.objects.create(attribute=self.color, value="Black", code="black")
        self.blue = VariantAttributeValue.objects.create(attribute=self.color, value="Blue", code="blue", sort_order=1)
        self.gb128 = VariantAttributeValue.objects.create(attribute=self.storage, value="128GB", code="128gb")
        self.gb256 = VariantAttributeValue.objects.create(attribute=self.storage, value="256GB", code="256gb", sort_order=1)
        self.all_value_ids = [self.black.pk, self.blue.pk, self.gb128.pk, self.gb256.pk]

    def test_selected_preview_rows_do_not_create_unapproved_cartesian_combinations(self):
        selected = [
            f"{self.black.pk},{self.gb128.pk}",
            f"{self.blue.pk},{self.gb256.pk}",
        ]
        result = generate_variant_combinations(
            product=self.product,
            value_ids=self.all_value_ids,
            selected_signatures=selected,
        )

        self.assertEqual(result["total_requested"], 2)
        self.assertEqual(result["created"], 2)
        self.assertEqual(self.product.variants.count(), 2)
        self.assertTrue(self.product.variants.filter(name="Black / 128GB").exists())
        self.assertTrue(self.product.variants.filter(name="Blue / 256GB").exists())
        self.assertFalse(self.product.variants.filter(name="Black / 256GB").exists())
        self.assertFalse(self.product.variants.filter(name="Blue / 128GB").exists())

    def test_builder_view_passes_only_confirmed_preview_rows(self):
        request = self.factory.post(
            "/dashboard/variants/builder/",
            {
                "action": "generate",
                "product": str(self.product.pk),
                "value_ids": [str(value_id) for value_id in self.all_value_ids],
                "selected_signatures": [f"{self.black.pk},{self.gb256.pk}"],
            },
        )
        response = variant_builder_views.variant_builder(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.product.variants.count(), 1)
        self.assertTrue(self.product.variants.filter(name="Black / 256GB").exists())

    def test_invalid_preview_signature_is_rejected(self):
        with self.assertRaises(VariantGenerationError):
            generate_variant_combinations(
                product=self.product,
                value_ids=self.all_value_ids,
                selected_signatures=[f"{self.black.pk},{self.blue.pk}"],
            )

    def test_bulk_selling_price_uses_product_regular_price_when_override_is_blank(self):
        variant = ProductVariant.objects.create(
            product=self.product,
            name="Default",
            sku="PREVIEW-DEFAULT",
            stock_quantity=0,
            low_stock_alert=5,
            is_default=True,
            is_active=True,
        )
        request = self.factory.post(
            "/dashboard/variants/builder/",
            {
                "action": "bulk_save",
                "product": str(self.product.pk),
                "variant_ids": [str(variant.pk)],
                f"regular_{variant.pk}": "",
                f"price_{variant.pk}": "1200.00",
                f"stock_{variant.pk}": "0",
                f"low_{variant.pk}": "5",
                f"active_{variant.pk}": "on",
                "default_variant_id": str(variant.pk),
            },
        )

        with self.assertRaisesRegex(ValueError, "effective regular price"):
            variant_builder_views._bulk_save_variants(request, self.product)
