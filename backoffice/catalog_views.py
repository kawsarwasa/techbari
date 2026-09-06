from copy import deepcopy

from django.core.exceptions import ValidationError
from django.db.models import Count, IntegerField, Sum, Value
from django.db.models.deletion import ProtectedError
from django.db.models.functions import Coalesce
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from catalog.forms import BrandForm, CategoryForm, ProductForm, VARIANT_CHOICES, validate_product_images
from catalog.models import Brand, Category, Product
from catalog.presentation import catalog_queryset, serialize_admin_product, serialize_product
from catalog.services import save_product_bundle
from .context import page_context

DEFAULT_SPECS = [{"name": "Bluetooth Version", "value": "5.3"}, {"name": "Driver Size", "value": "13mm"}, {"name": "Playtime", "value": "Up to 30 hours"}, {"name": "Charging Port", "value": "USB Type-C"}, {"name": "Noise Cancellation", "value": "AI ENC"}, {"name": "Water Resistance", "value": "IPX4"}]
NOTICE_TEXT = {"created": "Product created successfully.", "updated": "Product updated successfully.", "deleted": "Product deleted successfully.", "archived": "Product archived successfully.", "category-saved": "Category saved successfully.", "category-deleted": "Category deleted successfully.", "brand-saved": "Brand saved successfully.", "brand-deleted": "Brand deleted successfully."}
ERROR_TEXT = {"category-used": "This category is used by products and cannot be deleted yet.", "brand-used": "This brand is used by products and cannot be deleted yet."}


def _base_context(page_name, request):
    context = page_context(page_name)
    context["catalog_database"] = True
    context["catalog_notice"] = NOTICE_TEXT.get(request.GET.get("notice", ""), "")
    context["catalog_error"] = ERROR_TEXT.get(request.GET.get("error", ""), "")
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
                product.delete()
                return redirect(reverse("backoffice:products") + "?notice=deleted")
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
    context.update(form=form, product_obj=product, is_edit=bool(product), variant_choices=VARIANT_CHOICES, selected_variants=list(form["variant_names"].value() or []), specifications=_posted_specs(request, [{"name": s.name, "value": s.value} for s in product.specifications.all()] if product else DEFAULT_SPECS), product_images=serialize_product(product)["images"] if product else [])
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
