"""Storefront presentation context backed by catalog, inventory, promotions, CMS and public integration settings."""
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone

from catalog.models import Category, Product
from catalog.presentation import brand_filters, catalog_queryset, category_filters, serialize_product
from integrations.services import public_tracking_config
from inventory.models import InventoryBalance, Warehouse
from promotions.models import Coupon
from promotions.services import decorate_catalog
from store_settings.services import storefront_cms_context
from . import mock_data


def _apply_online_warehouse_stock(catalog):
    warehouse = Warehouse.objects.filter(is_default=True, is_active=True).order_by("id").first() or Warehouse.objects.filter(is_active=True).order_by("id").first()
    if warehouse is None:
        return
    balances = {variant_id: max(0, int(on_hand) - int(reserved)) for variant_id, on_hand, reserved in InventoryBalance.objects.filter(warehouse=warehouse).values_list("variant_id", "on_hand", "reserved_quantity")}
    for product in catalog:
        total_available = 0
        for variant in product.get("variants", []):
            available = balances.get(variant["id"], 0)
            variant["stock"] = available
            variant["available"] = available > 0
            total_available += available
        product["stock"] = total_available


def _category_menu(image_urls=None):
    image_urls = image_urls or {}
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
            "image_url": image_urls.get(row.pk, ""),
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


def _coupon_product_ids(coupon):
    if coupon.scope == Coupon.Scope.ALL:
        return []
    if coupon.scope == Coupon.Scope.PRODUCTS:
        return list(coupon.products.filter(status=Product.Status.ACTIVE, category__is_active=True, brand__is_active=True).values_list("public_id", flat=True))
    if coupon.scope == Coupon.Scope.CATEGORIES:
        return list(Product.objects.filter(category__in=coupon.categories.all(), status=Product.Status.ACTIVE, category__is_active=True, brand__is_active=True).values_list("public_id", flat=True))
    return []


def _browser_coupon_map():
    now = timezone.now()
    coupons = Coupon.objects.filter(is_active=True, starts_at__lte=now, ends_at__gte=now).prefetch_related("products", "categories")
    result = {}
    for coupon in coupons:
        if not coupon.is_live:
            continue
        result[coupon.code] = {"type": "fixed" if coupon.discount_type == Coupon.DiscountType.FIXED else "percent", "value": float(coupon.value), "minimum": float(coupon.minimum_order_amount), "scope": coupon.scope, "product_ids": _coupon_product_ids(coupon)}
    return result


def catalog_context():
    catalog = [serialize_product(product) for product in catalog_queryset()]
    decorate_catalog(catalog)
    _apply_online_warehouse_stock(catalog)
    for product in catalog:
        product["url"] = reverse("storefront:product_detail", kwargs={"slug": product["slug"]})

    browser_products = [{**product, "img": product["image_url"], "old": product["regular_price"], "badgeClass": product["badge_class"]} for product in catalog]
    routes = {name: reverse("storefront:" + name) for name in ("home", "products", "cart", "checkout", "wishlist", "track_order", "login", "register", "contact")}
    featured = [product for product in catalog if product.get("is_featured")][:6]
    cms = storefront_cms_context()
    hero_slides = cms["hero_slides"]
    categories = category_filters()
    category_images = {row["id"]: row["image_url"] for row in categories}
    context = {
        "catalog": catalog,
        "products": catalog,
        "hero": hero_slides[0] if hero_slides else None,
        "cart_summary": {"count": 0, "subtotal": 0, "total": 0},
        "categories": categories,
        "home_categories": _home_categories(),
        "category_menu": _category_menu(category_images),
        "brands": brand_filters(),
        "tracking": mock_data.TRACKING_ORDER,
        "featured_products": featured,
        "related_products": catalog[:4],
        "recommended_products": catalog[3:9] if len(catalog) > 3 else catalog[:6],
        "routes": routes,
        "tracking_integrations": public_tracking_config(),
        **cms,
    }
    context["page_seo_description"] = cms["home_seo_description"]
    context["store_data"] = {"products": browser_products, "listing_products": browser_products, "cart": [], "wishlist": mock_data.DEFAULT_WISHLIST, "coupons": _browser_coupon_map(), "slides": hero_slides, "delivery": cms["delivery"]}
    return context
