from collections import defaultdict
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from catalog.models import ProductVariant
from .models import (
    InventoryBalance,
    StockAdjustment,
    StockMovement,
    StockTransfer,
    StockTransferItem,
    Warehouse,
)


class InventoryError(ValidationError):
    pass


class InsufficientStock(InventoryError):
    pass


def make_reference(prefix):
    stamp = timezone.localtime().strftime("%y%m%d%H%M%S")
    return f"{prefix}-{stamp}-{uuid4().hex[:6].upper()}"


def get_default_warehouse():
    warehouse = Warehouse.objects.filter(is_default=True, is_active=True).order_by("id").first()
    if warehouse:
        return warehouse
    warehouse = Warehouse.objects.filter(is_active=True).order_by("id").first()
    if warehouse:
        if not warehouse.is_default:
            Warehouse.objects.filter(is_default=True).update(is_default=False)
            warehouse.is_default = True
            warehouse.save(update_fields=["is_default", "updated_at"])
        return warehouse
    return Warehouse.objects.create(
        name="Main Warehouse",
        code="MAIN",
        address="Primary stock location",
        is_active=True,
        is_default=True,
    )


def _lock_balance(warehouse, variant):
    balance, _ = InventoryBalance.objects.get_or_create(
        warehouse=warehouse,
        variant=variant,
        defaults={
            "on_hand": 0,
            "reserved_quantity": 0,
            "low_stock_threshold": variant.low_stock_alert,
        },
    )
    return InventoryBalance.objects.select_for_update().select_related(
        "warehouse", "variant", "variant__product"
    ).get(pk=balance.pk)


def _sync_variant_cache(variant_id):
    total_available = sum(
        max(0, on_hand - reserved)
        for on_hand, reserved in InventoryBalance.objects.filter(variant_id=variant_id).values_list(
            "on_hand", "reserved_quantity"
        )
    )
    ProductVariant.objects.filter(pk=variant_id).update(stock_quantity=total_available)
    return total_available


def sync_variant_cache(variant):
    return _sync_variant_cache(variant.pk)


def _movement_snapshot(variant):
    return variant.sku, variant.product.name


def _create_movement(
    *,
    balance,
    movement_type,
    quantity_delta=0,
    reserved_delta=0,
    reference_type="",
    reference_no="",
    note="",
    actor="",
):
    if quantity_delta == 0 and reserved_delta == 0:
        raise InventoryError("A stock movement must change on-hand or reserved stock.")
    sku, product_name = _movement_snapshot(balance.variant)
    return StockMovement.objects.create(
        warehouse=balance.warehouse,
        variant=balance.variant,
        sku_snapshot=sku,
        product_snapshot=product_name,
        movement_type=movement_type,
        quantity_delta=quantity_delta,
        reserved_delta=reserved_delta,
        quantity_after=balance.on_hand,
        reserved_after=balance.reserved_quantity,
        reference_type=reference_type,
        reference_no=reference_no,
        note=note,
        actor=actor,
    )


@transaction.atomic
def post_movement(
    *,
    warehouse,
    variant,
    movement_type,
    quantity_delta=0,
    reserved_delta=0,
    reference_type="",
    reference_no="",
    note="",
    actor="",
):
    balance = _lock_balance(warehouse, variant)
    next_on_hand = balance.on_hand + int(quantity_delta)
    next_reserved = balance.reserved_quantity + int(reserved_delta)
    if next_on_hand < 0:
        raise InsufficientStock(
            f"Not enough stock for {variant.sku} in {warehouse.name}. On hand: {balance.on_hand}."
        )
    if next_reserved < 0:
        raise InventoryError("Reserved stock cannot become negative.")
    if next_reserved > next_on_hand:
        raise InsufficientStock(
            f"Not enough available stock for {variant.sku} in {warehouse.name}. "
            f"Available: {balance.available_quantity}."
        )
    balance.on_hand = next_on_hand
    balance.reserved_quantity = next_reserved
    balance.save(update_fields=["on_hand", "reserved_quantity", "updated_at"])
    movement = _create_movement(
        balance=balance,
        movement_type=movement_type,
        quantity_delta=int(quantity_delta),
        reserved_delta=int(reserved_delta),
        reference_type=reference_type,
        reference_no=reference_no,
        note=note,
        actor=actor,
    )
    _sync_variant_cache(variant.pk)
    return movement


