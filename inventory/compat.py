from django.db import transaction

from .models import InventoryBalance, StockMovement
from .services import (
    InventoryError,
    _create_movement,
    _lock_balance,
    _sync_variant_cache,
    bootstrap_variant_stock,
    get_default_warehouse,
)


@transaction.atomic
def reconcile_catalog_stock(variant):
    """Keep legacy ProductVariant.stock_quantity writes compatible with Inventory.

    Inventory remains authoritative. If an older catalog form writes the compatibility
    stock field, the difference is posted as auditable adjustment movements instead
    of silently overwriting warehouse balances.
    """
    balances = list(
        InventoryBalance.objects.select_for_update()
        .select_related("warehouse", "variant", "variant__product")
        .filter(variant=variant)
        .order_by("-warehouse__is_default", "warehouse_id")
    )
    if not balances:
        return bootstrap_variant_stock(variant)

    current_available = sum(row.available_quantity for row in balances)
    desired_available = int(variant.stock_quantity or 0)
    delta = desired_available - current_available
    if delta == 0:
        return balances[0]

    if delta > 0:
        warehouse = get_default_warehouse()
        balance = _lock_balance(warehouse, variant)
        balance.on_hand += delta
        balance.save(update_fields=["on_hand", "updated_at"])
        _create_movement(
            balance=balance,
            movement_type=StockMovement.Type.ADJUSTMENT_IN,
            quantity_delta=delta,
            reference_type="catalog-compat",
            reference_no="variant-stock-edit",
            note="Catalog stock field reconciled into Inventory Phase 1.",
            actor="Catalog Compatibility",
        )
    else:
        remaining = -delta
        for balance in balances:
            if remaining <= 0:
                break
            removable = balance.available_quantity
            take = min(removable, remaining)
            if not take:
                continue
            balance.on_hand -= take
            balance.save(update_fields=["on_hand", "updated_at"])
            _create_movement(
                balance=balance,
                movement_type=StockMovement.Type.ADJUSTMENT_OUT,
                quantity_delta=-take,
                reference_type="catalog-compat",
                reference_no="variant-stock-edit",
                note="Catalog stock field reconciled into Inventory Phase 1.",
                actor="Catalog Compatibility",
            )
            remaining -= take
        if remaining:
            _sync_variant_cache(variant.pk)
            raise InventoryError("Stock cannot be reduced below the quantity currently reserved.")

    _sync_variant_cache(variant.pk)
    return InventoryBalance.objects.filter(variant=variant).order_by("id").first()
