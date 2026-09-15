from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from catalog.models import Brand, Category, Product, ProductSpecification, ProductVariant


class StorefrontSearchTests(TestCase):
    def setUp(self):
        self.chargers = Category.objects.create(name="Search Chargers", slug="search-chargers")
        self.earbuds = Category.objects.create(name="Search Earbuds", slug="search-earbuds")
        self.power_banks = Category.objects.create(name="Search Power Banks", slug="search-power-banks")

        self.anker = Brand.objects.create(name="Search Anker", slug="search-anker")
        self.soundcore = Brand.objects.create(name="Search Soundcore", slug="search-soundcore")
        self.baseus = Brand.objects.create(name="Search Baseus", slug="search-baseus")

        self.charger = Product.objects.create(
            public_id="search-anker-nano",
            name="Anker Nano Charger 30W",
            slug="search-anker-nano",
            category=self.chargers,
            brand=self.anker,
            short_name="Nano 30W",
            subtitle="Compact GaN USB-C charger",
            short_description="Fast charging adapter for phones and tablets.",
            description="Compact GaN charger with USB-C Power Delivery.",
            regular_price=Decimal("2490.00"),
            status=Product.Status.ACTIVE,
        )
        ProductVariant.objects.create(
            product=self.charger,
            name="White",
            sku="ANKER-NANO-30W-WHT",
            barcode="123456789001",
            stock_quantity=5,
            is_default=True,
            is_active=True,
        )
        ProductSpecification.objects.create(product=self.charger, name="Output", value="30W USB-C PD")

        self.earbud = Product.objects.create(
            public_id="search-r50i",
            name="Soundcore R50i TWS Earbuds",
            slug="search-r50i",
            category=self.earbuds,
            brand=self.soundcore,
            subtitle="Bluetooth true wireless earbuds",
            short_description="Long battery life with clear calls.",
            description="IPX5 water resistant earbuds with Bluetooth audio and gaming mode.",
            regular_price=Decimal("2190.00"),
            status=Product.Status.ACTIVE,
        )
        ProductVariant.objects.create(
            product=self.earbud,
            name="Black",
            sku="R50I-BLK",
            barcode="123456789002",
            stock_quantity=7,
            is_default=True,
            is_active=True,
        )
        ProductSpecification.objects.create(product=self.earbud, name="Water Resistance", value="IPX5")

        self.power_bank = Product.objects.create(
            public_id="search-baseus-powerbank",
            name="Baseus 20000mAh Power Bank",
            slug="search-baseus-powerbank",
            category=self.power_banks,
            brand=self.baseus,
            short_description="22.5W fast-charge portable battery.",
            description="Digital display power bank for travel and daily charging.",
            regular_price=Decimal("3590.00"),
            status=Product.Status.ACTIVE,
        )
        ProductVariant.objects.create(
            product=self.power_bank,
            name="Black",
            sku="BASEUS-PB-20000",
            stock_quantity=4,
            is_default=True,
            is_active=True,
        )

        self.draft = Product.objects.create(
            public_id="search-hidden-product",
            name="Hidden Search Anker Prototype",
            slug="search-hidden-product",
            category=self.chargers,
            brand=self.anker,
            description="IPX5 internal prototype",
            regular_price=Decimal("999.00"),
            status=Product.Status.DRAFT,
        )

    def search(self, query):
        return self.client.get(reverse("storefront:products"), {"q": query})

    def result_ids(self, response):
        return [product["id"] for product in response.context["products"]]

    def test_header_search_is_real_get_form_with_submit_button(self):
        response = self.client.get(reverse("storefront:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'action="{reverse("storefront:products")}"')
        self.assertContains(response, 'name="q"')
        self.assertContains(response, 'class="search-btn" type="submit"')

    def test_search_matches_product_name(self):
        response = self.search("Nano Charger")
        self.assertEqual(self.result_ids(response), [self.charger.public_id])

    def test_search_matches_brand_and_category(self):
        brand_response = self.search("Search Baseus")
        category_response = self.search("Search Earbuds")
        self.assertEqual(self.result_ids(brand_response), [self.power_bank.public_id])
        self.assertEqual(self.result_ids(category_response), [self.earbud.public_id])

    def test_search_matches_sku_and_specification(self):
        sku_response = self.search("R50I-BLK")
        spec_response = self.search("IPX5")
        self.assertEqual(self.result_ids(sku_response), [self.earbud.public_id])
        self.assertEqual(self.result_ids(spec_response), [self.earbud.public_id])

    def test_search_matches_related_description_keywords(self):
        response = self.search("water resistant")
        self.assertEqual(self.result_ids(response), [self.earbud.public_id])

    def test_multi_word_query_can_match_across_brand_and_specification(self):
        response = self.search("Soundcore IPX5")
        self.assertEqual(self.result_ids(response), [self.earbud.public_id])

    def test_search_keeps_full_browser_catalog_but_limits_listing_products(self):
        response = self.search("20000mAh")
        self.assertEqual(self.result_ids(response), [self.power_bank.public_id])
        listing_ids = [product["id"] for product in response.context["store_data"]["listing_products"]]
        all_browser_ids = [product["id"] for product in response.context["store_data"]["products"]]
        self.assertEqual(listing_ids, [self.power_bank.public_id])
        self.assertIn(self.charger.public_id, all_browser_ids)
        self.assertIn(self.earbud.public_id, all_browser_ids)

    def test_category_filter_limits_visible_and_browser_listing_products(self):
        response = self.client.get(reverse("storefront:products"), {"category": self.earbuds.name})
        self.assertEqual(self.result_ids(response), [self.earbud.public_id])
        self.assertEqual(response.context["selected_category_name"], self.earbuds.name)
        listing_ids = [product["id"] for product in response.context["store_data"]["listing_products"]]
        self.assertEqual(listing_ids, [self.earbud.public_id])

    def test_category_slug_still_resolves_for_old_or_bookmarked_links(self):
        response = self.client.get(reverse("storefront:products"), {"category": self.power_banks.slug})
        self.assertEqual(self.result_ids(response), [self.power_bank.public_id])
        self.assertEqual(response.context["selected_category_name"], self.power_banks.name)

    def test_category_and_search_are_intersected(self):
        response = self.client.get(
            reverse("storefront:products"),
            {"category": self.earbuds.name, "q": "Anker"},
        )
        self.assertEqual(self.result_ids(response), [])
        self.assertEqual(response.context["search_result_count"], 0)

    def test_home_category_cards_use_filter_compatible_category_names(self):
        response = self.client.get(reverse("storefront:home"))
        self.assertContains(response, "category=Search%20Earbuds")
        self.assertNotContains(response, "category=search-earbuds")

    def test_draft_product_is_not_returned(self):
        response = self.search("prototype")
        self.assertNotIn(self.draft.public_id, self.result_ids(response))
        self.assertEqual(response.context["search_result_count"], 0)

    def test_no_result_page_is_graceful_and_keeps_query(self):
        response = self.search("does-not-exist-xyz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["products"], [])
        self.assertEqual(response.context["search_query"], "does-not-exist-xyz")
        self.assertContains(response, "No products found")
        self.assertContains(response, "View All Products")
