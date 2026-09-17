from decimal import Decimal
from urllib.parse import quote

from django.test import TestCase
from django.urls import reverse

from catalog.models import Brand, Category, Product


class StorefrontCategoryDirectoryTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="Category Test Brand", slug="category-test-brand")
        self.audio = Category.objects.create(name="Category Test Audio", slug="category-test-audio", sort_order=1)
        self.chargers = Category.objects.create(name="Category Test Chargers", slug="category-test-chargers", sort_order=2)
        self.hidden = Category.objects.create(name="Hidden Category", slug="hidden-category", is_active=False)

        Product.objects.create(
            public_id="category-audio-product",
            name="Category Audio Product",
            slug="category-audio-product",
            category=self.audio,
            brand=self.brand,
            regular_price=Decimal("1200.00"),
            status=Product.Status.ACTIVE,
        )
        Product.objects.create(
            public_id="category-charger-product",
            name="Category Charger Product",
            slug="category-charger-product",
            category=self.chargers,
            brand=self.brand,
            regular_price=Decimal("900.00"),
            status=Product.Status.ACTIVE,
        )

    def test_home_view_all_categories_opens_categories_directory(self):
        response = self.client.get(reverse("storefront:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("storefront:categories"))
        self.assertContains(response, "View All Categories")

    def test_categories_directory_lists_active_categories_only(self):
        response = self.client.get(reverse("storefront:categories"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Shop by Category")
        self.assertContains(response, self.audio.name)
        self.assertContains(response, self.chargers.name)
        self.assertNotContains(response, self.hidden.name)

    def test_category_directory_card_links_to_filtered_products(self):
        response = self.client.get(reverse("storefront:categories"))
        self.assertContains(response, reverse("storefront:products"))
        self.assertContains(response, f"category={quote(self.audio.name)}")
