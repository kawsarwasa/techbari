from decimal import Decimal

from django.test import TestCase

from .forms import ProductForm, ProductSpecificationForm, ProductVariantForm
from .models import Brand, Category, Product, ProductSpecification, ProductVariant
from .presentation import serialize_product


class CatalogModelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Earbuds", slug="earbuds")
        self.brand = Brand.objects.create(name="Tech Brand", slug="tech-brand")

    def product_form_data(self, **overrides):
        data = {"name": "Test Earbuds", "slug": "test-earbuds", "category": self.category.pk, "brand": self.brand.pk, "short_name": "Test Earbuds", "subtitle": "Demo", "short_description": "Short", "description": "Description", "regular_price": "2000", "sale_price": "1800", "weight": "0.250", "shipping_class": "standard", "warranty": "1 year", "status": Product.Status.ACTIVE, "is_featured": "on", "meta_title": "Test Earbuds", "meta_description": "Test", "sku": "TB-TEST-001", "barcode": "1234567890123", "stock_quantity": "12", "low_stock_alert": "3"}
        data.update(overrides)
        return data

    def test_product_form_creates_default_variant_without_destroying_future_variants(self):
        form = ProductForm(data=self.product_form_data())
        self.assertTrue(form.is_valid(), form.errors)
        product = form.save()
        self.assertEqual(product.public_id, "test-earbuds")
        self.assertEqual(product.current_price, Decimal("1800"))
        self.assertEqual(product.variants.count(), 1)
        default = product.variants.get(is_default=True)
        self.assertEqual(default.sku, "TB-TEST-001")
        self.assertEqual(default.barcode, "1234567890123")
        self.assertEqual(default.stock_quantity, 12)
        extra = ProductVariant.objects.create(product=product, name="Black", sku="TB-TEST-BLK", barcode="1234567890124", stock_quantity=4)
        edit = ProductForm(data=self.product_form_data(name="Test Earbuds Updated"), instance=product)
        self.assertTrue(edit.is_valid(), edit.errors)
        edit.save()
        self.assertTrue(ProductVariant.objects.filter(pk=extra.pk).exists())

    def test_variant_form_rejects_duplicate_barcode(self):
        product = Product.objects.create(public_id="stable-id", name="Stable Product", slug="stable-product", category=self.category, brand=self.brand, regular_price=Decimal("1000"), status=Product.Status.ACTIVE)
        ProductVariant.objects.create(product=product, name="Default", sku="TB-STABLE-001", barcode="111", stock_quantity=7, is_default=True)
        form = ProductVariantForm(data={"product": product.pk, "name": "Black", "sku": "TB-STABLE-BLK", "barcode": "111", "symbol": "", "regular_price_override": "", "price_override": "", "stock_quantity": "1", "low_stock_alert": "1", "is_active": "on"})
        self.assertFalse(form.is_valid())
        self.assertIn("barcode", form.errors)

    def test_specification_form_rejects_duplicate_name_case_insensitive(self):
        product = Product.objects.create(public_id="spec-product", name="Spec Product", slug="spec-product", category=self.category, brand=self.brand, regular_price=Decimal("1000"), status=Product.Status.ACTIVE)
        ProductSpecification.objects.create(product=product, name="Bluetooth", value="5.3")
        form = ProductSpecificationForm(data={"product": product.pk, "name": "bluetooth", "value": "5.4", "sort_order": "0"})
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_storefront_serializer_includes_default_barcode(self):
        product = Product.objects.create(public_id="serializable", name="Serializable Product", slug="serializable-product", category=self.category, brand=self.brand, regular_price=Decimal("1000"), status=Product.Status.ACTIVE)
        ProductVariant.objects.create(product=product, name="Default", sku="TB-SERIAL-001", barcode="987654321", stock_quantity=7, is_default=True)
        data = serialize_product(product)
        self.assertEqual(data["id"], "serializable")
        self.assertEqual(data["stock"], 7)
        self.assertEqual(data["sku"], "TB-SERIAL-001")
        self.assertEqual(data["barcode"], "987654321")
