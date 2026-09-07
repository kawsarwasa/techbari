from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from inventory.models import InventoryBalance, StockMovement
from inventory.services import (
    InventoryError,
    post_movement,
    release_reserved_stock,
    reserve_stock,
    transfer_stock,
)
from .models import SerializedUnit, SerializedUnitEvent, WarrantyClaim


class SerialTrackingError(ValidationError):
    pass


STOCK_BEARING_STATUSES = {
    SerializedUnit.Status.AVAILABLE,
    SerializedUnit.Status.RESERVED,
    SerializedUnit.Status.RETURNED,
}

TERMINAL_CLAIM_STATUSES = {
    WarrantyClaim.Status.RESOLVED,
    WarrantyClaim.Status.REPLACED,
    WarrantyClaim.Status.REJECTED,
}


def _event(
    unit,
    event_type,
    *,
    from_status="",
    to_status="",
    from_warehouse=None,
    to_warehouse=None,
    reference_no="",
    note="",
    actor="",
):
    return SerializedUnitEvent.objects.create(
        unit=unit,
        event_type=event_type,
        from_status=from_status or "",
        to_status=to_status or "",
        from_warehouse=from_warehouse,
        to_warehouse=to_warehouse,
        reference_no=reference_no or "",
        note=note or "",
        actor=actor or "",
    )


def _tracked_stock_count(warehouse, variant, exclude_unit_id=None):
    qs = SerializedUnit.objects.filter(
        warehouse=warehouse,
        variant=variant,
        status__in=STOCK_BEARING_STATUSES,
    )
    if exclude_unit_id:
        qs = qs.exclude(pk=exclude_unit_id)
    return qs.count()


def _locked_balance(warehouse, variant):
    try:
        return InventoryBalance.objects.select_for_update().get(warehouse=warehouse, variant=variant)
    except InventoryBalance.DoesNotExist as exc:
        raise SerialTrackingError(
            f"No inventory balance exists for {variant.sku} in {warehouse.name}. Add stock before registering this unit."
        ) from exc


def _ensure_registration_capacity(warehouse, variant, exclude_unit_id=None):
    balance = _locked_balance(warehouse, variant)
    tracked = _tracked_stock_count(warehouse, variant, exclude_unit_id=exclude_unit_id)
    if tracked >= balance.on_hand:
        raise SerialTrackingError(
            f"Cannot register another stock unit for {variant.sku} in {warehouse.name}. "
            f"Inventory on hand is {balance.on_hand}, and {tracked} serialized unit(s) are already registered."
        )
    return balance


def _movement_reference(unit, suffix="status"):
    return f"SERIAL:{unit.display_identifier}:{suffix}"


