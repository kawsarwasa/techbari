import json
from decimal import Decimal
from datetime import timedelta

from django.test import Client, TestCase
from django.utils import timezone

from catalog.models import Brand, Category, Product, ProductVariant
from customers.models import CustomerGroup
from inventory.models import InventoryBalance, Warehouse
from sales.models import SalesOrder
from storefront.checkout_services import place_checkout_order

from .models import Campaign, CampaignEvent, Coupon, CouponRedemption, FlashSale
from .services import PromotionError, apply_flash_sale_prices, coupon_discount_for_rows, record_campaign_conversion, redeem_coupon


class PromotionMarketingTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.category = Category.objects.create(name="Promo Audio QA", slug="promo-audio-qa")
        self.other_category = Category.objects.create(name="Promo Power QA", slug="promo-power-qa")
        self.brand = Brand.objects.create(name="Promo Brand QA", slug="promo-brand-qa")
        self.product = Product.objects.create(public_id="promo-p-audio", name="Promo TWS", slug="promo-tws", category=self.category, brand=self.brand, regular_price=Decimal("1000.00"), sale_price=Decimal("900.00"), status=Product.Status.ACTIVE)
        self.variant = ProductVariant.objects.create(product=self.product, name="Default", sku="PROMO-TWS-1", is_default=True, stock_quantity=10)
        self.other_product = Product.objects.create(public_id="promo-p-power", name="Promo Power Bank", slug="promo-power-bank", category=self.other_category, brand=self.brand, regular_price=Decimal("2000.00"), status=Product.Status.ACTIVE)
        self.other_variant = ProductVariant.objects.create(product=self.other_product, name="Default", sku="PROMO-PB-1", is_default=True, stock_quantity=10)
        self.warehouse = Warehouse.objects.filter(is_default=True, is_active=True).order_by("id").first()
        if self.warehouse is None:
            self.warehouse = Warehouse.objects.create(name="Promo Main", code="PROMO-MAIN", is_default=True)
        InventoryBalance.objects.update_or_create(warehouse=self.warehouse, variant=self.variant, defaults={"on_hand": 20})
        InventoryBalance.objects.update_or_create(warehouse=self.warehouse, variant=self.other_variant, defaults={"on_hand": 20})
        CustomerGroup.objects.get_or_create(name="Retail", code="RETAIL")
        self.campaign = Campaign.objects.create(code="FB-SEPT", name="Facebook September", source="facebook", medium="paid_social", starts_at=self.now - timedelta(days=1), ends_at=self.now + timedelta(days=7))

    def rows(self, variant=None, qty=1, price=None):
        variant = variant or self.variant
        return [{"variant": variant, "quantity": qty, "unit_price": Decimal(price if price is not None else "900.00"), "discount_amount": Decimal("0.00")}]

    def make_coupon(self, **overrides):
        data = {"code": "SAVE10", "name": "Save 10%", "discount_type": Coupon.DiscountType.PERCENTAGE, "value": Decimal("10.00"), "minimum_order_amount": Decimal("0.00"), "starts_at": self.now - timedelta(hours=1), "ends_at": self.now + timedelta(days=1), "usage_limit": 10, "scope": Coupon.Scope.ALL}
        data.update(overrides)
        return Coupon.objects.create(**data)

    def checkout_post_data(self, token, *, coupon_code="", extra=None):
        data = {
            "checkout_token": token,
            "cart_payload": json.dumps([{"variant_id": self.variant.pk, "qty": 1}]),
            "coupon_code": coupon_code,
            "delivery_option": "inside",
            "payment_method": "cod",
            "full_name": "Promo Buyer",
            "phone": "01700000000",
            "email": "",
            "division": "Dhaka",
            "district": "Dhaka",
            "upazila": "Dhanmondi",
            "address": "Road 1",
            "landmark": "",
            "order_note": "",
        }
        data.update(extra or {})
        return data

    def test_percentage_coupon_discount(self):
        coupon = self.make_coupon()
        resolved, discount = coupon_discount_for_rows(coupon.code, self.rows(qty=2))
        self.assertEqual(resolved.pk, coupon.pk)
        self.assertEqual(discount, Decimal("180.00"))

    def test_fixed_coupon_respects_eligible_subtotal(self):
        coupon = self.make_coupon(code="FIXED", discount_type=Coupon.DiscountType.FIXED, value=Decimal("1000.00"), scope=Coupon.Scope.PRODUCTS)
        coupon.products.add(self.product)
        _, discount = coupon_discount_for_rows(coupon.code, self.rows())
        self.assertEqual(discount, Decimal("900.00"))

    def test_coupon_minimum_order_and_usage_limit(self):
        coupon = self.make_coupon(minimum_order_amount=Decimal("2000.00"))
        with self.assertRaisesMessage(PromotionError, "Minimum order"):
            coupon_discount_for_rows(coupon.code, self.rows())
        coupon.minimum_order_amount = Decimal("0.00")
        coupon.usage_count = coupon.usage_limit
        coupon.save(update_fields=["minimum_order_amount", "usage_count"])
        with self.assertRaisesMessage(PromotionError, "usage limit"):
            coupon_discount_for_rows(coupon.code, self.rows())

    def test_coupon_scheduled_expired_and_inactive_rules(self):
        scheduled = self.make_coupon(code="FUTURE", starts_at=self.now + timedelta(hours=1), ends_at=self.now + timedelta(hours=2))
        with self.assertRaisesMessage(PromotionError, "not active yet"):
            coupon_discount_for_rows(scheduled.code, self.rows())
        expired = self.make_coupon(code="OLD", starts_at=self.now - timedelta(days=2), ends_at=self.now - timedelta(days=1))
        with self.assertRaisesMessage(PromotionError, "expired"):
            coupon_discount_for_rows(expired.code, self.rows())
        inactive = self.make_coupon(code="OFF", is_active=False)
        with self.assertRaisesMessage(PromotionError, "not valid"):
            coupon_discount_for_rows(inactive.code, self.rows())

    def test_product_and_category_scopes(self):
        coupon = self.make_coupon(code="PRODUCT", scope=Coupon.Scope.PRODUCTS)
        coupon.products.add(self.other_product)
        with self.assertRaisesMessage(PromotionError, "does not apply"):
            coupon_discount_for_rows(coupon.code, self.rows())
        category_coupon = self.make_coupon(code="CAT", scope=Coupon.Scope.CATEGORIES)
        category_coupon.categories.add(self.category)
        _, discount = coupon_discount_for_rows(category_coupon.code, self.rows())
        self.assertEqual(discount, Decimal("90.00"))

    def test_browser_coupon_preview_contains_scope_and_minimum_rules(self):
        coupon = self.make_coupon(code="SCOPED", scope=Coupon.Scope.CATEGORIES, minimum_order_amount=Decimal("1500.00"))
        coupon.categories.add(self.category)
        response = Client().get("/cart/")
        preview = response.context["store_data"]["coupons"][coupon.code]
        self.assertEqual(preview["scope"], Coupon.Scope.CATEGORIES)
        self.assertEqual(preview["minimum"], 1500.0)
        self.assertEqual(preview["product_ids"], [self.product.public_id])

    def test_flash_sale_uses_best_price_without_bad_stacking(self):
        weak = FlashSale.objects.create(name="5% Flash", discount_type=FlashSale.DiscountType.PERCENTAGE, value=Decimal("5.00"), starts_at=self.now - timedelta(hours=1), ends_at=self.now + timedelta(hours=1))
        weak.products.add(self.product)
        rows = apply_flash_sale_prices(self.rows(price="900.00"))
        self.assertEqual(rows[0]["unit_price"], Decimal("900.00"))
        strong = FlashSale.objects.create(name="25% Flash", discount_type=FlashSale.DiscountType.PERCENTAGE, value=Decimal("25.00"), starts_at=self.now - timedelta(hours=1), ends_at=self.now + timedelta(hours=1))
        strong.products.add(self.product)
        rows = apply_flash_sale_prices(self.rows(price="900.00"))
        self.assertEqual(rows[0]["unit_price"], Decimal("750.00"))
        self.assertEqual(rows[0]["flash_sale"]["name"], "25% Flash")

    def test_redemption_increments_usage_once(self):
        coupon = self.make_coupon()
        order = SalesOrder.objects.create(warehouse=self.warehouse)
        redemption = redeem_coupon(coupon=coupon, order=order, discount_amount=Decimal("50.00"))
        coupon.refresh_from_db()
        self.assertEqual(coupon.usage_count, 1)
        second = redeem_coupon(coupon=coupon, order=order, discount_amount=Decimal("50.00"))
        coupon.refresh_from_db()
        self.assertEqual(second.pk, redemption.pk)
        self.assertEqual(coupon.usage_count, 1)

    def test_campaign_conversion_is_idempotent(self):
        order = SalesOrder.objects.create(warehouse=self.warehouse, grand_total=Decimal("500.00"))
        attribution = {"campaign": self.campaign, "tracking_token": "visit-token", "source": "facebook", "medium": "cpc"}
        first = record_campaign_conversion(order=order, attribution=attribution)
        second = record_campaign_conversion(order=order, attribution=attribution)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(CampaignEvent.objects.filter(event_type=CampaignEvent.EventType.CONVERSION).count(), 1)

    def test_campaign_landing_is_tracked_and_cookie_is_set(self):
        response = Client().get("/products/?campaign=FB-SEPT&utm_source=facebook&utm_medium=cpc")
        self.assertEqual(response.status_code, 200)
        self.assertIn("tb_campaign", response.cookies)
        event = CampaignEvent.objects.get(event_type=CampaignEvent.EventType.VISIT)
        self.assertEqual(event.campaign, self.campaign)
        self.assertEqual(event.source, "facebook")
        self.assertEqual(event.medium, "cpc")

    def test_signed_visit_attribution_flows_to_conversion_and_ignores_posted_campaign(self):
        other_campaign = Campaign.objects.create(code="OTHER", name="Other Campaign", starts_at=self.now - timedelta(days=1), ends_at=self.now + timedelta(days=7))
        client = Client()
        landing = client.get("/products/?campaign=FB-SEPT&utm_source=facebook&utm_medium=retargeting", HTTP_REFERER="https://facebook.example/ad")
        self.assertEqual(landing.status_code, 200)
        visit = CampaignEvent.objects.get(event_type=CampaignEvent.EventType.VISIT)
        checkout = client.get("/checkout/")
        token = checkout.context["checkout_form"].initial["checkout_token"]
        response = client.post("/checkout/", self.checkout_post_data(token, extra={"campaign_code": other_campaign.code}))
        self.assertEqual(response.status_code, 302)
        conversion = CampaignEvent.objects.get(event_type=CampaignEvent.EventType.CONVERSION)
        self.assertEqual(conversion.campaign, self.campaign)
        self.assertEqual(conversion.tracking_token, visit.tracking_token)
        self.assertEqual(conversion.source, "facebook")
        self.assertEqual(conversion.medium, "retargeting")
        self.assertEqual(conversion.referrer, "https://facebook.example/ad")

    def test_tampered_campaign_cookie_does_not_create_conversion(self):
        client = Client()
        client.cookies["tb_campaign"] = "tampered-value"
        checkout = client.get("/checkout/")
        token = checkout.context["checkout_form"].initial["checkout_token"]
        response = client.post("/checkout/", self.checkout_post_data(token, extra={"campaign_code": self.campaign.code}))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(CampaignEvent.objects.filter(event_type=CampaignEvent.EventType.CONVERSION).exists())

    def test_checkout_uses_real_coupon_and_records_redemption(self):
        coupon = self.make_coupon(code="CHECKOUT", discount_type=Coupon.DiscountType.FIXED, value=Decimal("100.00"), campaign=self.campaign)
        cleaned = {"checkout_token": {"order_number": "TB-TEST-CHECKOUT"}, "cart_payload": [{"variant_id": self.variant.pk, "qty": 1}], "coupon_code": coupon.code, "delivery_option": "inside", "payment_method": "cod", "full_name": "Test Buyer", "phone": "01700000000", "email": "", "division": "Dhaka", "district": "Dhaka", "upazila": "Dhanmondi", "address": "Road 1", "landmark": "", "order_note": ""}
        order, created = place_checkout_order(cleaned)
        self.assertTrue(created)
        self.assertEqual(order.subtotal, Decimal("900.00"))
        self.assertEqual(order.discount_amount, Decimal("100.00"))
        self.assertEqual(order.grand_total, Decimal("860.00"))
        self.assertTrue(CouponRedemption.objects.filter(order=order, coupon=coupon).exists())
        self.assertTrue(CampaignEvent.objects.filter(order=order, event_type=CampaignEvent.EventType.CONVERSION).exists())

    def test_featured_product_can_be_toggled_from_marketing_dashboard(self):
        self.assertFalse(self.product.is_featured)
        response = Client().post("/dashboard/marketing/", {"action": "toggle-featured", "product_id": self.product.pk})
        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        self.assertTrue(self.product.is_featured)

    def test_dashboard_marketing_pages_are_database_backed(self):
        self.make_coupon()
        client = Client()
        self.assertEqual(client.get("/dashboard/marketing/").status_code, 200)
        self.assertEqual(client.get("/dashboard/coupons/").status_code, 200)
        self.assertEqual(client.get("/dashboard/coupons/add/").status_code, 200)
