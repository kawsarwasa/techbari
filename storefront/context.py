"""Storefront presentation context backed by the catalog, inventory and promotion databases."""
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone

from catalog.presentation import brand_filters, catalog_queryset, category_filters, serialize_product
from inventory.models import InventoryBalance, Warehouse
from promotions.models import Coupon
from promotions.services import decorate_catalog
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


def _browser_coupon_map():
    now = timezone.now()
    coupons = Coupon.objects.filter(
        is_active=True,
        starts_at__lte=now,
        ends_at__gte=now,
    )
    result = {}
    for coupon in coupons:
        if not coupon.is_live:
            continue
        result[coupon.code] = {
            "type": "fixed" if coupon.discount_type == Coupon.DiscountType.FIXED else "percent",
            "value": float(coupon.value),
            "minimum": float(coupon.minimum_order_amount),
            "scope": coupon.scope,
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
    return {
        "catalog": catalog,
        "products": catalog,
        "hero": mock_data.HERO_SLIDES[0],
        "cart_summary": {"count": 0, "subtotal": 0, "total": 0},
        "categories": category_filters(),
        "brands": brand_filters(),
        "tracking": mock_data.TRACKING_ORDER,
        "featured_products": featured,
        "related_products": catalog[:4],
        "recommended_products": catalog[3:9] if len(catalog) > 3 else catalog[:6],
        "routes": routes,
        "store_data": {
            "products": browser_products,
            "listing_products": browser_products,
            "cart": [],
            "wishlist": mock_data.DEFAULT_WISHLIST,
            # Browser display is a preview only. Checkout revalidates all promotion rules server-side.
            "coupons": _browser_coupon_map(),
            "slides": [
                {**slide, "img": static(slide["image"]), "href": routes["products"]}
                for slide in mock_data.HERO_SLIDES
            ],
        },
    }
