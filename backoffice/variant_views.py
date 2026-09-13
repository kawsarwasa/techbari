from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from catalog.models import (
    Product,
    ProductVariant,
    VariantAttribute,
    VariantAttributeValue,
    VariantPreset,
)
from catalog.variant_forms import (
    StructuredProductVariantForm,
    VariantAttributeForm,
    VariantAttributeValueForm,
    VariantPresetForm,
)
from catalog.variant_services import VariantGenerationError, generate_variant_combinations, variant_usage_reasons
from .context import page_context


NOTICE_TEXT = {
    "saved": "Variant saved successfully.",
    "deleted": "Variant deleted successfully.",
    "deactivated-used": "This variant has business history, so it was deactivated instead of deleted.",
    "attribute-saved": "Variant attribute saved successfully.",
    "value-saved": "Attribute value saved successfully.",
    "attribute-toggled": "Variant attribute status updated.",
    "value-toggled": "Attribute value status updated.",
    "preset-saved": "Variant preset saved successfully.",
    "preset-toggled": "Variant preset status updated.",
    "generated": "Variant combinations generated successfully.",
    "bulk-saved": "Variant pricing, stock and status updated successfully.",
}
ERROR_TEXT = {
    "last-variant": "A product must keep at least one variant/SKU. Create another variant before deleting this one.",
    "last-active-variant": "A product must keep at least one active variant/SKU. Activate or create another variant first.",
}


def _product_id(request):
    value = request.GET.get("product") or request.POST.get("product_filter") or request.POST.get("product")
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


def _protect_used_variant_identity(form, instance):
    if not instance or not variant_usage_reasons(instance):
        return

    selected_values = form.cleaned_data.get("attribute_values")
    selected_ids = set(selected_values.values_list("id", flat=True)) if selected_values is not None else set()
    existing_ids = set(instance.variant_values.values_list("value_id", flat=True))
    intended_name = (form.cleaned_data.get("name") or "").strip()
    intended_sku = (form.cleaned_data.get("sku") or "").strip()

    if selected_ids != existing_ids:
        form.add_error(
            "attribute_values",
            "This SKU already has stock or business history. Its attribute combination cannot be changed; create a new variant instead.",
        )
    elif intended_name != instance.name:
        form.add_error(
            "name",
            "This SKU already has stock or business history. Its variant identity cannot be renamed; create a new variant instead.",
        )
    if intended_sku != instance.sku:
        form.add_error(
            "sku",
            "This SKU already has stock or business history and cannot be changed. Create a new variant instead.",
        )


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

        usage = variant_usage_reasons(variant)
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
        "variant_values__value__attribute"
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
        _protect_used_variant_identity(form, instance)
        if instance and instance.is_active and not form.cleaned_data.get("is_active"):
            if not instance.product.variants.filter(is_active=True).exclude(pk=instance.pk).exists():
                form.add_error("is_active", "A product must keep at least one active variant/SKU.")

        if not form.errors:
            with transaction.atomic():
                variant = form.save(commit=False)
                product = variant.product
                if variant.is_default:
                    product.variants.exclude(pk=variant.pk).update(is_default=False)
                variant.save()
                form.save_attribute_values(variant)
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


