from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from django.core import signing
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Campaign, CampaignEvent, Coupon, CouponRedemption, FlashSale

MONEY = Decimal("0.01")
CAMPAIGN_COOKIE = "tb_campaign"
CAMPAIGN_COOKIE_SALT = "techbari.promotions.campaign.v230"
CAMPAIGN_COOKIE_MAX_AGE = 60 * 60 * 24 * 30


class PromotionError(ValidationError):
    pass


def _money(value):
    return Decimal(value or 0).quantize(MONEY, rounding=ROUND_HALF_UP)


def _discount_price(base, discount_type, value):
    base = _money(base)
    value = Decimal(value or 0)
    if discount_type in {Coupon.DiscountType.PERCENTAGE, FlashSale.DiscountType.PERCENTAGE}:
        discount = (base * value / Decimal("100")).quantize(MONEY, rounding=ROUND_HALF_UP)
    else:
        discount = _money(value)
    return max(base - discount, Decimal("0.00"))


def _live_window(qs, at):
    return qs.filter(is_active=True, starts_at__lte=at, ends_at__gte=at)


def _sales_by_product(product_ids, *, at=None):
    at = at or timezone.now()
    product_ids = {int(value) for value in product_ids if value}
    if not product_ids:
        return {}
    rows = (_live_window(FlashSale.objects.all(), at).filter(products__id__in=product_ids).values("id", "name", "discount_type", "value", "products__id").distinct())
    mapping = {}
    for row in rows:
        mapping.setdefault(row["products__id"], []).append(row)
    return mapping


def apply_flash_sale_prices(rows, *, at=None):
    sales = _sales_by_product((row["variant"].product_id for row in rows), at=at)
    for row in rows:
        variant = row["variant"]
        product = variant.product
        regular = variant.regular_price_override if variant.regular_price_override is not None else product.regular_price
        current = variant.price_override if variant.price_override is not None else product.current_price
        best = _money(current)
        best_sale = None
        for sale in sales.get(product.pk, []):
            candidate = _discount_price(regular, sale["discount_type"], sale["value"])
            if candidate < best:
                best = candidate
                best_sale = sale
        row["unit_price"] = best
        row["flash_sale"] = best_sale
    return rows


def decorate_catalog(catalog, *, at=None):
    sales = _sales_by_product((product.get("pk") for product in catalog), at=at)
    for product in catalog:
        product_sales = sales.get(product.get("pk"), [])
        best_product_sale = None
        for variant in product.get("variants", []):
            current = _money(variant.get("price", 0))
            regular = _money(variant.get("regular_price", current))
            best = current
            chosen = None
            for sale in product_sales:
                candidate = _discount_price(regular, sale["discount_type"], sale["value"])
                if candidate < best:
                    best = candidate
                    chosen = sale
            variant["price"] = int(best) if best == best.to_integral() else float(best)
            if chosen:
                variant["flash_sale"] = True
                variant["flash_sale_name"] = chosen["name"]
                if variant.get("is_default"):
                    best_product_sale = chosen
        default_variant = next((variant for variant in product.get("variants", []) if variant.get("is_default")), product.get("variants", [None])[0] if product.get("variants") else None)
        if default_variant:
            product["price"] = default_variant["price"]
        if best_product_sale:
            product["flash_sale"] = True
            product["flash_sale_name"] = best_product_sale["name"]
            product["badge"] = product.get("badge") or "Flash Sale"
            product["badge_class"] = product.get("badge_class") or "red"
    return catalog


def _eligible_subtotal(rows, coupon):
    if coupon.scope == Coupon.Scope.ALL:
        return sum((_money(row["unit_price"]) * int(row["quantity"]) for row in rows), Decimal("0.00"))
    if coupon.scope == Coupon.Scope.PRODUCTS:
        allowed = set(coupon.products.values_list("id", flat=True))
        return sum((_money(row["unit_price"]) * int(row["quantity"]) for row in rows if row["variant"].product_id in allowed), Decimal("0.00"))
    if coupon.scope == Coupon.Scope.CATEGORIES:
        allowed = set(coupon.categories.values_list("id", flat=True))
        return sum((_money(row["unit_price"]) * int(row["quantity"]) for row in rows if row["variant"].product.category_id in allowed), Decimal("0.00"))
    return Decimal("0.00")


