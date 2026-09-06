from decimal import Decimal

from django.test import TestCase

from .forms import ProductForm
from .models import Brand, Category, Product, ProductVariant
from .presentation import serialize_product


class CatalogModelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Earbuds", slug="earbuds")
        self.brand = Brand.objects.create(name="Tech Brand", slug="tech-brand")

    def test_product_form_creates_default_variant(self):
        form = ProductForm(data={"name": "Test Earbuds", "slug": "test-earbuds", "category": self.category.pk, "brand": self.brand.pk, "short_name": "Test Earbuds", "subtitle": "Demo", "short_description": "Short", "description": "Description", "regular_price": "2000", "sale_price": "1800", "weight": "0.250", "shipping_class": "standard", "warranty": "1 year", "status": Product.Status.ACTIVE, "is_featured": "on", "meta_title": "Test Earbuds", "meta_description": "Test", "sku": "TB-TEST-001", "stock_quantity": "12", "low_stock_alert": "3", "variant_names": ["Black", "White"]})
        self.assertTrue(form.is_valid(), form.errors)
        product = form.save()
        self.assertEqual(product.public_id, "test-earbuds")
        self.assertEqual(product.current_price, Decimal("1800"))
        self.assertEqual(product.variants.count(), 2)
        default = product.variants.get(is_default=True)
        self.assertEqual(default.sku, "TB-TEST-001")
        self.assertEqual(default.stock_quantity, 12)

    def test_storefront_serializer_uses_stable_public_id(self):
        product = Product.objects.create(public_id="stable-id", name="Stable Product", slug="stable-product", category=self.category, brand=self.brand, regular_price=Decimal("1000"), status=Product.Status.ACTIVE)
        ProductVariant.objects.create(product=product, name="Default", sku="TB-STABLE-001", stock_quantity=7, is_default=True)
        data = serialize_product(product)
        self.assertEqual(data["id"], "stable-id")
        self.assertEqual(data["stock"], 7)
        self.assertEqual(data["sku"], "TB-STABLE-001")