def _apply_status_inventory(unit, old_status, new_status, *, actor="", note="", reference_no=""):
    if old_status == new_status:
        return

    warehouse = unit.warehouse
    variant = unit.variant
    reference_no = reference_no or _movement_reference(unit)

    old_stock = old_status in STOCK_BEARING_STATUSES
    new_stock = new_status in STOCK_BEARING_STATUSES

    if old_status == SerializedUnit.Status.RESERVED:
        if new_status in {SerializedUnit.Status.AVAILABLE, SerializedUnit.Status.RETURNED}:
            release_reserved_stock(
                warehouse=warehouse,
                variant=variant,
                quantity=1,
                reference_no=reference_no,
                note=note,
                actor=actor,
            )
            return
        if new_status == SerializedUnit.Status.SOLD:
            post_movement(
                warehouse=warehouse,
                variant=variant,
                movement_type=StockMovement.Type.RESERVED_SALE,
                quantity_delta=-1,
                reserved_delta=-1,
                reference_type="serialized_unit",
                reference_no=reference_no,
                note=note,
                actor=actor,
            )
            return
        if not new_stock:
            movement_type = (
                StockMovement.Type.DAMAGE_OUT
                if new_status in {SerializedUnit.Status.DAMAGED, SerializedUnit.Status.SCRAPPED}
                else StockMovement.Type.ADJUSTMENT_OUT
            )
            post_movement(
                warehouse=warehouse,
                variant=variant,
                movement_type=movement_type,
                quantity_delta=-1,
                reserved_delta=-1,
                reference_type="serialized_unit",
                reference_no=reference_no,
                note=note,
                actor=actor,
            )
            return

    if old_stock and not new_stock:
        if new_status == SerializedUnit.Status.SOLD:
            movement_type = StockMovement.Type.SALE_OUT
        elif new_status in {SerializedUnit.Status.DAMAGED, SerializedUnit.Status.SCRAPPED}:
            movement_type = StockMovement.Type.DAMAGE_OUT
        else:
            movement_type = StockMovement.Type.ADJUSTMENT_OUT
        post_movement(
            warehouse=warehouse,
            variant=variant,
            movement_type=movement_type,
            quantity_delta=-1,
            reference_type="serialized_unit",
            reference_no=reference_no,
            note=note,
            actor=actor,
        )
        return

    if not old_stock and new_stock:
        inbound_type = (
            StockMovement.Type.RETURN_IN
            if old_status == SerializedUnit.Status.SOLD
            else StockMovement.Type.ADJUSTMENT_IN
        )
        post_movement(
            warehouse=warehouse,
            variant=variant,
            movement_type=inbound_type,
            quantity_delta=1,
            reference_type="serialized_unit",
            reference_no=reference_no,
            note=note,
            actor=actor,
        )
        if new_status == SerializedUnit.Status.RESERVED:
            reserve_stock(
                warehouse=warehouse,
                variant=variant,
                quantity=1,
                reference_no=reference_no,
                note=note,
                actor=actor,
            )
        return

    if old_stock and new_status == SerializedUnit.Status.RESERVED:
        reserve_stock(
            warehouse=warehouse,
            variant=variant,
            quantity=1,
            reference_no=reference_no,
            note=note,
            actor=actor,
        )


def _transfer_locked(unit, to_warehouse, *, actor="", note="", reference_no=""):
    from_warehouse = unit.warehouse
    if from_warehouse_id := getattr(from_warehouse, "pk", None):
        if from_warehouse_id == to_warehouse.pk:
            return unit
    if not to_warehouse.is_active:
        raise SerialTrackingError("The destination warehouse must be active.")

    reference_no = reference_no or _movement_reference(unit, "transfer")
    status = unit.status

    try:
        if status in {SerializedUnit.Status.AVAILABLE, SerializedUnit.Status.RETURNED}:
            transfer_stock(
                from_warehouse=from_warehouse,
                to_warehouse=to_warehouse,
                items=[(unit.variant, 1)],
                note=f"Serialized unit {unit.display_identifier}. {note}".strip(),
                actor=actor,
                transfer_no=None,
            )
        elif status == SerializedUnit.Status.RESERVED:
            release_reserved_stock(
                warehouse=from_warehouse,
                variant=unit.variant,
                quantity=1,
                reference_no=reference_no,
                note="Release reservation for serialized-unit transfer.",
                actor=actor,
            )
            transfer_stock(
                from_warehouse=from_warehouse,
                to_warehouse=to_warehouse,
                items=[(unit.variant, 1)],
                note=f"Reserved serialized unit {unit.display_identifier}. {note}".strip(),
                actor=actor,
                transfer_no=None,
            )
            reserve_stock(
                warehouse=to_warehouse,
                variant=unit.variant,
                quantity=1,
                reference_no=reference_no,
                note="Restore reservation after serialized-unit transfer.",
                actor=actor,
            )
    except InventoryError as exc:
        raise SerialTrackingError(exc.messages if hasattr(exc, "messages") else str(exc)) from exc

    unit.warehouse = to_warehouse
    unit.save(update_fields=["warehouse", "updated_at"])
    _event(
        unit,
        SerializedUnitEvent.Type.TRANSFERRED,
        from_status=status,
        to_status=status,
        from_warehouse=from_warehouse,
        to_warehouse=to_warehouse,
        reference_no=reference_no,
        note=note,
        actor=actor,
    )
    return unit


