from copy import deepcopy

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, IntegerField, Sum, Value
from django.db.models.deletion import ProtectedError
from django.db.models.functions import Coalesce
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from catalog.forms import (
    BrandForm,
    CategoryForm,
    ProductForm,
    ProductImageForm,
    ProductSpecificationForm,
    ProductVariantForm,
    validate_product_images,
)
from catalog.models import Brand, Category, Product, ProductImage, ProductSpecification, ProductVariant
from catalog.presentation import catalog_queryset, serialize_admin_product, serialize_product
from catalog.services import save_product_bundle
from .context import page_context

DEFAULT_SPECS = [
    {"name": "Bluetooth Version", "value": "5.3"},
    {"name": "Driver Size", "value": "13mm"},
    {"name": "Playtime", "value": "Up to 30 hours"},
    {"name": "Charging Port", "value": "USB Type-C"},
    {"name": "Noise Cancellation", "value": "AI ENC"},
    {"name": "Water Resistance", "value": "IPX4"},
]
NOTICE_TEXT = {
    "created": "Product created successfully.",
    "updated": "Product updated successfully.",
    "deleted": "Product deleted successfully.",
    "archived": "Product archived successfully.",
    "category-saved": "Category saved successfully.",
    "category-deleted": "Category deleted successfully.",
    "brand-saved": "Brand saved successfully.",
    "brand-deleted": "Brand deleted successfully.",
}
ERROR_TEXT = {
    "category-used": "This category is used by products and cannot be deleted yet.",
    "brand-used": "This brand is used by products and cannot be deleted yet.",
}


def _base_context(page_name, request):
    context = page_context(page_name)
    context["catalog_database"] = True
    context["catalog_notice"] = NOTICE_TEXT.get(request.GET.get("notice", ""), "")
    context["catalog_error"] = ERROR_TEXT.get(request.GET.get("error", ""), "")
    return context


def _catalog_management_context(request, notice_map=None, error_map=None):
    context = _base_context("products", request)
    notice_map = notice_map or {}
    error_map = error_map or {}
    code = request.GET.get("notice", "")
    error_code = request.GET.get("error", "")
    context["catalog_notice"] = notice_map.get(code, context.get("catalog_notice", ""))
    context["catalog_error"] = error_map.get(error_code, context.get("catalog_error", ""))
    context["catalog_products"] = Product.objects.order_by("name")
    return context


def _replace_stat_values(stats, rows):
    result = deepcopy(stats)
    for stat, data in zip(result, rows):
        stat.update(data)
    return result


def _product_statistics(context):
    stock_qs = Product.objects.annotate(total_stock=Coalesce(Sum("variants__stock_quantity"), Value(0), output_field=IntegerField()))
    rows = [
        {"label": "Total Products", "value": str(Product.objects.count()), "trend": "Live", "trend_class": "up"},
        {"label": "Active Products", "value": str(Product.objects.filter(status=Product.Status.ACTIVE).count()), "trend": "Live", "trend_class": "up"},
        {"label": "Out of Stock", "value": str(stock_qs.filter(total_stock=0).count()), "trend": "Live", "trend_class": "up"},
        {"label": "Draft Products", "value": str(Product.objects.filter(status=Product.Status.DRAFT).count()), "trend": "Live", "trend_class": "up"},
    ]
    context["statistics"] = _replace_stat_values(context["statistics"], rows)


def products(request):
    if request.method == "POST":
        action = request.POST.get("action", "")
        product_id = request.POST.get("product_id")
        ids = [value for value in request.POST.getlist("product_ids") if value]
        if action in {"delete", "archive"} and product_id:
            product = get_object_or_404(Product, pk=product_id)
            if action == "delete":
                product.delete(); return redirect(reverse("backoffice:products") + "?notice=deleted")
            product.status = Product.Status.ARCHIVED
            product.save(update_fields=["status", "updated_at"])
            return redirect(reverse("backoffice:products") + "?notice=archived")
        if action.startswith("bulk_") and ids:
            qs = Product.objects.filter(pk__in=ids)
            if action == "bulk_delete": qs.delete()
            elif action == "bulk_archive": qs.update(status=Product.Status.ARCHIVED)
            elif action == "bulk_activate": qs.update(status=Product.Status.ACTIVE)
            elif action == "bulk_draft": qs.update(status=Product.Status.DRAFT)
            return redirect("backoffice:products")
    context = _base_context("products", request)
    rows = [serialize_admin_product(product) for product in catalog_queryset(include_inactive=True)]
    context["products"] = rows
    context["catalog_categories"] = Category.objects.order_by("name")
    context["admin_data"]["seeds"]["products"] = rows
    _product_statistics(context)
    return render(request, "backoffice/pages/products/products.html", context)


