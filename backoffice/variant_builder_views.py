from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse

from catalog.models import Product, ProductVariant, VariantAttribute, VariantPreset
from catalog.variant_services import VariantGenerationError, generate_variant_combinations, variant_signature
from inventory.services import InventoryError
from .context import page_context


NOTICE_TEXT = {
    "generated": "Selected variant combinations generated successfully.",
    "bulk-saved": "Variant pricing, low-stock alerts and status updated successfully.",
    "stock-adjusted": "Inventory stock adjustment posted successfully.",
}


def _product_id(request):
    value = request.GET.get("product") or request.POST.get("product")
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
    return context


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


def _decimal_or_none(raw, label):
    value = str(raw or "").strip()
    if value == "":
        return None
    try:
        amount = Decimal(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {label}.") from exc
    if amount < 0:
        raise ValueError(f"{label} cannot be negative.")
    return amount


def _int_nonnegative(raw, label, default=0):
    try:
        value = int(str(raw if raw not in (None, "") else default))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {label}.") from exc
    if value < 0:
        raise ValueError(f"{label} cannot be negative.")
    return value


def _bulk_save_variants(request, product):
    variant_ids = []
    for raw in request.POST.getlist("variant_ids"):
        if str(raw).isdigit():
            variant_ids.append(int(raw))
    variants = list(product.variants.filter(pk__in=variant_ids).order_by("id"))
    if len(variants) != len(set(variant_ids)):
        raise ValueError("One or more variant rows are invalid.")

    active_ids = {
        int(raw.split("_", 1)[1])
        for raw in request.POST.keys()
        if raw.startswith("active_") and raw.split("_", 1)[1].isdigit()
    }
    default_raw = request.POST.get("default_variant_id")
    default_id = int(default_raw) if str(default_raw or "").isdigit() else None

    if variants and not any(variant.pk in active_ids for variant in variants):
        untouched_active = product.variants.filter(is_active=True).exclude(pk__in=variant_ids).exists()
        if not untouched_active:
            raise ValueError("A product must keep at least one active SKU.")
    if default_id and default_id not in active_ids:
        raise ValueError("The default SKU must stay active.")

    with transaction.atomic():
        if default_id:
            product.variants.update(is_default=False)
        for variant in variants:
            regular = _decimal_or_none(request.POST.get(f"regular_{variant.pk}"), "regular price")
            selling = _decimal_or_none(request.POST.get(f"price_{variant.pk}"), "selling price")
            effective_regular = regular if regular is not None else product.regular_price
            if selling is not None and effective_regular is not None and selling > effective_regular:
                raise ValueError(
                    f"Selling price cannot exceed the effective regular price for {variant.sku}."
                )
            variant.regular_price_override = regular
            variant.price_override = selling
            # Stock is intentionally inventory-owned. Builder submissions must never
            # mutate ProductVariant.stock_quantity, even if a stale/malicious client
            # still posts a stock_<id> field.
            variant.low_stock_alert = _int_nonnegative(request.POST.get(f"low_{variant.pk}"), "low stock alert", 5)
            variant.is_active = variant.pk in active_ids
            variant.is_default = bool(default_id and variant.pk == default_id)
            variant.save()
        _ensure_default_variant(product)


def variant_builder(request):
    product_id = _product_id(request)
    preset_id = request.GET.get("preset") or request.POST.get("preset")
    product = Product.objects.filter(pk=product_id).first() if product_id else None
    generator_error = ""

    if request.method == "POST" and product:
        action = request.POST.get("action", "")
        if action == "generate":
            try:
                result = generate_variant_combinations(
                    product=product,
                    value_ids=request.POST.getlist("value_ids"),
                    selected_signatures=request.POST.getlist("selected_signatures"),
                )
                params = (
                    f"?product={product.pk}&notice=generated"
                    f"&created={result['created']}&reused={result['reused']}&skipped={result['skipped']}"
                )
                if preset_id:
                    params += f"&preset={preset_id}"
                return redirect(reverse("backoffice:catalog_variant_builder") + params)
            except VariantGenerationError as exc:
                generator_error = " ".join(str(value) for value in getattr(exc, "messages", [str(exc)]))
        elif action == "bulk_save":
            try:
                _bulk_save_variants(request, product)
                params = f"?product={product.pk}&notice=bulk-saved"
                if preset_id:
                    params += f"&preset={preset_id}"
                return redirect(reverse("backoffice:catalog_variant_builder") + params)
            except (ValueError, InventoryError) as exc:
                messages = getattr(exc, "messages", None)
                generator_error = "; ".join(str(value) for value in messages) if messages else str(exc)

    presets = list(
        VariantPreset.objects.filter(is_active=True)
        .prefetch_related("attribute_links__attribute")
        .order_by("sort_order", "name")
    )
    selected_preset = None
    if str(preset_id or "").isdigit():
        selected_preset = next((preset for preset in presets if preset.pk == int(preset_id)), None)

    attributes = list(
        VariantAttribute.objects.filter(is_active=True)
        .prefetch_related("values")
        .order_by("sort_order", "name")
    )
    preset_attribute_ids = []
    if selected_preset:
        preset_attribute_ids = list(
            selected_preset.attribute_links.order_by("sort_order", "id").values_list("attribute_id", flat=True)
        )

    variants_qs = ProductVariant.objects.none()
    existing_value_ids = set()
    existing_combinations = []
    if product:
        variants_qs = product.variants.prefetch_related(
            "variant_values__value__attribute"
        ).order_by("-is_default", "id")
        variants = list(variants_qs)
        for variant in variants:
            signature = variant_signature(variant)
            if not signature:
                continue
            existing_value_ids.update(signature)
            existing_combinations.append(
                {
                    "signature": ",".join(str(value_id) for value_id in signature),
                    "name": variant.display_name,
                    "sku": variant.sku,
                    "active": variant.is_active,
                }
            )
        variants_qs = variants

    context = _context(request, product_id)
    context.update(
        selected_product=product,
        presets=presets,
        selected_preset=selected_preset,
        preset_attribute_ids=preset_attribute_ids,
        builder_attributes=attributes,
        existing_value_ids=existing_value_ids,
        existing_combinations=existing_combinations,
        builder_variants=variants_qs,
        generator_error=generator_error,
        generation_created=request.GET.get("created", ""),
        generation_reused=request.GET.get("reused", ""),
        generation_skipped=request.GET.get("skipped", ""),
    )
    return render(request, "backoffice/pages/catalog/variant_builder.html", context)
