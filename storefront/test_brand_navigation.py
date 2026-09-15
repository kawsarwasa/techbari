from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from catalog.models import Brand, Category, Product


class StorefrontBrandNavigationTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Brand Test Audio", slug="brand-test-audio")
        self.anker = Brand.objects.create(name="Brand Test Anker", slug="brand-test-anker", sort_order=1)
        self.baseus = Brand.objects.create(name="Brand Test Baseus", slug="brand-test-baseus", sort_order=2)
        self.hidden = Brand.objects.create(name="Hidden Brand", slug="hidden-brand", is_active=False)

        self.anker_product = Product.objects.create(
            public_id="brand-anker-product",
            name="Brand Anker Product",
            slug="brand-anker-product",
            category=self.category,
            brand=self.anker,
            regular_price=Decimal("1200.00"),
            status=Product.Status.ACTIVE,
        )
        self.baseus_product = Product.objects.create(
            public_id="brand-baseus-product",
            name="Brand Baseus Product",
            slug="brand-baseus-product",
            category=self.category,
            brand=self.baseus,
            regular_price=Decimal("1400.00"),
            status=Product.Status.ACTIVE,
        )

    def result_ids(self, response):
        return [product["id"] for product in response.context["products"]]

    def test_brand_name_filters_products_server_side(self):
        response = self.client.get(reverse("storefront:products"), {"brand": self.anker.name})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.result_ids(response), [self.anker_product.public_id])
        self.assertEqual(response.context["selected_brand_name"], self.anker.name)
        self.assertContains(response, f"{self.anker.name} Products")

    def test_brand_slug_is_backward_compatible(self):
        response = self.client.get(reverse("storefront:products"), {"brand": self.baseus.slug})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.result_ids(response), [self.baseus_product.public_id])
        self.assertEqual(response.context["selected_brand_name"], self.baseus.name)

    def test_brands_directory_lists_active_brands_only(self):
        response = self.client.get(reverse("storefront:brands"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.anker.name)
        self.assertContains(response, self.baseus.name)
        self.assertNotContains(response, self.hidden.name)
        self.assertContains(response, "Shop by Brand")

    def test_top_brands_are_clickable_and_view_all_opens_brands_directory(self):
        response = self.client.get(reverse("storefront:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("storefront:brands"))
        self.assertContains(response, f"brand={self.anker.name.replace(' ', '+')}")