@transaction.atomic
def register_serial_unit(*, data, actor=""):
    unit = SerializedUnit(**data)
    unit.full_clean()
    if not unit.warehouse.is_active:
        raise SerialTrackingError("The warehouse must be active.")
    if unit.status in STOCK_BEARING_STATUSES:
        _ensure_registration_capacity(unit.warehouse, unit.variant)
    unit.save()
    if unit.status == SerializedUnit.Status.RESERVED:
        try:
            reserve_stock(
                warehouse=unit.warehouse,
                variant=unit.variant,
                quantity=1,
                reference_no=_movement_reference(unit, "register-reserved"),
                note="Serialized unit registered as reserved.",
                actor=actor,
            )
        except InventoryError as exc:
            raise SerialTrackingError(exc.messages if hasattr(exc, "messages") else str(exc)) from exc
    _event(
        unit,
        SerializedUnitEvent.Type.REGISTERED,
        to_status=unit.status,
        to_warehouse=unit.warehouse,
        reference_no=unit.purchase_reference,
        note="Serialized unit registered.",
        actor=actor,
    )
    return unit


@transaction.atomic
def change_serial_unit_status(unit, new_status, *, actor="", note="", reference_no=""):
    unit = SerializedUnit.objects.select_for_update().select_related("variant", "variant__product", "warehouse").get(pk=unit.pk)
    old_status = unit.status
    if old_status == new_status:
        return unit
    valid_statuses = {value for value, _ in SerializedUnit.Status.choices}
    if new_status not in valid_statuses:
        raise SerialTrackingError("Invalid serialized-unit status.")
    try:
        _apply_status_inventory(
            unit,
            old_status,
            new_status,
            actor=actor,
            note=note,
            reference_no=reference_no,
        )
    except InventoryError as exc:
        raise SerialTrackingError(exc.messages if hasattr(exc, "messages") else str(exc)) from exc
    unit.status = new_status
    unit.save(update_fields=["status", "updated_at"])
    _event(
        unit,
        SerializedUnitEvent.Type.STATUS_CHANGED,
        from_status=old_status,
        to_status=new_status,
        from_warehouse=unit.warehouse,
        to_warehouse=unit.warehouse,
        reference_no=reference_no,
        note=note,
        actor=actor,
    )
    return unit


@transaction.atomic
def transfer_serial_unit(unit, to_warehouse, *, actor="", note="", reference_no=""):
    unit = SerializedUnit.objects.select_for_update().select_related("variant", "variant__product", "warehouse").get(pk=unit.pk)
    return _transfer_locked(
        unit,
        to_warehouse,
        actor=actor,
        note=note,
        reference_no=reference_no,
    )