def _posted_specs(request, fallback):
    if request.method != "POST": return fallback
    names, values = request.POST.getlist("spec_name"), request.POST.getlist("spec_value")
    rows = [{"name": name, "value": value} for name, value in zip(names, values) if name or value]
    return rows or fallback


def _product_form_context(page_name, request, form, product=None):
    context = _base_context(page_name, request)
    context.update(form=form, product_obj=product, is_edit=bool(product), specifications=_posted_specs(request, [{"name": s.name, "value": s.value} for s in product.specifications.all()] if product else DEFAULT_SPECS), product_images=serialize_product(product)["images"] if product else [])
    return context


def product_add(request):
    form = ProductForm(request.POST or None)
    if request.method == "POST":
        image_files = request.FILES.getlist("images")
        try: validate_product_images(image_files)
        except ValidationError as exc: form.add_error(None, exc)
        if form.is_valid():
            save_product_bundle(form, image_files, request.POST.getlist("spec_name"), request.POST.getlist("spec_value"))
            return redirect(reverse("backoffice:products") + "?notice=created")
    return render(request, "backoffice/pages/products/product_add.html", _product_form_context("product_add", request, form))


def product_edit(request):
    try: product_id = int(request.GET.get("id", ""))
    except (TypeError, ValueError): raise Http404("Product not found")
    product = get_object_or_404(catalog_queryset(include_inactive=True), pk=product_id)
    form = ProductForm(request.POST or None, instance=product)
    if request.method == "POST":
        image_files = request.FILES.getlist("images")
        try:
            validate_product_images(image_files)
            if product.images.count() + len(image_files) > 8: raise ValidationError("A product can have a maximum of 8 images in total.")
        except ValidationError as exc: form.add_error(None, exc)
        if form.is_valid():
            save_product_bundle(form, image_files, request.POST.getlist("spec_name"), request.POST.getlist("spec_value"))
            return redirect(reverse("backoffice:products") + "?notice=updated")
    return render(request, "backoffice/pages/products/product_edit.html", _product_form_context("product_edit", request, form, product))


def categories(request):
    if request.method == "POST" and request.POST.get("action") == "delete":
        category = get_object_or_404(Category, pk=request.POST.get("category_id"))
        try: category.delete()
        except ProtectedError: return redirect(reverse("backoffice:categories") + "?error=category-used")
        return redirect(reverse("backoffice:categories") + "?notice=category-deleted")
    context = _base_context("categories", request)
    queryset = Category.objects.select_related("parent").annotate(product_count=Count("products")).order_by("sort_order", "name")
    rows = [{"id": row.pk, "name": row.name, "slug": row.slug, "parent": row.parent.name if row.parent else "—", "products": row.product_count, "status": "Active" if row.is_active else "Inactive"} for row in queryset]
    context["categories"] = rows
    active = sum(1 for row in rows if row["status"] == "Active")
    parent_count = sum(1 for row in queryset if row.parent_id is None)
    context["statistics"] = _replace_stat_values(context["statistics"], [{"label": "Total Categories", "value": str(len(rows)), "trend": "Live"}, {"label": "Active Categories", "value": str(active), "trend": "Live"}, {"label": "Top-level Categories", "value": str(parent_count), "trend": "Live"}, {"label": "Inactive Categories", "value": str(len(rows)-active), "trend": "Live"}])
    return render(request, "backoffice/pages/categories/categories.html", context)