def variant_attributes(request):
    edit_attribute = None
    edit_value = None
    if request.GET.get("attribute"):
        edit_attribute = get_object_or_404(VariantAttribute, pk=request.GET.get("attribute"))
    if request.GET.get("value"):
        edit_value = get_object_or_404(VariantAttributeValue.objects.select_related("attribute"), pk=request.GET.get("value"))

    attribute_form = VariantAttributeForm(instance=edit_attribute)
    value_form = VariantAttributeValueForm(instance=edit_value, attribute_id=request.GET.get("for_attribute"))

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "save_attribute":
            instance = VariantAttribute.objects.filter(pk=request.POST.get("attribute_id")).first()
            attribute_form = VariantAttributeForm(request.POST, instance=instance)
            if attribute_form.is_valid():
                attribute_form.save()
                return redirect(reverse("backoffice:catalog_variant_attributes") + "?notice=attribute-saved")
        elif action == "save_value":
            instance = VariantAttributeValue.objects.filter(pk=request.POST.get("value_id")).first()
            value_form = VariantAttributeValueForm(request.POST, instance=instance)
            if value_form.is_valid():
                value_form.save()
                return redirect(reverse("backoffice:catalog_variant_attributes") + "?notice=value-saved")
        elif action == "toggle_attribute":
            attribute = get_object_or_404(VariantAttribute, pk=request.POST.get("attribute_id"))
            attribute.is_active = not attribute.is_active
            attribute.save(update_fields=["is_active", "updated_at"])
            return redirect(reverse("backoffice:catalog_variant_attributes") + "?notice=attribute-toggled")
        elif action == "toggle_value":
            value = get_object_or_404(VariantAttributeValue, pk=request.POST.get("value_id"))
            value.is_active = not value.is_active
            value.save(update_fields=["is_active", "updated_at"])
            return redirect(reverse("backoffice:catalog_variant_attributes") + "?notice=value-toggled")

    context = _context(request)
    context.update(
        attributes=VariantAttribute.objects.prefetch_related("values").order_by("sort_order", "name"),
        attribute_form=attribute_form,
        value_form=value_form,
        edit_attribute=edit_attribute,
        edit_value=edit_value,
    )
    return render(request, "backoffice/pages/catalog/variant_attributes.html", context)


def variant_presets(request):
    edit_preset = None
    if request.GET.get("id"):
        edit_preset = get_object_or_404(VariantPreset, pk=request.GET.get("id"))
    form = VariantPresetForm(instance=edit_preset)

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "save_preset":
            instance = VariantPreset.objects.filter(pk=request.POST.get("preset_id")).first()
            form = VariantPresetForm(request.POST, instance=instance)
            if form.is_valid():
                form.save()
                return redirect(reverse("backoffice:catalog_variant_presets") + "?notice=preset-saved")
        elif action == "toggle_preset":
            preset = get_object_or_404(VariantPreset, pk=request.POST.get("preset_id"))
            preset.is_active = not preset.is_active
            preset.save(update_fields=["is_active", "updated_at"])
            return redirect(reverse("backoffice:catalog_variant_presets") + "?notice=preset-toggled")

    presets = VariantPreset.objects.prefetch_related("attribute_links__attribute").order_by("sort_order", "name")
    context = _context(request)
    context.update(presets=presets, preset_form=form, edit_preset=edit_preset)
    return render(request, "backoffice/pages/catalog/variant_presets.html", context)


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
            if regular is not None and selling is not None and selling > regular:
                raise ValueError(f"Selling price cannot exceed regular price for {variant.sku}.")
            variant.regular_price_override = regular
            variant.price_override = selling
            variant.stock_quantity = _int_nonnegative(request.POST.get(f"stock_{variant.pk}"), "stock")
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
            except ValueError as exc:
                generator_error = str(exc)

    presets = VariantPreset.objects.filter(is_active=True).prefetch_related("attribute_links__attribute").order_by("sort_order", "name")
    selected_preset = None
    if str(preset_id or "").isdigit():
        selected_preset = next((preset for preset in presets if preset.pk == int(preset_id)), None)

    attributes = VariantAttribute.objects.filter(is_active=True).prefetch_related("values").order_by("sort_order", "name")
    if selected_preset:
        selected_ids = list(selected_preset.attribute_links.order_by("sort_order", "id").values_list("attribute_id", flat=True))
        attribute_map = {attribute.pk: attribute for attribute in attributes}
        attributes = [attribute_map[attr_id] for attr_id in selected_ids if attr_id in attribute_map]
    else:
        attributes = list(attributes)

    existing_value_ids = set()
    variants_qs = ProductVariant.objects.none()
    if product:
        variants_qs = product.variants.prefetch_related("variant_values__value__attribute").order_by("-is_default", "id")
        existing_value_ids = set(
            VariantAttributeValue.objects.filter(variant_links__variant__product=product)
            .values_list("id", flat=True)
            .distinct()
        )

    context = _context(request, product_id)
    context.update(
        selected_product=product,
        presets=presets,
        selected_preset=selected_preset,
        builder_attributes=attributes,
        existing_value_ids=existing_value_ids,
        builder_variants=variants_qs,
        generator_error=generator_error,
        generation_created=request.GET.get("created", ""),
        generation_reused=request.GET.get("reused", ""),
        generation_skipped=request.GET.get("skipped", ""),
    )
    return render(request, "backoffice/pages/catalog/variant_builder.html", context)
