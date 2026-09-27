"""Storefront presentation context backed by catalog, inventory, promotions, CMS and public integration settings."""
from django.templatetags.static import static
from django.urls import reverse

from catalog.models import Category
from catalog.presentation import brand_filters, category_filters, serialize_product
from integrations.services import public_tracking_config
from inventory.models import InventoryBalance, Warehouse
from promotions.services import decorate_catalog
from store_settings.services import storefront_cms_context

from . import mock_data


def _apply_online_warehouse_stock(catalog):
    variant_ids = [
        variant["id"]
        for product in catalog
        for variant in product.get("variants", [])
        if variant.get("id")
    ]
    if not variant_ids:
        return

    warehouse = (
        Warehouse.objects.filter(is_default=True, is_active=True).order_by("id").first()
        or Warehouse.objects.filter(is_active=True).order_by("id").first()
    )
    if warehouse is None:
        return

    balances = {
        variant_id: max(0, int(on_hand) - int(reserved))
        for variant_id, on_hand, reserved in InventoryBalance.objects.filter(
            warehouse=warehouse,
            variant_id__in=variant_ids,
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


def _category_image_url(category):
    if category.image:
        try:
            return category.image.url
        except ValueError:
            pass
    if category.static_image_path:
        return static(category.static_image_path)
    return static("store/images/category-placeholder.svg")


def _category_menu():
    rows = list(
        Category.objects.filter(is_active=True)
        .select_related("parent")
        .order_by("sort_order", "name", "id")
    )
    nodes = {
        row.pk: {
            "id": row.pk,
            "name": row.name,
            "slug": row.slug,
            "parent_id": row.parent_id,
            "image_url": _category_image_url(row),
            "children": [],
        }
        for row in rows
    }
    roots = []
    for row in rows:
        node = nodes[row.pk]
        parent = nodes.get(row.parent_id)
        if parent is None:
            roots.append(node)
        else:
            parent["children"].append(node)
    return roots


def _home_categories():
    """Nine fixed homepage category cards with consistent black-product artwork."""
    rows = (
        ("TWS Earbuds", "TWS Earbuds", "black-earbuds.svg"),
        ("Over-Ear Headphones", "Headphones", "black-headphones.svg"),
        ("Neckband Earphones", "Neckband", "black-neckband.svg"),
        ("Smartwatches", "Smartwatches", "black-smartwatch.svg"),
        ("Bluetooth Speakers", "Speakers", "black-speaker.svg"),
        ("Power Banks", "Power Banks", "black-powerbank.svg"),
        ("Wall Chargers", "Chargers", "black-charger.svg"),
        ("Cables", "Cables", "black-cable.svg"),
        ("Phone Accessories", "Phone Accessories", "black-phone-stand.svg"),
    )
    return [
        {
            "name": name,
            "filter_name": filter_name,
            "image_url": static(f"store/images/categories/{image_name}"),
        }
        for name, filter_name, image_name in rows
    ]


def prepare_catalog_products(products):
    """Serialize only the products needed by the current page."""
    catalog = [serialize_product(product) for product in products]
    decorate_catalog(catalog)
    _apply_online_warehouse_stock(catalog)
    for product in catalog:
        product["url"] = reverse("storefront:product_detail", kwargs={"slug": product["slug"]})
    return catalog


def browser_product_rows(catalog):
    return [
        {
            **product,
            "img": product["image_url"],
            "old": product["regular_price"],
            "badgeClass": product["badge_class"],
        }
        for product in catalog
    ]


def attach_catalog(context, products):
    catalog = prepare_catalog_products(products)
    browser_products = browser_product_rows(catalog)
    context.update(
        catalog=catalog,
        products=catalog,
        featured_products=[product for product in catalog if product.get("is_featured")][:6],
        related_products=catalog[:4],
        recommended_products=catalog[:6],
    )
    context["store_data"]["products"] = browser_products
    context["store_data"]["listing_products"] = browser_products
    return context


def catalog_context(products=None, *, include_filter_counts=False):
    """
    Build the common storefront shell without loading the whole product catalog.

    Product rows are opt-in per view. Category/brand count queries are also opt-in
    for directory/listing pages that actually render those filters.
    """
    cms = storefront_cms_context()
    hero_slides = cms["hero_slides"]
    categories = category_filters() if include_filter_counts else []
    brands = brand_filters() if include_filter_counts else []
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
            "coupon_preview",
            "product_bootstrap",
        )
    }
    context = {
        "catalog": [],
        "products": [],
        "hero": hero_slides[0] if hero_slides else None,
        "cart_summary": {"count": 0, "subtotal": 0, "total": 0},
        "categories": categories,
        "home_categories": _home_categories(),
        "category_menu": _category_menu(),
        "brands": brands,
        "tracking": mock_data.TRACKING_ORDER,
        "featured_products": [],
        "related_products": [],
        "recommended_products": [],
        "routes": routes,
        "tracking_integrations": public_tracking_config(),
        **cms,
    }
    context["page_seo_description"] = cms["home_seo_description"]
    context["store_data"] = {
        "products": [],
        "listing_products": [],
        "cart": [],
        "wishlist": mock_data.DEFAULT_WISHLIST,
        "coupons": {},
        "slides": hero_slides,
        "delivery": cms["delivery"],
    }
    if products is not None:
        attach_catalog(context, products)
    return context
