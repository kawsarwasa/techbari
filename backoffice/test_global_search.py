from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from catalog.models import Brand, Category, Product, ProductVariant
from customers.models import Customer
from inventory.models import Warehouse
from sales.models import SalesOrder


@override_settings(STAFF_AUTH_ENABLED=True)
class GlobalSearchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="searchadmin",
            email="search@example.com",
            password="StrongPass123!",
        )
        self.client.force_login(self.user)

        category = Category.objects.create(name="Power Banks", slug="power-banks")
        brand = Brand.objects.create(name="Baseus", slug="baseus")
        self.product = Product.objects.create(
            public_id="baseus-adaman",
            name="Baseus Adaman Power Bank",
            slug="baseus-adaman-power-bank",
            category=category,
            brand=brand,
            regular_price=Decimal("2000.00"),
            status=Product.Status.ACTIVE,
        )
        ProductVariant.objects.create(
            product=self.product,
            name="Default",
            sku="TB-BASEUS-AD20",
            barcode="1234567890",
            is_default=True,
        )

        self.customer = Customer.objects.create(
            name="Rahim Ahmed",
            phone="01700000000",
            email="rahim@example.com",
        )
        warehouse = Warehouse.objects.create(
            name="Search Warehouse",
            code="SEARCH-WH",
            is_default=True,
            is_active=True,
        )
        self.order = SalesOrder.objects.create(
            order_number="TB-SEARCH-001",
            customer=self.customer,
            warehouse=warehouse,
            status=SalesOrder.Status.PENDING,
            grand_total=Decimal("2000.00"),
        )

    def test_global_search_returns_product_order_and_customer_matches(self):
        url = reverse("backoffice:global_search")

        product_response = self.client.get(url, {"q": "AD20"})
        self.assertEqual(product_response.status_code, 200)
        self.assertTrue(any(row["type"] == "Product" and row["title"] == self.product.name for row in product_response.json()["results"]))

        order_response = self.client.get(url, {"q": "SEARCH-001"})
        self.assertTrue(any(row["type"] == "Order" and row["title"] == self.order.order_number for row in order_response.json()["results"]))

        customer_response = self.client.get(url, {"q": "Rahim"})
        self.assertTrue(any(row["type"] == "Customer" and row["title"] == self.customer.name for row in customer_response.json()["results"]))

    def test_global_search_ignores_single_character_query(self):
        response = self.client.get(reverse("backoffice:global_search"), {"q": "a"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])
