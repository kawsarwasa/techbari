from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from catalog.models import Brand, Category, Product, ProductVariant


class StorefrontScopedCatalogTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Scoped Catalog",
            slug="scoped-catalog",
            is_active=True,
        )
        self.brand = Brand.objects.create(
            name="Scoped Brand",
            slug="scoped-brand",
            is_active=True,
        )
        self.products = []
        for index in range(14):
            product = Product.objects.create(
                public_id=f"scoped-product-{index:02d}",
                name=f"Scoped Product {index:02d}",
                slug=f"scoped-product-{index:02d}",
                category=self.category,
                brand=self.brand,
                regular_price=Decimal("1000.00") + index,
                status=Product.Status.ACTIVE,
            )
            ProductVariant.objects.create(
                product=product,
                name="Default",
                sku=f"SCOPED-{index:02d}",
                stock_quantity=10,
                is_default=True,
                is_active=True,
            )
            self.products.append(product)

    def test_contact_page_does_not_serialize_catalog_products(self):
        with patch("storefront.context.serialize_product") as serializer:
            response = self.client.get(reverse("storefront:contact"))
        self.assertEqual(response.status_code, 200)
        serializer.assert_not_called()
        self.assertEqual(response.context["catalog"], [])
        self.assertEqual(response.context["store_data"]["products"], [])

    def test_products_page_serializes_only_current_page(self):
        response = self.client.get(reverse("storefront:products"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["paginator"].count, 14)
        self.assertEqual(len(response.context["products"]), 12)
        self.assertEqual(len(response.context["store_data"]["products"]), 12)

    def test_cart_initial_payload_is_limited_to_recommendations(self):
        response = self.client.get(reverse("storefront:cart"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["catalog"]), 6)
        self.assertEqual(len(response.context["store_data"]["products"]), 6)

    def test_product_bootstrap_returns_only_requested_ids(self):
        wanted = self.products[3]
        other = self.products[4]
        response = self.client.get(
            reverse("storefront:product_bootstrap"),
            {"ids": f"{wanted.public_id},missing-product"},
        )
        self.assertEqual(response.status_code, 200)
        rows = response.json()["products"]
        self.assertEqual([row["id"] for row in rows], [wanted.public_id])
        self.assertNotIn(other.public_id, [row["id"] for row in rows])

    def test_product_detail_scopes_catalog_to_current_and_four_related(self):
        response = self.client.get(
            reverse("storefront:product_detail", args=[self.products[0].slug])
        )
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(response.context["catalog"]), 5)
        self.assertEqual(response.context["product"]["id"], self.products[0].public_id)