@transaction.atomic
def bootstrap_variant_stock(variant):
    if InventoryBalance.objects.filter(variant=variant).exists():
        _sync_variant_cache(variant.pk)
        return InventoryBalance.objects.filter(variant=variant).order_by("id").first()
    warehouse = get_default_warehouse()
    balance = _lock_balance(warehouse, variant)
    opening_quantity = int(variant.stock_quantity or 0)
    if opening_quantity:
        balance.on_hand = opening_quantity
        balance.save(update_fields=["on_hand", "updated_at"])
        _create_movement(
            balance=balance,
            movement_type=StockMovement.Type.OPENING,
            quantity_delta=opening_quantity,
            reference_type="catalog",
            reference_no="variant-created",
            note="Opening stock imported from the catalog variant.",
            actor="System",
        )
    _sync_variant_cache(variant.pk)
    return balance


@transaction.atomic
def adjust_stock(*, warehouse, variant, actual_quantity, reason, note="", actor="", reference_no=None):
    actual_quantity = int(actual_quantity)
    if actual_quantity < 0:
        raise InventoryError("Actual quantity cannot be negative.")
    balance = _lock_balance(warehouse, variant)
    if actual_quantity < balance.reserved_quantity:
        raise InventoryError(
            f"Actual stock cannot be below reserved quantity ({balance.reserved_quantity})."
        )
    difference = actual_quantity - balance.on_hand
    if difference == 0:
        raise InventoryError("No stock difference to post.")
    reference_no = reference_no or make_reference("ADJ")
    sku, product_name = _movement_snapshot(variant)
    adjustment = StockAdjustment.objects.create(
        reference_no=reference_no,
        warehouse=warehouse,
        variant=variant,
        sku_snapshot=sku,
        product_snapshot=product_name,
        system_quantity=balance.on_hand,
        actual_quantity=actual_quantity,
        difference=difference,
        reason=reason,
        note=note,
        actor=actor,
    )
    balance.on_hand = actual_quantity
    balance.save(update_fields=["on_hand", "updated_at"])
    _create_movement(
        balance=balance,
        movement_type=(
            StockMovement.Type.ADJUSTMENT_IN if difference > 0 else StockMovement.Type.ADJUSTMENT_OUT
        ),
        quantity_delta=difference,
        reference_type="adjustment",
        reference_no=reference_no,
        note=f"{reason}. {note}".strip(),
        actor=actor,
    )
    _sync_variant_cache(variant.pk)
    return adjustment