@transaction.atomic
def update_serial_unit(*, unit, data, actor=""):
    unit = SerializedUnit.objects.select_for_update().select_related("variant", "variant__product", "warehouse").get(pk=unit.pk)
    old_identifier = (unit.serial_number, unit.imei1, unit.imei2)
    old_status = unit.status
    old_warehouse = unit.warehouse

    new_variant = data.get("variant", unit.variant)
    if new_variant.pk != unit.variant_id:
        raise SerialTrackingError("A registered unit cannot be moved to a different product variant/SKU.")
    new_warehouse = data.get("warehouse", unit.warehouse)
    new_status = data.get("status", unit.status)

    if new_warehouse.pk != unit.warehouse_id:
        _transfer_locked(
            unit,
            new_warehouse,
            actor=actor,
            note="Warehouse changed from the serialized-unit form.",
        )

    if new_status != unit.status:
        current_status = unit.status
        try:
            _apply_status_inventory(
                unit,
                current_status,
                new_status,
                actor=actor,
                note="Status changed from the serialized-unit form.",
                reference_no=_movement_reference(unit, "status"),
            )
        except InventoryError as exc:
            raise SerialTrackingError(exc.messages if hasattr(exc, "messages") else str(exc)) from exc
        unit.status = new_status
        unit.save(update_fields=["status", "updated_at"])
        _event(
            unit,
            SerializedUnitEvent.Type.STATUS_CHANGED,
            from_status=current_status,
            to_status=new_status,
            from_warehouse=unit.warehouse,
            to_warehouse=unit.warehouse,
            note="Status changed from the serialized-unit form.",
            actor=actor,
        )

    editable_fields = (
        "serial_number",
        "imei1",
        "imei2",
        "supplier_reference",
        "purchase_reference",
        "purchase_date",
        "purchase_cost",
        "received_date",
        "sales_reference",
        "customer_reference",
        "sold_at",
        "warranty_type",
        "warranty_start_date",
        "warranty_end_date",
        "supplier_warranty_reference",
        "notes",
    )
    for field in editable_fields:
        if field in data:
            setattr(unit, field, data[field])
    unit.full_clean()
    unit.save()

    new_identifier = (unit.serial_number, unit.imei1, unit.imei2)
    if new_identifier != old_identifier:
        _event(
            unit,
            SerializedUnitEvent.Type.IDENTIFIERS_UPDATED,
            from_status=old_status,
            to_status=unit.status,
            from_warehouse=old_warehouse,
            to_warehouse=unit.warehouse,
            note="Serial / IMEI identifiers updated.",
            actor=actor,
        )
    return unit


@transaction.atomic
def open_warranty_claim(*, data, actor=""):
    unit = SerializedUnit.objects.select_for_update().select_related("variant", "variant__product", "warehouse").get(pk=data["unit"].pk)
    status = data.get("status", WarrantyClaim.Status.OPEN)
    if status not in {WarrantyClaim.Status.OPEN, WarrantyClaim.Status.IN_SERVICE}:
        raise SerialTrackingError("A new warranty claim must start as Open or In Service.")

    previous_status = unit.status
    claim = WarrantyClaim(**data)
    claim.unit = unit
    claim.unit_status_before_claim = previous_status
    claim.actor = actor
    claim.full_clean()
    claim.save()

    if unit.status != SerializedUnit.Status.WARRANTY_SERVICE:
        change_serial_unit_status(
            unit,
            SerializedUnit.Status.WARRANTY_SERVICE,
            actor=actor,
            note=f"Warranty claim {claim.claim_no} opened.",
            reference_no=claim.claim_no,
        )
        unit.refresh_from_db()

    _event(
        unit,
        SerializedUnitEvent.Type.WARRANTY_OPENED,
        from_status=previous_status,
        to_status=unit.status,
        from_warehouse=unit.warehouse,
        to_warehouse=unit.warehouse,
        reference_no=claim.claim_no,
        note=claim.issue,
        actor=actor,
    )
    return claim