def category_add(request):
    category_id = request.GET.get("id")
    instance = get_object_or_404(Category, pk=category_id) if category_id else None
    form = CategoryForm(request.POST or None, request.FILES or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save(); return redirect(reverse("backoffice:categories") + "?notice=category-saved")
    context = _base_context("category_add", request); context.update(form=form, is_edit=bool(instance), category_obj=instance)
    return render(request, "backoffice/pages/categories/category_add.html", context)


def brands(request):
    if request.method == "POST" and request.POST.get("action") == "delete":
        brand = get_object_or_404(Brand, pk=request.POST.get("brand_id"))
        try: brand.delete()
        except ProtectedError: return redirect(reverse("backoffice:brands") + "?error=brand-used")
        return redirect(reverse("backoffice:brands") + "?notice=brand-deleted")
    context = _base_context("brands", request)
    queryset = Brand.objects.annotate(product_count=Count("products")).order_by("sort_order", "name")
    rows = [{"id": row.pk, "name": row.name, "slug": row.slug, "products": row.product_count, "featured": "Yes" if row.is_featured else "No", "status": "Active" if row.is_active else "Inactive"} for row in queryset]
    context["brands"] = rows
    active = sum(1 for row in rows if row["status"] == "Active"); featured = sum(1 for row in rows if row["featured"] == "Yes")
    context["statistics"] = _replace_stat_values(context["statistics"], [{"label": "Total Brands", "value": str(len(rows)), "trend": "Live"}, {"label": "Active Brands", "value": str(active), "trend": "Live"}, {"label": "Featured Brands", "value": str(featured), "trend": "Live"}, {"label": "Inactive Brands", "value": str(len(rows)-active), "trend": "Live"}])
    return render(request, "backoffice/pages/brands/brands.html", context)


def brand_add(request):
    brand_id = request.GET.get("id")
    instance = get_object_or_404(Brand, pk=brand_id) if brand_id else None
    form = BrandForm(request.POST or None, request.FILES or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save(); return redirect(reverse("backoffice:brands") + "?notice=brand-saved")
    context = _base_context("brand_add", request); context.update(form=form, is_edit=bool(instance), brand_obj=instance)
    return render(request, "backoffice/pages/brands/brand_add.html", context)


def _filtered_product_id(request):
    value = request.GET.get("product") or request.POST.get("product_filter")
    try: return int(value) if value else None
    except (TypeError, ValueError): return None


def variants(request):
    notice_map = {"saved": "Variant saved successfully.", "deleted": "Variant deleted successfully."}
    error_map = {"last-variant": "A product must keep at least one variant/SKU. Create another variant before deleting this one."}
    if request.method == "POST" and request.POST.get("action") == "delete":
        variant = get_object_or_404(ProductVariant.objects.select_related("product"), pk=request.POST.get("variant_id"))
        product = variant.product
        if product.variants.count() <= 1:
            return redirect(reverse("backoffice:catalog_variants") + f"?product={product.pk}&error=last-variant")
        was_default = variant.is_default
        variant.delete()
        if was_default:
            replacement = product.variants.filter(is_active=True).order_by("id").first() or product.variants.order_by("id").first()
            if replacement:
                product.variants.update(is_default=False)
                replacement.is_default = True
                replacement.save(update_fields=["is_default", "updated_at"])
        return redirect(reverse("backoffice:catalog_variants") + f"?product={product.pk}&notice=deleted")
    context = _catalog_management_context(request, notice_map, error_map)
    product_id = _filtered_product_id(request)
    qs = ProductVariant.objects.select_related("product", "product__category", "product__brand").order_by("product__name", "-is_default", "id")
    if product_id: qs = qs.filter(product_id=product_id)
    context["variants"] = qs; context["product_filter"] = product_id
    return render(request, "backoffice/pages/catalog/variants.html", context)


def variant_form(request):
    variant_id = request.GET.get("id")
    product_id = _filtered_product_id(request)
    instance = get_object_or_404(ProductVariant, pk=variant_id) if variant_id else None
    if instance: product_id = instance.product_id
    form = ProductVariantForm(request.POST or None, instance=instance, product_id=product_id)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            variant = form.save(commit=False)
            product = variant.product
            if variant.is_default: product.variants.exclude(pk=variant.pk).update(is_default=False)
            variant.save()
            if not product.variants.filter(is_default=True).exists():
                replacement = product.variants.filter(is_active=True).order_by("id").first() or variant
                replacement.is_default = True
                replacement.save(update_fields=["is_default", "updated_at"])
        return redirect(reverse("backoffice:catalog_variants") + f"?product={variant.product_id}&notice=saved")
    context = _catalog_management_context(request); context.update(form=form, is_edit=bool(instance), variant_obj=instance, product_filter=product_id)
    return render(request, "backoffice/pages/catalog/variant_form.html", context)


def _image_preview_url(image):
    if image.image:
        try: return image.image.url
        except ValueError: pass
    if image.static_path:
        from django.templatetags.static import static
        return static(image.static_path)
    return ""


def _ensure_product_primary_image(product, preferred=None):
    if product.images.filter(role=ProductImage.Role.PRIMARY).exists(): return
    candidate = product.images.exclude(pk=preferred.pk if preferred else None).order_by("sort_order", "id").first() or preferred or product.images.order_by("sort_order", "id").first()
    if candidate:
        candidate.role = ProductImage.Role.PRIMARY
        candidate.save(update_fields=["role"])


def media(request):
    notice_map = {"saved": "Product image saved successfully.", "deleted": "Product image deleted successfully.", "primary": "Primary image updated.", "detail": "Detail image updated."}
    if request.method == "POST":
        image = get_object_or_404(ProductImage.objects.select_related("product"), pk=request.POST.get("image_id"))
        action = request.POST.get("action")
        product = image.product
        if action == "delete":
            was_primary = image.role == ProductImage.Role.PRIMARY
            if image.image: image.image.delete(save=False)
            image.delete()
            if was_primary:
                replacement = product.images.order_by("sort_order", "id").first()
                if replacement:
                    replacement.role = ProductImage.Role.PRIMARY
                    replacement.save(update_fields=["role"])
            return redirect(reverse("backoffice:catalog_media") + f"?product={product.pk}&notice=deleted")
        if action == "set_primary":
            product.images.filter(role=ProductImage.Role.PRIMARY).exclude(pk=image.pk).update(role=ProductImage.Role.GALLERY)
            image.role = ProductImage.Role.PRIMARY; image.save(update_fields=["role"])
            return redirect(reverse("backoffice:catalog_media") + f"?product={product.pk}&notice=primary")
        if action == "set_detail":
            product.images.filter(role=ProductImage.Role.DETAIL).exclude(pk=image.pk).update(role=ProductImage.Role.GALLERY)
            image.role = ProductImage.Role.DETAIL; image.save(update_fields=["role"])
            _ensure_product_primary_image(product, preferred=image)
            return redirect(reverse("backoffice:catalog_media") + f"?product={product.pk}&notice=detail")
    context = _catalog_management_context(request, notice_map)
    product_id = _filtered_product_id(request)
    qs = ProductImage.objects.select_related("product").order_by("product__name", "sort_order", "id")
    if product_id: qs = qs.filter(product_id=product_id)
    context["media_rows"] = [{"obj": image, "preview": _image_preview_url(image)} for image in qs]
    context["product_filter"] = product_id
    return render(request, "backoffice/pages/catalog/media.html", context)


def media_form(request):
    image_id = request.GET.get("id")
    product_id = _filtered_product_id(request)
    instance = get_object_or_404(ProductImage, pk=image_id) if image_id else None
    if instance: product_id = instance.product_id
    form = ProductImageForm(request.POST or None, request.FILES or None, instance=instance, product_id=product_id)
    if request.method == "POST" and form.is_valid():
        product = form.cleaned_data["product"]
        existing_count = product.images.exclude(pk=instance.pk if instance else None).count()
        if not instance and existing_count >= 8:
            form.add_error("image", "A product can have a maximum of 8 images.")
        else:
            with transaction.atomic():
                image = form.save(commit=False)
                if image.role in {ProductImage.Role.PRIMARY, ProductImage.Role.DETAIL}:
                    product.images.filter(role=image.role).exclude(pk=image.pk).update(role=ProductImage.Role.GALLERY)
                image.save()
                _ensure_product_primary_image(product, preferred=image)
            return redirect(reverse("backoffice:catalog_media") + f"?product={image.product_id}&notice=saved")
    context = _catalog_management_context(request); context.update(form=form, is_edit=bool(instance), image_obj=instance, image_preview=_image_preview_url(instance) if instance else "", product_filter=product_id)
    return render(request, "backoffice/pages/catalog/media_form.html", context)


def specifications(request):
    notice_map = {"saved": "Specification saved successfully.", "deleted": "Specification deleted successfully."}
    if request.method == "POST" and request.POST.get("action") == "delete":
        specification = get_object_or_404(ProductSpecification.objects.select_related("product"), pk=request.POST.get("specification_id"))
        product_id = specification.product_id
        specification.delete()
        return redirect(reverse("backoffice:catalog_specifications") + f"?product={product_id}&notice=deleted")
    context = _catalog_management_context(request, notice_map)
    product_id = _filtered_product_id(request)
    qs = ProductSpecification.objects.select_related("product").order_by("product__name", "sort_order", "id")
    if product_id: qs = qs.filter(product_id=product_id)
    context["specifications"] = qs; context["product_filter"] = product_id
    return render(request, "backoffice/pages/catalog/specifications.html", context)


def specification_form(request):
    specification_id = request.GET.get("id")
    product_id = _filtered_product_id(request)
    instance = get_object_or_404(ProductSpecification, pk=specification_id) if specification_id else None
    if instance: product_id = instance.product_id
    form = ProductSpecificationForm(request.POST or None, instance=instance, product_id=product_id)
    if request.method == "POST" and form.is_valid():
        specification = form.save()
        return redirect(reverse("backoffice:catalog_specifications") + f"?product={specification.product_id}&notice=saved")
    context = _catalog_management_context(request); context.update(form=form, is_edit=bool(instance), specification_obj=instance, product_filter=product_id)
    return render(request, "backoffice/pages/catalog/specification_form.html", context)
