from django.test import TestCase
from django.urls import reverse

from catalog.models import Category


class StorefrontCategoryMenuTests(TestCase):
    def setUp(self):
        self.parent = Category.objects.create(
            name="Audio Gear",
            slug="audio-gear-menu-test",
            is_active=True,
            sort_order=1,
        )
        self.child = Category.objects.create(
            name="TWS Earbuds Menu",
            slug="tws-earbuds-menu-test",
            parent=self.parent,
            is_active=True,
            sort_order=1,
        )
        self.leaf = Category.objects.create(
            name="Power Banks Menu",
            slug="power-banks-menu-test",
            is_active=True,
            sort_order=2,
        )
        Category.objects.create(
            name="Hidden Menu Category",
            slug="hidden-menu-category-test",
            is_active=False,
            sort_order=3,
        )

    def test_home_renders_dynamic_category_dropdown(self):
        response = self.client.get(reverse("storefront:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-category-menu-trigger")
        self.assertContains(response, 'aria-expanded="false"')
        self.assertContains(response, "Audio Gear")
        self.assertContains(response, "TWS Earbuds Menu")
        self.assertContains(response, "Power Banks Menu")
        self.assertNotContains(response, "Hidden Menu Category")

    def test_category_menu_only_shows_submenu_control_for_parent_categories(self):
        response = self.client.get(reverse("storefront:home"))
        html = response.content.decode()
        self.assertEqual(html.count("data-category-submenu-toggle"), 1)
        self.assertIn("Show Audio Gear subcategories", html)
        self.assertNotIn("Show Power Banks Menu subcategories", html)
        self.assertNotIn("category-menu-caret", html)
        self.assertNotIn("category-menu-footer", html)

    def test_category_menu_context_groups_children_under_parent(self):
        response = self.client.get(reverse("storefront:home"))
        menu = response.context["category_menu"]
        parent = next(row for row in menu if row["id"] == self.parent.pk)
        self.assertEqual([row["id"] for row in parent["children"]], [self.child.pk])

    def test_products_page_uses_selected_category_as_heading(self):
        response = self.client.get(reverse("storefront:products"), {"category": self.leaf.name})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_category_name"], self.leaf.name)
        self.assertContains(response, f'<h1 class="page-title">{self.leaf.name}</h1>', html=True)
        self.assertContains(response, f"Explore all {self.leaf.name} products available at TechBari.")
        self.assertNotContains(response, '<h1 class="page-title">All Products</h1>', html=True)

    def test_invalid_category_falls_back_to_all_products_heading(self):
        response = self.client.get(reverse("storefront:products"), {"category": "Not A Real Category"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_category_name"], "")
        self.assertContains(response, '<h1 class="page-title">All Products</h1>', html=True)