def coupon_discount_for_rows(code, rows, *, at=None, lock=False):
    code = (code or "").strip().upper()
    if not code:
        return None, Decimal("0.00")
    at = at or timezone.now()
    qs = Coupon.objects.select_related("campaign")
    if lock:
        qs = qs.select_for_update()
    coupon = qs.filter(code=code).first()
    if coupon is None or not coupon.is_active:
        raise PromotionError("This coupon code is not valid.")
    if at < coupon.starts_at:
        raise PromotionError("This coupon is not active yet.")
    if at > coupon.ends_at:
        raise PromotionError("This coupon has expired.")
    if coupon.usage_limit is not None and coupon.usage_count >= coupon.usage_limit:
        raise PromotionError("This coupon has reached its usage limit.")
    subtotal = sum((_money(row["unit_price"]) * int(row["quantity"]) for row in rows), Decimal("0.00"))
    if subtotal < coupon.minimum_order_amount:
        raise PromotionError(f"Minimum order for coupon {coupon.code} is {coupon.minimum_order_amount:.2f}.")
    eligible = _eligible_subtotal(rows, coupon)
    if eligible <= 0:
        raise PromotionError("This coupon does not apply to the products in your cart.")
    if coupon.discount_type == Coupon.DiscountType.PERCENTAGE:
        discount = (eligible * coupon.value / Decimal("100")).quantize(MONEY, rounding=ROUND_HALF_UP)
    else:
        discount = _money(coupon.value)
    return coupon, min(eligible, max(discount, Decimal("0.00")))


def redeem_coupon(*, coupon, order, discount_amount):
    if coupon is None or discount_amount <= 0:
        return None
    if CouponRedemption.objects.filter(order=order).exists():
        return CouponRedemption.objects.get(order=order)
    if coupon.usage_limit is not None and coupon.usage_count >= coupon.usage_limit:
        raise PromotionError("This coupon has reached its usage limit.")
    redemption = CouponRedemption.objects.create(coupon=coupon, order=order, discount_amount=_money(discount_amount))
    coupon.usage_count += 1
    coupon.save(update_fields=["usage_count", "updated_at"])
    if coupon.campaign_id:
        CampaignEvent.objects.get_or_create(campaign=coupon.campaign, order=order, event_type=CampaignEvent.EventType.COUPON_APPLIED, defaults={"coupon": coupon, "amount": _money(discount_amount)})
    return redemption


def campaign_for_code(code, *, require_live=False):
    code = (code or "").strip().upper()
    if not code:
        return None
    campaign = Campaign.objects.filter(code=code, is_active=True).first()
    if not campaign:
        return None
    if require_live and not campaign.is_live:
        return None
    return campaign


def encode_campaign_cookie(campaign, tracking_token=None):
    return signing.dumps({"code": campaign.code, "token": tracking_token or uuid4().hex}, salt=CAMPAIGN_COOKIE_SALT)


def decode_campaign_cookie(value):
    if not value:
        return {}
    try:
        payload = signing.loads(value, salt=CAMPAIGN_COOKIE_SALT, max_age=CAMPAIGN_COOKIE_MAX_AGE)
    except signing.BadSignature:
        return {}
    return payload if isinstance(payload, dict) else {}


def campaign_code_for_request(request):
    direct = (request.GET.get("campaign") or request.GET.get("utm_campaign") or "").strip().upper()
    if direct and campaign_for_code(direct, require_live=True):
        return direct
    payload = decode_campaign_cookie(request.COOKIES.get(CAMPAIGN_COOKIE, ""))
    code = str(payload.get("code") or "").strip().upper()
    return code if campaign_for_code(code) else ""


def capture_campaign_request(request):
    code = (request.GET.get("campaign") or request.GET.get("utm_campaign") or "").strip().upper()
    campaign = campaign_for_code(code, require_live=True)
    if campaign is None:
        return None
    tracking_token = uuid4().hex
    source = (request.GET.get("utm_source") or campaign.source or "")[:80]
    medium = (request.GET.get("utm_medium") or campaign.medium or "")[:80]
    CampaignEvent.objects.create(campaign=campaign, event_type=CampaignEvent.EventType.VISIT, tracking_token=tracking_token, source=source, medium=medium, landing_path=request.get_full_path()[:500], referrer=(request.META.get("HTTP_REFERER") or "")[:500])
    return campaign, tracking_token


def record_campaign_conversion(*, order, campaign_code="", coupon=None):
    campaign = campaign_for_code(campaign_code)
    if campaign is None and coupon is not None and coupon.campaign_id:
        campaign = coupon.campaign
    if campaign is None:
        return None
    event, _ = CampaignEvent.objects.get_or_create(campaign=campaign, order=order, event_type=CampaignEvent.EventType.CONVERSION, defaults={"coupon": coupon, "source": campaign.source, "medium": campaign.medium, "amount": _money(order.grand_total)})
    return event
