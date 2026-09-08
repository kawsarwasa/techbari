"""Storefront presentation context backed by catalog, inventory, promotions and CMS settings."""
from django.urls import reverse
from django.utils import timezone

from catalog.models import Product
from catalog.presentation import brand_filters, catalog_queryset, category_filters, serialize_product
from inventory.models import InventoryBalance, Warehouse
from promotions.models import Coupon
from promotions.services import decorate_catalog
from store_settings.services import storefront_cms_context
from . import mock_data


def _apply_online_warehouse_stock(catalog):
    warehouse = (
        Warehouse.objects.filter(is_default=True, is_active=True).order_by("id").first()
        or Warehouse.objects.filter(is_active=True).order_by("id").first()
    )
    if warehouse is None:
        return
    balances = {
        variant_id: max(0, int(on_hand) - int(reserved))
        for variant_id, on_hand, reserved in InventoryBalance.objects.filter(
            warehouse=warehouse
        ).values_list("variant_id", "on_hand", "reserved_quantity")
    }
    for product in catalog:
        total_available = 0
        for variant in product.get("variants", []):
            available = balances.get(variant["id"], 0)
            variant["stock"] = available
            variant["available"] = available > 0
            total_available += available
        product["stock"] = total_available


def _coupon_product_ids(coupon):
    if coupon.scope == Coupon.Scope.ALL:
        return []
    if coupon.scope == Coupon.Scope.PRODUCTS:
        return list(
            coupon.products.filter(
                status=Product.Status.ACTIVE,
                category__is_active=True,
                brand__is_active=True,
            ).values_list("public_id", flat=True)
        )
    if coupon.scope == Coupon.Scope.CATEGORIES:
        return list(
            Product.objects.filter(
                category__in=coupon.categories.all(),
                status=Product.Status.ACTIVE,
                category__is_active=True,
                brand__is_active=True,
            ).values_list("public_id", flat=True)
        )
    return []


def _browser_coupon_map():
    now = timezone.now()
    coupons = Coupon.objects.filter(
        is_active=True,
        starts_at__lte=now,
        ends_at__gte=now,
    ).prefetch_related("products", "categories")
    result = {}
    for coupon in coupons:
        if not coupon.is_live:
            continue
        result[coupon.code] = {
            "type": "fixed" if coupon.discount_type == Coupon.DiscountType.FIXED else "percent",
            "value": float(coupon.value),
            "minimum": float(coupon.minimum_order_amount),
            "scope": coupon.scope,
            "product_ids": _coupon_product_ids(coupon),
        }
    return result


def catalog_context():
    catalog = [serialize_product(product) for product in catalog_queryset()]
    decorate_catalog(catalog)
    _apply_online_warehouse_stock(catalog)
    for product in catalog:
        product["url"] = reverse("storefront:product_detail", kwargs={"slug": product["slug"]})

    browser_products = [
        {
            **product,
            "img": product["image_url"],
            "old": product["regular_price"],
            "badgeClass": product["badge_class"],
        }
        for product in catalog
    ]
    routes = {
        name: reverse("storefront:" + name)
        for name in (
            "home",
            "products",
            "cart",
            "checkout",
            "wishlist",
            "track_order",
            "login",
            "register",
            "contact",
        )
    }
    featured = [product for product in catalog if product.get("is_featured")][:6] or catalog[:6]
    cms = storefront_cms_context()
    hero_slides = cms["hero_slides"]
    context = {
        "catalog": catalog,
        "products": catalog,
        "hero": hero_slides[0] if hero_slides else None,
        "cart_summary": {"count": 0, "subtotal": 0, "total": 0},
        "categories": category_filters(),
        "brands": brand_filters(),
        "tracking": mock_data.TRACKING_ORDER,
        "featured_products": featured,
        "related_products": catalog[:4],
        "recommended_products": catalog[3:9] if len(catalog) > 3 else catalog[:6],
        "routes": routes,
        **cms,
    }
    context["store_data"] = {
        "products": browser_products,
        "listing_products": browser_products,
        "cart": [],
        "wishlist": mock_data.DEFAULT_WISHLIST,
        # Browser display is a preview only. Checkout revalidates all promotion/CMS rules server-side.
        "coupons": _browser_coupon_map(),
        "slides": hero_slides,
        "delivery": cms["delivery"],
    }
    return context
