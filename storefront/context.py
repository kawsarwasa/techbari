"""Storefront presentation context backed by the catalog and inventory databases."""
from django.templatetags.static import static
from django.urls import reverse

from catalog.presentation import brand_filters, catalog_queryset, category_filters, serialize_product
from inventory.models import InventoryBalance, Warehouse
from . import mock_data


def _apply_online_warehouse_stock(catalog):
    warehouse = Warehouse.objects.filter(is_default=True, is_active=True).order_by("id").first()
    if warehouse is None:
        warehouse = Warehouse.objects.filter(is_active=True).order_by("id").first()
    if warehouse is None:
        return

    balances = {
        variant_id: max(0, int(on_hand) - int(reserved))
        for variant_id, on_hand, reserved in InventoryBalance.objects.filter(warehouse=warehouse).values_list(
            "variant_id", "on_hand", "reserved_quantity"
        )
    }
    for product in catalog:
        total_available = 0
        for variant in product.get("variants", []):
            available = balances.get(variant["id"], 0)
            variant["stock"] = available
            variant["available"] = available > 0
            total_available += available
        product["stock"] = total_available


def catalog_context():
    catalog = [serialize_product(product) for product in catalog_queryset()]
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
        for name in ("home", "products", "cart", "checkout", "wishlist", "track_order", "login", "register", "contact")
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
            "coupons": mock_data.COUPONS,
            "slides": [
                {**slide, "img": static(slide["image"]), "href": routes["products"]}
                for slide in mock_data.HERO_SLIDES
            ],
        },
    }
