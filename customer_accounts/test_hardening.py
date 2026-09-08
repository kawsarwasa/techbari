import json
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from catalog.models import Brand, Category, Product, ProductVariant
from customers.models import Customer, CustomerGroup
from inventory.models import InventoryBalance, Warehouse
from sales.models import SalesOrder

from .models import CustomerAccount, SavedAddress
from .services import register_customer_account


PASSWORD = "StrongPass123!"


class CustomerAccountHardeningTests(TestCase):
    def setUp(self):
        self.group, _ = CustomerGroup.objects.get_or_create(name="Retail", code="RETAIL", defaults={"is_active": True})
        self.warehouse = Warehouse.objects.filter(is_default=True).first()
        if not self.warehouse:
            self.warehouse = Warehouse.objects.create(name="V270 Hardening Warehouse", code="V270-HARD", is_default=True, is_active=True)
        self.category = Category.objects.create(name="V270 Hardening", slug="v270-hardening")
        self.brand = Brand.objects.create(name="V270 Hardening Brand", slug="v270-hardening-brand")
        self.product = Product.objects.create(
            public_id="v270-hardening-product",
            name="V270 Hardening Product",
            slug="v270-hardening-product",
            category=self.category,
            brand=self.brand,
            regular_price=Decimal("800.00"),
            status=Product.Status.ACTIVE,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            name="Default",
            sku="V270-HARD-SKU",
            stock_quantity=5,
            is_default=True,
            is_active=True,
        )
        InventoryBalance.objects.update_or_create(
            warehouse=self.warehouse,
            variant=self.variant,
            defaults={"on_hand": 5, "reserved_quantity": 0, "low_stock_threshold": 1},
        )

    def test_existing_crm_opening_balance_cannot_be_self_claimed_without_verification(self):
        customer = Customer.objects.create(
            name="Legacy Due Customer",
            phone="01730000001",
            email="legacydue@example.com",
            group=self.group,
            opening_due=Decimal("2500.00"),
        )
        response = self.client.post(
            reverse("storefront:register"),
            {
                "name": customer.name,
                "phone": customer.phone,
                "email": customer.email,
                "previous_order_number": "",
                "password1": PASSWORD,
                "password2": PASSWORD,
                "terms": "on",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Contact TechBari support")
        self.assertFalse(CustomerAccount.objects.filter(customer=customer).exists())

    def test_saved_destination_prefill_keeps_linked_account_identity(self):
        account = register_customer_account(
            name="Account Owner",
            phone="01730000002",
            email="owner@example.com",
            password=PASSWORD,
        )
        SavedAddress.objects.create(
            account=account,
            label="Office",
            recipient_name="Office Receiver",
            phone="01739999999",
            division="Dhaka",
            district="Dhaka",
            upazila="Gulshan",
            address="Office Road 10",
            landmark="Tower A",
            is_default=True,
        )
        self.client.force_login(account.user)
        response = self.client.get(reverse("storefront:checkout"))
        initial = response.context["checkout_form"].initial
        self.assertEqual(initial["full_name"], account.customer.name)
        self.assertEqual(initial["phone"], account.customer.phone)
        self.assertEqual(initial["address"], "Office Road 10")
        self.assertEqual(initial["upazila"], "Gulshan")

    def test_logged_in_shipping_destination_does_not_overwrite_crm_profile(self):
        account = register_customer_account(
            name="Stable Profile",
            phone="01730000003",
            email="stable@example.com",
            password=PASSWORD,
        )
        account.customer.address = "Permanent Profile Address"
        account.customer.city = "Profile City"
        account.customer.district = "Profile District"
        account.customer.save(update_fields=["address", "city", "district", "updated_at"])
        self.client.force_login(account.user)
        token = self.client.get(reverse("storefront:checkout")).context["checkout_form"].initial["checkout_token"]
        response = self.client.post(
            reverse("storefront:checkout"),
            {
                "full_name": "Stable Profile",
                "phone": account.customer.phone,
                "email": account.customer.email,
                "division": "Dhaka",
                "district": "Shipping District",
                "upazila": "Shipping Area",
                "address": "Temporary Shipping Address",
                "landmark": "Near Market",
                "delivery_option": "inside",
                "payment_method": "cod",
                "order_note": "",
                "coupon_code": "",
                "cart_payload": json.dumps([{"variant_id": self.variant.pk, "qty": 1}]),
                "checkout_token": token,
            },
        )
        self.assertEqual(response.status_code, 302)
        account.customer.refresh_from_db()
        self.assertEqual(account.customer.name, "Stable Profile")
        self.assertEqual(account.customer.address, "Permanent Profile Address")
        self.assertEqual(account.customer.city, "Profile City")
        self.assertEqual(account.customer.district, "Profile District")
        order = SalesOrder.objects.filter(customer=account.customer).latest("id")
        self.assertEqual(order.shipping_address, "Temporary Shipping Address (Landmark: Near Market)")
        self.assertEqual(order.shipping_city, "Shipping Area")
        self.assertEqual(order.shipping_district, "Shipping District")
