from decimal import Decimal

from django.db.models import Count, Prefetch, Q
from django.templatetags.static import static
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe

from .models import Brand, Category, Product, ProductImage, ProductSpecification, ProductVariant
from .richtext import inline_rich_html


def catalog_queryset(include_inactive=False):
    qs = Product.objects.select_related("category", "brand").prefetch_related(
        Prefetch("variants", queryset=ProductVariant.objects.order_by("-is_default", "id")),
        Prefetch("images", queryset=ProductImage.objects.order_by("sort_order", "id")),
        Prefetch("specifications", queryset=ProductSpecification.objects.order_by("sort_order", "id")),
    )
    if not include_inactive:
        qs = qs.filter(status=Product.Status.ACTIVE, category__is_active=True, brand__is_active=True)
    return qs


def _image_url(image):
    if image is None:
        return ""
    if image.image:
        try:
            return image.image.url
        except ValueError:
            pass
    if image.static_path:
        return static(image.static_path)
    return ""


def _category_image_url(category):
    if category.image:
        try:
            return category.image.url
        except ValueError:
            pass
    if category.static_image_path:
        return static(category.static_image_path)
    return static("store/images/cat-earbuds.webp")


def _brand_image_url(brand):
    if brand.logo:
        try:
            return brand.logo.url
        except ValueError:
            pass
    if brand.static_image_path:
        return static(brand.static_image_path)
    return ""


def _number(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral() else float(value)
    return value


def _description_data(product):
    raw = product.description or ""
    has_markup = "<" in raw and ">" in raw
    if has_markup:
        rich = inline_rich_html(raw)
        plain = " ".join(strip_tags(rich).split())
        paragraphs = [mark_safe(rich)] if rich else []
    else:
        plain = raw
        paragraphs = product.description_paragraphs or ([raw] if raw else [])
    short_source = product.short_description or plain[:300]
    short = " ".join(strip_tags(short_source).split())
    return plain, short, paragraphs


def serialize_product(product):
    variants = list(product.variants.all())
    images = list(product.images.all())
    specs = list(product.specifications.all())
    default_variant = next((v for v in variants if v.is_default), variants[0] if variants else None)
    primary_image = next((i for i in images if i.role == ProductImage.Role.PRIMARY), images[0] if images else None)
    detail_image = next((i for i in images if i.role == ProductImage.Role.DETAIL), primary_image)
    gallery_images = [i for i in images if i.role in {ProductImage.Role.GALLERY, ProductImage.Role.PRIMARY}]
    if not gallery_images and primary_image:
        gallery_images = [primary_image]
    regular_price = (
        default_variant.regular_price_override
        if default_variant and default_variant.regular_price_override is not None
        else product.regular_price
    )
    price = (
        default_variant.price_override
        if default_variant and default_variant.price_override is not None
        else product.current_price
    )
    stock = sum(v.stock_quantity for v in variants if v.is_active)
    image_url = _image_url(primary_image) or static("store/images/baseus-e16.webp")
    detail_image_url = _image_url(detail_image) or image_url
    gallery_urls = [_image_url(i) for i in gallery_images if _image_url(i)] or [image_url]
    description, short_description, description_paragraphs = _description_data(product)
    return {
        "pk": product.pk,
        "id": product.public_id,
        "name": product.name,
        "slug": product.slug,
        "category": product.category.name,
        "brand": product.brand.name,
        "price": _number(price),
        "regular_price": _number(regular_price),
        "stock": stock,
        "variant": default_variant.name if default_variant else "Default",
        "sku": default_variant.sku if default_variant else "",
        "barcode": default_variant.barcode if default_variant and default_variant.barcode else "",
        "badge": product.badge,
        "badge_class": product.badge_class or "blue",
        "image_url": image_url,
        "image": image_url,
        "images": gallery_urls,
        "detail_image": detail_image_url,
        "detail_image_url": detail_image_url,
        "short_name": product.short_name or product.name,
        "subtitle": product.subtitle,
        "description": description,
        "short_description": short_description,
        "description_paragraphs": description_paragraphs,
        "features": product.features or [],
        "specifications": [{"name": s.name, "value": s.value} for s in specs],
        "variants": [
            {
                "id": v.pk,
                "name": v.name,
                "symbol": v.symbol,
                "sku": v.sku,
                "barcode": v.barcode or "",
                "price": _number(v.price_override if v.price_override is not None else product.current_price),
                "regular_price": _number(
                    v.regular_price_override if v.regular_price_override is not None else product.regular_price
                ),
                "stock": v.stock_quantity,
                "is_default": v.is_default,
            }
            for v in variants
            if v.is_active
        ],
        "box_contents": product.box_contents or [],
        "review_score": str(product.review_score.normalize()) if product.review_score else "0",
        "review_count": str(product.review_count),
        "rating": f"{product.review_score} ({product.review_count})",
        "detail_badge": product.detail_badge or product.badge,
        "detail_regular_price": _number(product.regular_price),
        "reviews": product.reviews or [],
        "questions": product.questions or [],
        "status": product.get_status_display(),
        "is_featured": product.is_featured,
        "is_new_arrival": product.is_new_arrival,
        "created_at": product.created_at,
        "updated_at": product.updated_at,
    }


def serialize_admin_product(product):
    data = serialize_product(product)
    return {
        "id": product.pk,
        "public_id": product.public_id,
        "name": data["name"],
        "sku": data["sku"],
        "barcode": data["barcode"],
        "category": data["category"],
        "brand": data["brand"],
        "price": data["price"],
        "regular_price": data["regular_price"],
        "stock": data["stock"],
        "status": data["status"],
        "image": data["image_url"],
        "slug": data["slug"],
        "created_at": product.created_at.isoformat(),
    }


def category_filters():
    rows = Category.objects.filter(is_active=True).annotate(
        product_count=Count("products", filter=Q(products__status=Product.Status.ACTIVE), distinct=True)
    ).order_by("sort_order", "name")
    return [
        {
            "id": row.pk,
            "name": row.name,
            "slug": row.slug,
            "image_url": _category_image_url(row),
            "image": _category_image_url(row),
            "count": row.product_count,
        }
        for row in rows
    ]


def brand_filters():
    rows = Brand.objects.filter(is_active=True).annotate(
        product_count=Count("products", filter=Q(products__status=Product.Status.ACTIVE), distinct=True)
    ).order_by("sort_order", "name")
    return [
        {
            "id": row.pk,
            "name": row.name,
            "slug": row.slug,
            "image_url": _brand_image_url(row),
            "count": row.product_count,
        }
        for row in rows
    ]
