import json
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from catalog.models import Brand, Category, Product, ProductVariant
from customers.models import Customer
from inventory.models import InventoryBalance, Warehouse
from sales.models import SalesOrder


class CheckoutBackendTests(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.filter(is_default=True, is_active=True).order_by("id").first()
        if self.warehouse is None:
            self.warehouse = Warehouse.objects.create(
                name="Online Main",
                code="ONLINE-MAIN",
                is_default=True,
                is_active=True,
            )
        self.category = Category.objects.create(name="Checkout Phones", slug="checkout-phones")
        self.brand = Brand.objects.create(name="Checkout Brand", slug="checkout-brand")
        self.product = Product.objects.create(
            public_id="checkout-phone",
            name="Checkout Phone",
            slug="checkout-phone",
            category=self.category,
            brand=self.brand,
            regular_price=Decimal("100.00"),
            status=Product.Status.ACTIVE,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            name="Black",
            sku="CHECKOUT-BLK",
            stock_quantity=5,
            is_default=True,
            is_active=True,
        )

    def checkout_token(self):
        response = self.client.get(reverse("storefront:checkout"))
        self.assertEqual(response.status_code, 200)
        return response.context["checkout_form"].initial["checkout_token"]

    def payload(self, token=None, quantity=2, **overrides):
        data = {
            "full_name": "Online Customer",
            "phone": "01712345678",
            "email": "buyer@example.com",
            "division": "Dhaka",
            "district": "Dhaka",
            "upazila": "Dhanmondi",
            "address": "House 1, Road 2",
            "landmark": "Near Lake",
            "delivery_option": "inside",
            "payment_method": "cod",
            "order_note": "Call before delivery",
            "coupon_code": "",
            "cart_payload": json.dumps([{"variant_id": self.variant.pk, "qty": quantity}]),
            "checkout_token": token or self.checkout_token(),
        }
        data.update(overrides)
        return data

    def test_checkout_get_is_real_form_and_default_browser_cart_is_empty(self):
        response = self.client.get(reverse("storefront:checkout"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "checkoutForm")
        self.assertContains(response, "Cash on Delivery")
        self.assertEqual(response.context["store_data"]["cart"], [])

    def test_checkout_creates_customer_pending_order_and_reserves_stock(self):
        response = self.client.post(reverse("storefront:checkout"), self.payload())
        self.assertEqual(response.status_code, 302)
        order = SalesOrder.objects.get()
        customer = Customer.objects.get(phone="01712345678")
        balance = InventoryBalance.objects.get(warehouse=self.warehouse, variant=self.variant)
        self.assertEqual(order.customer, customer)
        self.assertEqual(customer.source, Customer.Source.ONLINE)
        self.assertEqual(order.channel, SalesOrder.Channel.ONLINE)
        self.assertEqual(order.status, SalesOrder.Status.PENDING)
        self.assertEqual(order.payment_status, SalesOrder.PaymentStatus.UNPAID)
        self.assertEqual(order.subtotal, Decimal("200.00"))
        self.assertEqual(order.shipping_charge, Decimal("60.00"))
        self.assertEqual(order.grand_total, Decimal("260.00"))
        self.assertEqual(balance.on_hand, 5)
        self.assertEqual(balance.reserved_quantity, 2)
        self.assertEqual(order.items.get().reserved_quantity, 2)

    def test_checkout_uses_database_price_and_server_coupon_calculation(self):
        response = self.client.post(
            reverse("storefront:checkout"),
            self.payload(coupon_code="TECH10", fake_price="1.00"),
        )
        self.assertEqual(response.status_code, 302)
        order = SalesOrder.objects.get()
        self.assertEqual(order.items.get().unit_price, Decimal("100.00"))
        self.assertEqual(order.discount_amount, Decimal("20.00"))
        self.assertEqual(order.grand_total, Decimal("240.00"))

    def test_outside_dhaka_shipping_is_verified_server_side(self):
        response = self.client.post(
            reverse("storefront:checkout"),
            self.payload(delivery_option="outside", division="Chattogram", district="Chattogram"),
        )
        self.assertEqual(response.status_code, 302)
        order = SalesOrder.objects.get()
        self.assertEqual(order.shipping_charge, Decimal("120.00"))
        self.assertEqual(order.grand_total, Decimal("320.00"))

    def test_insufficient_stock_rolls_back_customer_order_and_reservation(self):
        response = self.client.post(reverse("storefront:checkout"), self.payload(quantity=6))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Not enough available stock")
        self.assertEqual(SalesOrder.objects.count(), 0)
        self.assertEqual(Customer.objects.filter(phone="01712345678").count(), 0)
        balance = InventoryBalance.objects.get(warehouse=self.warehouse, variant=self.variant)
        self.assertEqual(balance.on_hand, 5)
        self.assertEqual(balance.reserved_quantity, 0)

    def test_duplicate_checkout_submission_is_idempotent(self):
        token = self.checkout_token()
        data = self.payload(token=token)
        first = self.client.post(reverse("storefront:checkout"), data)
        second = self.client.post(reverse("storefront:checkout"), data)
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(SalesOrder.objects.count(), 1)
        balance = InventoryBalance.objects.get(warehouse=self.warehouse, variant=self.variant)
        self.assertEqual(balance.reserved_quantity, 2)

    def test_existing_phone_updates_and_reuses_customer(self):
        customer = Customer.objects.create(name="Old Name", phone="01712345678", email="")
        response = self.client.post(reverse("storefront:checkout"), self.payload(full_name="New Name"))
        self.assertEqual(response.status_code, 302)
        customer.refresh_from_db()
        self.assertEqual(Customer.objects.filter(phone="01712345678").count(), 1)
        self.assertEqual(customer.name, "New Name")
        self.assertEqual(SalesOrder.objects.get().customer, customer)

    def test_non_cod_payment_is_rejected_until_payment_phase(self):
        response = self.client.post(reverse("storefront:checkout"), self.payload(payment_method="bkash"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")
        self.assertEqual(SalesOrder.objects.count(), 0)

    def test_tampered_or_empty_cart_does_not_create_order(self):
        response = self.client.post(
            reverse("storefront:checkout"),
            self.payload(cart_payload=json.dumps([{"variant_id": 999999, "qty": 1}])),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "no longer available")
        self.assertEqual(SalesOrder.objects.count(), 0)

        response = self.client.post(reverse("storefront:checkout"), self.payload(cart_payload="[]"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your cart is empty")
        self.assertEqual(SalesOrder.objects.count(), 0)

    def test_checkout_success_requires_signed_order_token(self):
        response = self.client.post(reverse("storefront:checkout"), self.payload())
        self.assertEqual(response.status_code, 302)
        success = self.client.get(response["Location"])
        self.assertEqual(success.status_code, 200)
        self.assertContains(success, SalesOrder.objects.get().order_number)

        order = SalesOrder.objects.get()
        denied = self.client.get(reverse("storefront:checkout_success", args=[order.order_number]))
        self.assertEqual(denied.status_code, 404)

    def test_storefront_available_stock_follows_default_warehouse_reservations(self):
        self.client.post(reverse("storefront:checkout"), self.payload(quantity=2))
        response = self.client.get(reverse("storefront:products"))
        product = next(
            row for row in response.context["store_data"]["products"] if row["id"] == self.product.public_id
        )
        variant = next(row for row in product["variants"] if row["id"] == self.variant.pk)
        self.assertEqual(variant["stock"], 3)
        self.assertEqual(product["stock"], 3)
