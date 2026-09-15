from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from catalog.models import Brand, Category, Product, ProductVariant
from inventory.models import Warehouse
from sales.models import SalesOrder, SalesOrderItem


class StorefrontFeaturedCollectionTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Collection Audio", slug="collection-audio", is_active=True)
        brand = Brand.objects.create(name="Collection Brand", slug="collection-brand", is_active=True)
        self.warehouse = Warehouse.objects.create(name="Collection Warehouse", code="COLL-WH", is_active=True, is_default=True)

        self.best = Product.objects.create(
            public_id="collection-best",
            name="Collection Bestseller",
            slug="collection-best",
            category=category,
            brand=brand,
            regular_price=Decimal("2000.00"),
            status=Product.Status.ACTIVE,
            is_featured=True,
        )
        self.best_variant = ProductVariant.objects.create(
            product=self.best,
            name="Default",
            sku="COLL-BEST",
            stock_quantity=10,
            is_default=True,
            is_active=True,
        )

        self.new = Product.objects.create(
            public_id="collection-new",
            name="Collection New Arrival",
            slug="collection-new",
            category=category,
            brand=brand,
            regular_price=Decimal("1800.00"),
            status=Product.Status.ACTIVE,
            is_new_arrival=True,
        )
        self.new_variant = ProductVariant.objects.create(
            product=self.new,
            name="Default",
            sku="COLL-NEW",
            stock_quantity=10,
            is_default=True,
            is_active=True,
        )

        self.offer = Product.objects.create(
            public_id="collection-offer",
            name="Collection Special Offer",
            slug="collection-offer",
            category=category,
            brand=brand,
            regular_price=Decimal("2500.00"),
            sale_price=Decimal("1990.00"),
            status=Product.Status.ACTIVE,
        )
        self.offer_variant = ProductVariant.objects.create(
            product=self.offer,
            name="Default",
            sku="COLL-OFFER",
            stock_quantity=10,
            is_default=True,
            is_active=True,
        )

        self.secondary = Product.objects.create(
            public_id="collection-secondary",
            name="Collection Secondary Seller",
            slug="collection-secondary",
            category=category,
            brand=brand,
            regular_price=Decimal("1500.00"),
            status=Product.Status.ACTIVE,
        )
        self.secondary_variant = ProductVariant.objects.create(
            product=self.secondary,
            name="Default",
            sku="COLL-SECOND",
            stock_quantity=10,
            is_default=True,
            is_active=True,
        )

        order = SalesOrder.objects.create(warehouse=self.warehouse, status=SalesOrder.Status.PENDING)
        SalesOrderItem.objects.create(
            order=order,
            variant=self.best_variant,
            product_snapshot=self.best.name,
            variant_snapshot="Default",
            sku_snapshot=self.best_variant.sku,
            quantity=7,
            unit_price=Decimal("2000.00"),
        )
        SalesOrderItem.objects.create(
            order=order,
            variant=self.secondary_variant,
            product_snapshot=self.secondary.name,
            variant_snapshot="Default",
            sku_snapshot=self.secondary_variant.sku,
            quantity=2,
            unit_price=Decimal("1500.00"),
        )
        SalesOrder.objects.filter(pk=order.pk).update(status=SalesOrder.Status.COMPLETED)

    def product_ids(self, response):
        return [product["id"] for product in response.context["products"]]

    def test_homepage_featured_tabs_are_real_collections(self):
        response = self.client.get(reverse("storefront:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-home-featured-tab="best-selling"')
        self.assertContains(response, 'data-home-featured-tab="new-arrivals"')
        self.assertContains(response, 'data-home-featured-tab="special-offers"')
        self.assertContains(response, "?collection=best-selling")
        self.assertEqual(response.context["featured_products"][0]["id"], self.best.public_id)
        self.assertEqual(response.context["home_featured_collection_ids"]["new-arrivals"], [self.new.public_id])
        self.assertEqual(response.context["home_featured_collection_ids"]["special-offers"], [self.offer.public_id])

    def test_best_selling_collection_uses_completed_sales_quantity_order(self):
        response = self.client.get(reverse("storefront:products"), {"collection": "best-selling"})
        self.assertEqual(self.product_ids(response)[:2], [self.best.public_id, self.secondary.public_id])
        self.assertEqual(response.context["selected_collection_label"], "Best Selling")
        self.assertContains(response, "Best Selling Products")

    def test_new_arrivals_collection_only_returns_marked_products(self):
        response = self.client.get(reverse("storefront:products"), {"collection": "new-arrivals"})
        self.assertEqual(self.product_ids(response), [self.new.public_id])
        self.assertContains(response, "New Arrivals Products")

    def test_special_offers_collection_only_returns_discounted_products(self):
        response = self.client.get(reverse("storefront:products"), {"collection": "special-offers"})
        self.assertEqual(self.product_ids(response), [self.offer.public_id])
        self.assertContains(response, "Special Offers Products")

    def test_invalid_collection_falls_back_to_normal_products(self):
        response = self.client.get(reverse("storefront:products"), {"collection": "not-a-collection"})
        self.assertEqual(response.context["selected_collection"], "")
        self.assertGreaterEqual(len(self.product_ids(response)), 4)
        self.assertContains(response, "All Products")