@transaction.atomic
def update_warranty_claim(*, claim, data, actor=""):
    claim = WarrantyClaim.objects.select_for_update().select_related(
        "unit", "unit__variant", "unit__variant__product", "unit__warehouse"
    ).get(pk=claim.pk)
    old_status = claim.status
    new_status = data.get("status", claim.status)

    if old_status in TERMINAL_CLAIM_STATUSES and new_status not in TERMINAL_CLAIM_STATUSES:
        raise SerialTrackingError("A completed warranty claim cannot be reopened. Create a new claim instead.")

    unit = claim.unit
    replacement = data.get("replacement_unit")

    if new_status == WarrantyClaim.Status.REPLACED:
        if not replacement:
            raise SerialTrackingError("Choose a replacement unit.")
        replacement = SerializedUnit.objects.select_for_update().select_related("variant", "variant__product", "warehouse").get(pk=replacement.pk)
        if replacement.pk == unit.pk or replacement.variant_id != unit.variant_id:
            raise SerialTrackingError("Replacement must be a different unit using the same product variant/SKU.")
        if replacement.status not in {SerializedUnit.Status.AVAILABLE, SerializedUnit.Status.RETURNED}:
            raise SerialTrackingError("Replacement unit must be Available or Returned.")
        change_serial_unit_status(
            replacement,
            SerializedUnit.Status.SOLD,
            actor=actor,
            note=f"Replacement issued for warranty claim {claim.claim_no}.",
            reference_no=claim.claim_no,
        )
        if unit.status != SerializedUnit.Status.SCRAPPED:
            change_serial_unit_status(
                unit,
                SerializedUnit.Status.SCRAPPED,
                actor=actor,
                note=f"Original unit replaced under warranty claim {claim.claim_no}.",
                reference_no=claim.claim_no,
            )
        _event(
            unit,
            SerializedUnitEvent.Type.WARRANTY_REPLACED,
            from_status=SerializedUnit.Status.WARRANTY_SERVICE,
            to_status=SerializedUnit.Status.SCRAPPED,
            from_warehouse=unit.warehouse,
            to_warehouse=unit.warehouse,
            reference_no=claim.claim_no,
            note=f"Replacement unit: {replacement.display_identifier}",
            actor=actor,
        )
    elif new_status in {WarrantyClaim.Status.RESOLVED, WarrantyClaim.Status.REJECTED}:
        restore_status = claim.unit_status_before_claim or SerializedUnit.Status.SOLD
        if unit.status == SerializedUnit.Status.WARRANTY_SERVICE and restore_status != SerializedUnit.Status.WARRANTY_SERVICE:
            change_serial_unit_status(
                unit,
                restore_status,
                actor=actor,
                note=f"Warranty claim {claim.claim_no} closed.",
                reference_no=claim.claim_no,
            )
    elif new_status in {WarrantyClaim.Status.OPEN, WarrantyClaim.Status.IN_SERVICE}:
        if unit.status != SerializedUnit.Status.WARRANTY_SERVICE:
            change_serial_unit_status(
                unit,
                SerializedUnit.Status.WARRANTY_SERVICE,
                actor=actor,
                note=f"Warranty claim {claim.claim_no} in service.",
                reference_no=claim.claim_no,
            )

    editable_fields = (
        "customer_name",
        "customer_phone",
        "order_reference",
        "claim_date",
        "issue",
        "status",
        "resolution",
        "service_reference",
        "replacement_unit",
        "resolved_at",
        "notes",
    )
    for field in editable_fields:
        if field in data:
            setattr(claim, field, data[field])
    claim.actor = actor or claim.actor
    if claim.status in TERMINAL_CLAIM_STATUSES and not claim.resolved_at:
        claim.resolved_at = timezone.localdate()
    claim.full_clean()
    claim.save()

    _event(
        unit,
        SerializedUnitEvent.Type.WARRANTY_UPDATED,
        from_status=old_status,
        to_status=claim.status,
        from_warehouse=unit.warehouse,
        to_warehouse=unit.warehouse,
        reference_no=claim.claim_no,
        note=claim.resolution or claim.issue,
        actor=actor,
    )
    return claim


def unit_inventory_gap(unit):
    try:
        balance = InventoryBalance.objects.get(warehouse=unit.warehouse, variant=unit.variant)
    except InventoryBalance.DoesNotExist:
        return None
    tracked = _tracked_stock_count(unit.warehouse, unit.variant)
    return balance.on_hand - tracked


def variant_serialization_summary(warehouse, variant):
    try:
        balance = InventoryBalance.objects.get(warehouse=warehouse, variant=variant)
    except InventoryBalance.DoesNotExist:
        return {"on_hand": 0, "tracked": 0, "unregistered": 0}
    tracked = _tracked_stock_count(warehouse, variant)
    return {
        "on_hand": balance.on_hand,
        "tracked": tracked,
        "unregistered": max(0, balance.on_hand - tracked),
    }
