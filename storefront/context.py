"""Presentation context; replace the catalog source here in the database phase."""
from copy import deepcopy
from django.templatetags.static import static
from django.urls import reverse
from . import mock_data


def catalog_context():
    catalog = deepcopy(mock_data.PRODUCTS)
    for product in catalog:
        product["url"] = reverse("storefront:product_detail", kwargs={"slug": product["slug"]})
    browser_products = [
        {**product, "img": static(product["image"]), "old": product["regular_price"],
         "badgeClass": product["badge_class"]} for product in catalog
    ]
    listing_products = catalog + [{**product, "name": product["name"] + f" {index + 2}"}
                                  for index, product in enumerate(catalog[:5])]
    browser_listing = browser_products + [{**product, "name": product["name"] + f" {index + 2}"}
                                          for index, product in enumerate(browser_products[:5])]
    cart_count = sum(item["qty"] for item in mock_data.DEFAULT_CART)
    cart_subtotal = sum(next(p["price"] for p in catalog if p["id"] == item["id"]) * item["qty"]
                        for item in mock_data.DEFAULT_CART)
    routes = {name: reverse("storefront:" + name) for name in (
        "home", "products", "cart", "checkout", "wishlist", "track_order", "login", "register", "contact"
    )}
    return {
        "catalog": catalog, "products": listing_products,
        "hero": mock_data.HERO_SLIDES[0],
        "cart_summary": {"count": cart_count, "subtotal": cart_subtotal, "total": cart_subtotal + 60},
        "categories": mock_data.CATEGORIES, "brands": mock_data.BRANDS,
        "tracking": mock_data.TRACKING_ORDER,
        "featured_products": catalog[:6], "related_products": catalog[1:5],
        "recommended_products": catalog[3:9], "routes": routes,
        "store_data": {
            "products": browser_products, "listing_products": browser_listing, "cart": mock_data.DEFAULT_CART,
            "wishlist": mock_data.DEFAULT_WISHLIST, "coupons": mock_data.COUPONS,
            "slides": [{**slide, "img": static(slide["image"]), "href": routes["products"]}
                       for slide in mock_data.HERO_SLIDES],
        },
    }
