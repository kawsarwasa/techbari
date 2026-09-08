import json
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from catalog.models import Brand, Category, Product, ProductVariant
from inventory.models import Warehouse
from sales.models import SalesOrder
from store_settings.models import StoreSettings


class StoreSettingsCheckoutIntegrationTests(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.filter(is_default=True, is_active=True).order_by("id").first()
        if self.warehouse is None:
            self.warehouse = Warehouse.objects.create(name="CMS Online", code="CMS-ONLINE", is_default=True, is_active=True)
        category = Category.objects.create(name="CMS Checkout", slug="cms-checkout")
        brand = Brand.objects.create(name="CMS Brand", slug="cms-brand")
        product = Product.objects.create(public_id="cms-product", name="CMS Product", slug="cms-product", category=category, brand=brand, regular_price=Decimal("100.00"), status=Product.Status.ACTIVE)
        self.variant = ProductVariant.objects.create(product=product, name="Default", sku="CMS-SKU", stock_quantity=10, is_default=True, is_active=True)

    def token(self):
        return self.client.get(reverse("storefront:checkout")).context["checkout_form"].initial["checkout_token"]

    def payload(self, **overrides):
        data = {
            "full_name": "CMS Buyer", "phone": "01811111111", "email": "cms@example.com",
            "division": "Dhaka", "district": "Dhaka", "upazila": "Dhanmondi", "address": "Road 1",
            "landmark": "", "delivery_option": "inside", "payment_method": "cod", "order_note": "", "coupon_code": "",
            "cart_payload": json.dumps([{"variant_id": self.variant.pk, "qty": 2}]), "checkout_token": self.token(),
        }
        data.update(overrides)
        return data

    def test_checkout_uses_custom_delivery_charge_from_store_settings(self):
        store = StoreSettings.get_solo()
        store.delivery_inside_dhaka_charge = Decimal("75.00")
        store.free_delivery_threshold = Decimal("0.00")
        store.save()
        response = self.client.post(reverse("storefront:checkout"), self.payload())
        self.assertEqual(response.status_code, 302)
        order = SalesOrder.objects.get()
        self.assertEqual(order.shipping_charge, Decimal("75.00"))
        self.assertEqual(order.grand_total, Decimal("275.00"))

    def test_checkout_applies_server_side_free_delivery_threshold(self):
        store = StoreSettings.get_solo()
        store.delivery_inside_dhaka_charge = Decimal("75.00")
        store.free_delivery_threshold = Decimal("200.00")
        store.save()
        response = self.client.post(reverse("storefront:checkout"), self.payload())
        self.assertEqual(response.status_code, 302)
        order = SalesOrder.objects.get()
        self.assertEqual(order.subtotal, Decimal("200.00"))
        self.assertEqual(order.shipping_charge, Decimal("0.00"))
        self.assertEqual(order.grand_total, Decimal("200.00"))

    def test_checkout_rejects_cod_when_store_disables_it(self):
        store = StoreSettings.get_solo()
        store.cod_enabled = False
        store.save()
        response = self.client.post(reverse("storefront:checkout"), self.payload())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cash on Delivery is currently disabled")
        self.assertEqual(SalesOrder.objects.count(), 0)
