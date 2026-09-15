from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from catalog.models import Brand, Category, Product


class StorefrontPaginationTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Pagination Accessories",
            slug="pagination-accessories",
            is_active=True,
        )
        self.brand = Brand.objects.create(
            name="Pagination Brand",
            slug="pagination-brand",
            is_active=True,
        )
        for index in range(13):
            Product.objects.create(
                public_id=f"pagination-product-{index:02d}",
                name=f"Pagination Product {index:02d}",
                slug=f"pagination-product-{index:02d}",
                category=self.category,
                brand=self.brand,
                short_description="UniqueSingleNeedle" if index == 0 else "Pagination test product",
                regular_price=Decimal("1000.00") + index,
                status=Product.Status.ACTIVE,
                is_new_arrival=True,
            )

    def test_products_are_paginated_twelve_per_page(self):
        response = self.client.get(reverse("storefront:products"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["paginator"].count, 13)
        self.assertEqual(response.context["paginator"].num_pages, 2)
        self.assertEqual(response.context["page_obj"].number, 1)
        self.assertEqual(len(response.context["products"]), 12)
        self.assertContains(response, 'aria-label="Product pages"')
        self.assertContains(response, "page=2")
        self.assertNotContains(response, ">14<")

    def test_second_page_contains_remaining_product(self):
        response = self.client.get(reverse("storefront:products"), {"page": 2})

        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertEqual(len(response.context["products"]), 1)
        self.assertContains(response, "Showing 13–13 of 13 products")

    def test_single_page_result_hides_pagination(self):
        response = self.client.get(reverse("storefront:products"), {"q": "UniqueSingleNeedle"})

        self.assertEqual(response.context["paginator"].num_pages, 1)
        self.assertEqual(len(response.context["products"]), 1)
        self.assertNotContains(response, 'aria-label="Product pages"')

    def test_out_of_range_page_falls_back_to_last_page(self):
        response = self.client.get(reverse("storefront:products"), {"page": 999})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertEqual(len(response.context["products"]), 1)

    def test_pagination_links_preserve_collection_and_search_query(self):
        response = self.client.get(
            reverse("storefront:products"),
            {"collection": "new-arrivals", "q": "Pagination", "page": 1},
        )
        html = response.content.decode()

        self.assertEqual(response.context["paginator"].num_pages, 2)
        self.assertIn("collection=new-arrivals", html)
        self.assertIn("q=Pagination", html)
        self.assertIn("page=2", html)
