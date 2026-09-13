from django.db import transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from catalog.models import Product, ProductOption, ProductOptionValue, ProductVariant
from catalog.variant_forms import ProductOptionForm, ProductOptionValueForm, StructuredProductVariantForm
from .context import page_context


NOTICE_TEXT = {
    "saved": "Variant saved successfully.",
    "deleted": "Variant deleted successfully.",
    "deactivated-used": "This variant has business history, so it was deactivated instead of deleted.",
    "option-saved": "Product option saved successfully.",
    "value-saved": "Option value saved successfully.",
    "option-deleted": "Product option deleted successfully.",
    "value-deleted": "Option value deleted successfully.",
}
ERROR_TEXT = {
    "last-variant": "A product must keep at least one variant/SKU. Create another variant before deleting this one.",
    "last-active-variant": "A product must keep at least one active variant/SKU. Activate or create another variant first.",
    "option-used": "This option is already used by a variant combination and cannot be deleted.",
    "value-used": "This option value is already used by a variant combination and cannot be deleted.",
}


def _product_id(request):
    value = request.GET.get("product") or request.POST.get("product_filter")
    try:
        return int(value) if value else None
    except (TypeError, ValueError):
        return None


def _context(request, product_id=None):
    context = page_context("products")
    context["catalog_database"] = True
    context["catalog_products"] = Product.objects.order_by("name")
    context["product_filter"] = product_id
    context["catalog_notice"] = NOTICE_TEXT.get(request.GET.get("notice", ""), "")
    context["catalog_error"] = ERROR_TEXT.get(request.GET.get("error", ""), "")
    return context


def _variant_usage_reasons(variant):
    reasons = []
    balances = variant.inventory_balances.filter(Q(on_hand__gt=0) | Q(reserved_quantity__gt=0))
    if balances.exists():
        reasons.append("stock")
    if variant.stock_movements.exists():
        reasons.append("inventory history")
    if variant.purchase_items.exists():
        reasons.append("purchase history")
    if variant.sales_order_items.exists():
        reasons.append("sales history")
    if variant.serialized_units.exists():
        reasons.append("serial/IMEI history")
    return reasons


def _ensure_default_variant(product):
    current = product.variants.filter(is_default=True, is_active=True).order_by("id").first()
    if current:
        return current
    replacement = product.variants.filter(is_active=True).order_by("id").first()
    if not replacement:
        return None
    product.variants.update(is_default=False)
    replacement.is_default = True
    replacement.save(update_fields=["is_default", "updated_at"])
    return replacement


def variants(request):
    product_id = _product_id(request)
    if request.method == "POST" and request.POST.get("action") == "delete":
        variant = get_object_or_404(
            ProductVariant.objects.select_related("product"),
            pk=request.POST.get("variant_id"),
        )
        product = variant.product
        if product.variants.count() <= 1:
            return redirect(reverse("backoffice:catalog_variants") + f"?product={product.pk}&error=last-variant")
        if variant.is_active and not product.variants.filter(is_active=True).exclude(pk=variant.pk).exists():
            return redirect(reverse("backoffice:catalog_variants") + f"?product={product.pk}&error=last-active-variant")

        usage = _variant_usage_reasons(variant)
        if usage:
            with transaction.atomic():
                variant.is_active = False
                variant.is_default = False
                variant.save(update_fields=["is_active", "is_default", "updated_at"])
                _ensure_default_variant(product)
            return redirect(reverse("backoffice:catalog_variants") + f"?product={product.pk}&notice=deactivated-used")

        was_default = variant.is_default
        variant.delete()
        if was_default:
            _ensure_default_variant(product)
        return redirect(reverse("backoffice:catalog_variants") + f"?product={product.pk}&notice=deleted")

    context = _context(request, product_id)
    qs = ProductVariant.objects.select_related(
        "product", "product__category", "product__brand"
    ).prefetch_related(
        "option_selections__option", "option_selections__value"
    ).order_by("product__name", "-is_default", "id")
    if product_id:
        qs = qs.filter(product_id=product_id)
    context["variants"] = qs
    return render(request, "backoffice/pages/catalog/variants.html", context)


def variant_form(request):
    variant_id = request.GET.get("id")
    product_id = _product_id(request)
    instance = get_object_or_404(ProductVariant, pk=variant_id) if variant_id else None
    if instance:
        product_id = instance.product_id

    form = StructuredProductVariantForm(
        request.POST or None,
        instance=instance,
        product_id=product_id,
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            variant = form.save(commit=False)
            product = variant.product
            if variant.is_default:
                product.variants.exclude(pk=variant.pk).update(is_default=False)
            variant.save()
            form.save_option_selections(variant)
            _ensure_default_variant(product)
        return redirect(reverse("backoffice:catalog_variants") + f"?product={variant.product_id}&notice=saved")

    context = _context(request, product_id)
    context.update(
        form=form,
        is_edit=bool(instance),
        variant_obj=instance,
        selected_product=Product.objects.filter(pk=product_id).first() if product_id else None,
    )
    return render(request, "backoffice/pages/catalog/variant_form.html", context)


def variant_options(request):
    product_id = _product_id(request)
    option_form = ProductOptionForm(product_id=product_id)
    value_form = ProductOptionValueForm(product_id=product_id)

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "add_option":
            option_form = ProductOptionForm(request.POST, product_id=product_id)
            if option_form.is_valid():
                option = option_form.save()
                return redirect(reverse("backoffice:catalog_variant_options") + f"?product={option.product_id}&notice=option-saved")
        elif action == "add_value":
            value_form = ProductOptionValueForm(request.POST, product_id=product_id)
            if value_form.is_valid():
                value = value_form.save()
                return redirect(reverse("backoffice:catalog_variant_options") + f"?product={value.option.product_id}&notice=value-saved")
        elif action == "delete_option":
            option = get_object_or_404(ProductOption, pk=request.POST.get("option_id"))
            product_id = option.product_id
            try:
                option.delete()
            except ProtectedError:
                return redirect(reverse("backoffice:catalog_variant_options") + f"?product={product_id}&error=option-used")
            return redirect(reverse("backoffice:catalog_variant_options") + f"?product={product_id}&notice=option-deleted")
        elif action == "delete_value":
            value = get_object_or_404(ProductOptionValue.objects.select_related("option"), pk=request.POST.get("value_id"))
            product_id = value.option.product_id
            try:
                value.delete()
            except ProtectedError:
                return redirect(reverse("backoffice:catalog_variant_options") + f"?product={product_id}&error=value-used")
            return redirect(reverse("backoffice:catalog_variant_options") + f"?product={product_id}&notice=value-deleted")

    context = _context(request, product_id)
    options = ProductOption.objects.select_related("product").prefetch_related("values").order_by(
        "product__name", "sort_order", "id"
    )
    if product_id:
        options = options.filter(product_id=product_id)
    context.update(
        options=options,
        option_form=option_form,
        value_form=value_form,
    )
    return render(request, "backoffice/pages/catalog/variant_options.html", context)
