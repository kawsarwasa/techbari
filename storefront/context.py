"""Storefront presentation context backed by the catalog database."""
from django.templatetags.static import static
from django.urls import reverse

from catalog.presentation import brand_filters, catalog_queryset, category_filters, serialize_product
from . import mock_data


def catalog_context():
    catalog = [serialize_product(product) for product in catalog_queryset()]
    for product in catalog:
        product["url"] = reverse("storefront:product_detail", kwargs={"slug": product["slug"]})

    browser_products = [{**product, "img": product["image_url"], "old": product["regular_price"], "badgeClass": product["badge_class"]} for product in catalog]
    products_by_id = {product["id"]: product for product in catalog}
    matched_cart = [item for item in mock_data.DEFAULT_CART if item["id"] in products_by_id]
    cart_count = sum(item["qty"] for item in matched_cart)
    cart_subtotal = sum(products_by_id[item["id"]]["price"] * item["qty"] for item in matched_cart)
    routes = {name: reverse("storefront:" + name) for name in ("home", "products", "cart", "checkout", "wishlist", "track_order", "login", "register", "contact")}
    featured = [product for product in catalog if product.get("is_featured")][:6] or catalog[:6]
    return {
        "catalog": catalog, "products": catalog, "hero": mock_data.HERO_SLIDES[0],
        "cart_summary": {"count": cart_count, "subtotal": cart_subtotal, "total": cart_subtotal + (60 if cart_count else 0)},
        "categories": category_filters(), "brands": brand_filters(), "tracking": mock_data.TRACKING_ORDER,
        "featured_products": featured, "related_products": catalog[:4],
        "recommended_products": catalog[3:9] if len(catalog) > 3 else catalog[:6], "routes": routes,
        "store_data": {
            "products": browser_products, "listing_products": browser_products, "cart": matched_cart,
            "wishlist": mock_data.DEFAULT_WISHLIST, "coupons": mock_data.COUPONS,
            "slides": [{**slide, "img": static(slide["image"]), "href": routes["products"]} for slide in mock_data.HERO_SLIDES],
        },
    }
