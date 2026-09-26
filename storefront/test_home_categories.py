from django.test import TestCase
from django.urls import reverse


class HomepageCategoryShowcaseTests(TestCase):
    def test_homepage_uses_nine_curated_black_product_categories(self):
        response = self.client.get(reverse("storefront:home"))

        self.assertEqual(response.status_code, 200)
        rows = response.context["home_categories"]
        self.assertEqual(len(rows), 9)
        self.assertEqual(
            [row["name"] for row in rows],
            [
                "TWS Earbuds",
                "Over-Ear Headphones",
                "Neckband Earphones",
                "Smartwatches",
                "Bluetooth Speakers",
                "Power Banks",
                "Wall Chargers",
                "Cables",
                "Phone Accessories",
            ],
        )
        for row in rows:
            self.assertIn("/static/store/images/categories/black-", row["image_url"])
            self.assertTrue(row["image_url"].endswith(".svg"))

    def test_homepage_category_cards_keep_product_filter_names(self):
        response = self.client.get(reverse("storefront:home"))
        rows = {row["name"]: row["filter_name"] for row in response.context["home_categories"]}

        self.assertEqual(rows["Over-Ear Headphones"], "Headphones")
        self.assertEqual(rows["Bluetooth Speakers"], "Speakers")
        self.assertEqual(rows["Wall Chargers"], "Chargers")
        self.assertEqual(rows["Neckband Earphones"], "Neckband")