@transaction.atomic
def transfer_stock(*, from_warehouse, to_warehouse, items, note="", actor="", transfer_no=None):
    if from_warehouse.pk == to_warehouse.pk:
        raise InventoryError("Source and destination warehouses must be different.")
    if not from_warehouse.is_active or not to_warehouse.is_active:
        raise InventoryError("Stock transfers require active source and destination warehouses.")

    quantities = defaultdict(int)
    variants = {}
    for variant, quantity in items:
        quantity = int(quantity)
        if quantity <= 0:
            raise InventoryError("Transfer quantity must be greater than zero.")
        quantities[variant.pk] += quantity
        variants[variant.pk] = variant
    if not quantities:
        raise InventoryError("Add at least one transfer item.")

    locked = {}
    keys = sorted(
        [(from_warehouse.pk, variant_id) for variant_id in quantities]
        + [(to_warehouse.pk, variant_id) for variant_id in quantities]
    )
    warehouse_map = {from_warehouse.pk: from_warehouse, to_warehouse.pk: to_warehouse}
    for warehouse_id, variant_id in keys:
        locked[(warehouse_id, variant_id)] = _lock_balance(
            warehouse_map[warehouse_id], variants[variant_id]
        )

    for variant_id, quantity in quantities.items():
        source = locked[(from_warehouse.pk, variant_id)]
        if source.available_quantity < quantity:
            raise InsufficientStock(
                f"Not enough available stock for {source.variant.sku} in {from_warehouse.name}. "
                f"Available: {source.available_quantity}."
            )

    transfer_no = transfer_no or make_reference("TRF")
    transfer = StockTransfer.objects.create(
        transfer_no=transfer_no,
        from_warehouse=from_warehouse,
        to_warehouse=to_warehouse,
        note=note,
        actor=actor,
    )

    for variant_id, quantity in quantities.items():
        variant = variants[variant_id]
        source = locked[(from_warehouse.pk, variant_id)]
        destination = locked[(to_warehouse.pk, variant_id)]
        sku, product_name = _movement_snapshot(variant)
        StockTransferItem.objects.create(
            transfer=transfer,
            variant=variant,
            sku_snapshot=sku,
            product_snapshot=product_name,
            quantity=quantity,
        )
        source.on_hand -= quantity
        destination.on_hand += quantity
        source.save(update_fields=["on_hand", "updated_at"])
        destination.save(update_fields=["on_hand", "updated_at"])
        _create_movement(
            balance=source,
            movement_type=StockMovement.Type.TRANSFER_OUT,
            quantity_delta=-quantity,
            reference_type="transfer",
            reference_no=transfer_no,
            note=f"Transfer to {to_warehouse.name}. {note}".strip(),
            actor=actor,
        )
        _create_movement(
            balance=destination,
            movement_type=StockMovement.Type.TRANSFER_IN,
            quantity_delta=quantity,
            reference_type="transfer",
            reference_no=transfer_no,
            note=f"Transfer from {from_warehouse.name}. {note}".strip(),
            actor=actor,
        )
        _sync_variant_cache(variant_id)
    return transfer


@transaction.atomic
def reserve_stock(*, warehouse, variant, quantity, reference_no="", note="", actor=""):
    quantity = int(quantity)
    if quantity <= 0:
        raise InventoryError("Reservation quantity must be greater than zero.")
    return post_movement(
        warehouse=warehouse,
        variant=variant,
        movement_type=StockMovement.Type.RESERVE,
        reserved_delta=quantity,
        reference_type="reservation",
        reference_no=reference_no,
        note=note,
        actor=actor,
    )


@transaction.atomic
def release_reserved_stock(*, warehouse, variant, quantity, reference_no="", note="", actor=""):
    quantity = int(quantity)
    if quantity <= 0:
        raise InventoryError("Release quantity must be greater than zero.")
    return post_movement(
        warehouse=warehouse,
        variant=variant,
        movement_type=StockMovement.Type.RELEASE,
        reserved_delta=-quantity,
        reference_type="reservation",
        reference_no=reference_no,
        note=note,
        actor=actor,
    )


@transaction.atomic
def issue_reserved_stock(*, warehouse, variant, quantity, reference_no="", note="", actor=""):
    quantity = int(quantity)
    if quantity <= 0:
        raise InventoryError("Issue quantity must be greater than zero.")
    return post_movement(
        warehouse=warehouse,
        variant=variant,
        movement_type=StockMovement.Type.RESERVED_SALE,
        quantity_delta=-quantity,
        reserved_delta=-quantity,
        reference_type="sale",
        reference_no=reference_no,
        note=note,
        actor=actor,
    )


def low_stock_balances():
    rows = InventoryBalance.objects.select_related(
        "warehouse", "variant", "variant__product"
    ).order_by("warehouse__name", "variant__product__name", "variant__sku")
    return [row for row in rows if row.available_quantity <= row.low_stock_threshold]
