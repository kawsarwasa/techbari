import re
from collections import defaultdict
from itertools import product as cartesian_product

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from .models import ProductVariant, ProductVariantValue, VariantAttributeValue


class VariantGenerationError(ValidationError):
    pass


def variant_usage_reasons(variant):
    """Return business reasons that make a variant identity immutable."""
    reasons = []
    if variant.inventory_balances.filter(Q(on_hand__gt=0) | Q(reserved_quantity__gt=0)).exists():
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


def ordered_values(values):
    return sorted(
        values,
        key=lambda value: (
            value.attribute.sort_order,
            value.attribute_id,
            value.sort_order,
            value.id,
        ),
    )


def variant_name(values):
    return " / ".join(value.value for value in ordered_values(values))[:120]


def combination_signature(values):
    return tuple(sorted(int(value.pk) for value in values))


def variant_signature(variant):
    return tuple(sorted(variant.variant_values.values_list("value_id", flat=True)))


def _compact_code(value, fallback="VAR", max_length=12):
    raw = str(value or fallback).upper()
    compact = re.sub(r"[^A-Z0-9]+", "", raw)
    return (compact or fallback)[:max_length]


def unique_variant_sku(product, values, *, exclude_variant_id=None):
    base = _compact_code(product.public_id or product.slug or product.name, "PROD", 18)
    pieces = [_compact_code(value.code or value.value, "VAL", 10) for value in ordered_values(values)]
    candidate = "-".join([base, *pieces])[:64]
    candidate = candidate.rstrip("-") or base
    qs = ProductVariant.objects.all()
    if exclude_variant_id:
        qs = qs.exclude(pk=exclude_variant_id)
    if not qs.filter(sku__iexact=candidate).exists():
        return candidate
    suffix = 2
    while True:
        tail = f"-{suffix}"
        proposed = f"{candidate[:64 - len(tail)]}{tail}"
        if not qs.filter(sku__iexact=proposed).exists():
            return proposed
        suffix += 1


def _legacy_reusable_variant(product):
    candidates = product.variants.filter(variant_values__isnull=True).distinct().order_by("-is_default", "id")
    for variant in candidates:
        if not variant_usage_reasons(variant):
            return variant
    return None


@transaction.atomic
def generate_variant_combinations(*, product, value_ids):
    """Generate the cartesian product of selected reusable global values.

    Existing ProductVariant rows are never recreated. A transaction-free legacy/default
    row may be converted into the first generated combination so a new product does not
    keep an unnecessary placeholder SKU.
    """
    normalized_ids = []
    seen_ids = set()
    for raw in value_ids:
        try:
            value_id = int(raw)
        except (TypeError, ValueError) as exc:
            raise VariantGenerationError("Select valid attribute values.") from exc
        if value_id not in seen_ids:
            normalized_ids.append(value_id)
            seen_ids.add(value_id)
    if not normalized_ids:
        raise VariantGenerationError("Select at least one attribute value before generating variants.")

    values = list(
        VariantAttributeValue.objects.select_related("attribute")
        .filter(pk__in=normalized_ids, is_active=True, attribute__is_active=True)
        .order_by("attribute__sort_order", "attribute_id", "sort_order", "id")
    )
    if len(values) != len(normalized_ids):
        raise VariantGenerationError("One or more selected attribute values are inactive or unavailable.")

    grouped = defaultdict(list)
    for value in values:
        grouped[value.attribute_id].append(value)
    attribute_order = []
    for value in values:
        if value.attribute_id not in attribute_order:
            attribute_order.append(value.attribute_id)
    value_groups = [grouped[attribute_id] for attribute_id in attribute_order]
    if not value_groups or any(not group for group in value_groups):
        raise VariantGenerationError("Every selected attribute must have at least one value.")

    combinations = [list(row) for row in cartesian_product(*value_groups)]
    if len(combinations) > 250:
        raise VariantGenerationError("This selection would create more than 250 variants. Reduce the selected values and generate in smaller groups.")

    existing_variants = list(
        product.variants.prefetch_related("variant_values__value__attribute").order_by("-is_default", "id")
    )
    existing_by_signature = {
        variant_signature(variant): variant
        for variant in existing_variants
        if variant.variant_values.exists()
    }
    existing_names = {variant.name.casefold(): variant.pk for variant in existing_variants}

    reusable = _legacy_reusable_variant(product)
    created = 0
    reused = 0
    skipped = 0
    first_generated = None

    for values_for_variant in combinations:
        signature = combination_signature(values_for_variant)
        if signature in existing_by_signature:
            skipped += 1
            continue

        name = variant_name(values_for_variant)
        name_owner = existing_names.get(name.casefold())
        if name_owner and (reusable is None or name_owner != reusable.pk):
            raise VariantGenerationError(
                f"Cannot generate {name}: another SKU already uses that variant name. Rename the conflicting legacy variant first."
            )

        symbol = next((value.symbol for value in ordered_values(values_for_variant) if value.symbol), "")
        if reusable is not None:
            variant = reusable
            reusable = None
            variant.name = name
            variant.sku = unique_variant_sku(product, values_for_variant, exclude_variant_id=variant.pk)
            if symbol and not variant.symbol:
                variant.symbol = symbol[:16]
            variant.is_active = True
            variant.save(update_fields=["name", "sku", "symbol", "is_active", "updated_at"])
            ProductVariantValue.objects.filter(variant=variant).delete()
            reused += 1
        else:
            has_default = product.variants.filter(is_default=True, is_active=True).exists()
            variant = ProductVariant.objects.create(
                product=product,
                name=name,
                sku=unique_variant_sku(product, values_for_variant),
                symbol=symbol[:16],
                stock_quantity=0,
                low_stock_alert=5,
                is_default=not has_default,
                is_active=True,
            )
            created += 1

        ProductVariantValue.objects.bulk_create(
            [ProductVariantValue(variant=variant, value=value) for value in ordered_values(values_for_variant)]
        )
        existing_by_signature[signature] = variant
        existing_names[name.casefold()] = variant.pk
        if first_generated is None:
            first_generated = variant

    if first_generated and not product.variants.filter(is_default=True, is_active=True).exists():
        first_generated.is_default = True
        first_generated.save(update_fields=["is_default", "updated_at"])

    return {
        "created": created,
        "reused": reused,
        "skipped": skipped,
        "total_requested": len(combinations),
    }
