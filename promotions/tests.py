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
        self.category = Category.objects.create(name="Audio", slug="audio")
        self.other_category = Category.objects.create(name="Power", slug="power")
        self.brand = Brand.objects.create(name="TechBari", slug="techbari")
        self.product = Product.objects.create(public_id="p-audio", name="TWS", slug="tws", category=self.category, brand=self.brand, regular_price=Decimal("1000.00"), sale_price=Decimal("900.00"), status=Product.Status.ACTIVE)
        self.variant = ProductVariant.objects.create(product=self.product, name="Default", sku="TWS-1", is_default=True, stock_quantity=10)
        self.other_product = Product.objects.create(public_id="p-power", name="Power Bank", slug="power-bank", category=self.other_category, brand=self.brand, regular_price=Decimal("2000.00"), status=Product.Status.ACTIVE)
        self.other_variant = ProductVariant.objects.create(product=self.other_product, name="Default", sku="PB-1", is_default=True, stock_quantity=10)
        self.warehouse = Warehouse.objects.create(name="Main", code="MAIN", is_default=True)
        InventoryBalance.objects.create(warehouse=self.warehouse, variant=self.variant, on_hand=20)
        InventoryBalance.objects.create(warehouse=self.warehouse, variant=self.other_variant, on_hand=20)
        CustomerGroup.objects.create(name="Retail", code="RETAIL")
        self.campaign = Campaign.objects.create(code="FB-SEPT", name="Facebook September", source="facebook", medium="paid_social", starts_at=self.now - timedelta(days=1), ends_at=self.now + timedelta(days=7))

    def rows(self, variant=None, qty=1, price=None):
        variant = variant or self.variant
        return [{"variant": variant, "quantity": qty, "unit_price": Decimal(price if price is not None else "900.00"), "discount_amount": Decimal("0.00")}]

    def make_coupon(self, **overrides):
        data = {"code": "SAVE10", "name": "Save 10%", "discount_type": Coupon.DiscountType.PERCENTAGE, "value": Decimal("10.00"), "minimum_order_amount": Decimal("0.00"), "starts_at": self.now - timedelta(hours=1), "ends_at": self.now + timedelta(days=1), "usage_limit": 10, "scope": Coupon.Scope.ALL}
        data.update(overrides)
        return Coupon.objects.create(**data)

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

    def test_product_and_category_scopes(self):
        coupon = self.make_coupon(code="PRODUCT", scope=Coupon.Scope.PRODUCTS)
        coupon.products.add(self.other_product)
        with self.assertRaisesMessage(PromotionError, "does not apply"):
            coupon_discount_for_rows(coupon.code, self.rows())
        category_coupon = self.make_coupon(code="CAT", scope=Coupon.Scope.CATEGORIES)
        category_coupon.categories.add(self.category)
        _, discount = coupon_discount_for_rows(category_coupon.code, self.rows())
        self.assertEqual(discount, Decimal("90.00"))

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
        first = record_campaign_conversion(order=order, campaign_code=self.campaign.code)
        second = record_campaign_conversion(order=order, campaign_code=self.campaign.code)
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

    def test_checkout_uses_real_coupon_and_records_redemption(self):
        coupon = self.make_coupon(code="CHECKOUT", discount_type=Coupon.DiscountType.FIXED, value=Decimal("100.00"))
        cleaned = {"checkout_token": {"order_number": "TB-TEST-CHECKOUT"}, "cart_payload": [{"variant_id": self.variant.pk, "qty": 1}], "coupon_code": coupon.code, "campaign_code": self.campaign.code, "delivery_option": "inside", "payment_method": "cod", "full_name": "Test Buyer", "phone": "01700000000", "email": "", "division": "Dhaka", "district": "Dhaka", "upazila": "Dhanmondi", "address": "Road 1", "landmark": "", "order_note": ""}
        order, created = place_checkout_order(cleaned)
        self.assertTrue(created)
        self.assertEqual(order.subtotal, Decimal("900.00"))
        self.assertEqual(order.discount_amount, Decimal("100.00"))
        self.assertEqual(order.grand_total, Decimal("860.00"))
        self.assertTrue(CouponRedemption.objects.filter(order=order, coupon=coupon).exists())
        self.assertTrue(CampaignEvent.objects.filter(order=order, event_type=CampaignEvent.EventType.CONVERSION).exists())

    def test_dashboard_marketing_pages_are_database_backed(self):
        self.make_coupon()
        client = Client()
        self.assertEqual(client.get("/dashboard/marketing/").status_code, 200)
        self.assertEqual(client.get("/dashboard/coupons/").status_code, 200)
        self.assertEqual(client.get("/dashboard/coupons/add/").status_code, 200)
