from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from inventory.models import StockMovement, Warehouse
from inventory.services import InventoryError, post_movement
from payments.models import PaymentTransaction
from payments.services import (
    PaymentError,
    refundable_amount,
    refund_sales_payment,
    sales_payment_totals,
    sync_sales_order_payment,
)
from sales.models import SalesOrder, SalesOrderItem
from serial_tracking.models import SerializedUnit
from serial_tracking.services import SerialTrackingError, change_serial_unit_status

from .models import SalesReturn, SalesReturnEvent, SalesReturnItem, SalesReturnRefund, ZERO


MONEY = Decimal("0.01")
CONSUMING_STATUSES = {
    SalesReturn.Status.REQUESTED,
    SalesReturn.Status.APPROVED,
    SalesReturn.Status.RECEIVED,
    SalesReturn.Status.COMPLETED,
}


class ReturnError(ValidationError):
    pass


def _decimal(value, label):
    try:
        return Decimal(str(value if value not in (None, "") else "0")).quantize(MONEY, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ReturnError(f"Invalid {label}.") from exc


def _error_text(exc):
    if hasattr(exc, "messages"):
        return " ".join(str(value) for value in exc.messages)
    return str(exc)


def _event(sales_return, event, *, previous_status="", new_status="", note="", actor=""):
    return SalesReturnEvent.objects.create(
        sales_return=sales_return,
        event=event,
        previous_status=previous_status or "",
        new_status=new_status or "",
        note=note or "",
        actor=actor or "",
    )


def _consuming_items(order_item, *, exclude_return_id=None):
    qs = SalesReturnItem.objects.filter(
        order_item=order_item,
        sales_return__status__in=CONSUMING_STATUSES,
    )
    if exclude_return_id:
        qs = qs.exclude(sales_return_id=exclude_return_id)
    return qs


def available_return_quantity(order_item):
    consumed = _consuming_items(order_item).aggregate(total=Sum("quantity"))["total"] or 0
    return max(int(order_item.issued_quantity or 0) - int(consumed), 0)


def available_return_credit(order_item):
    consumed = _consuming_items(order_item).aggregate(total=Sum("refund_amount"))["total"] or ZERO
    return max((order_item.line_total or ZERO) - consumed, ZERO)


def _validate_return_source(order, source):
    if source == SalesReturn.Source.POS and order.channel != SalesOrder.Channel.POS:
        raise ReturnError("POS / Counter Return can only be used for a POS Sales Order.")
    if source == SalesReturn.Source.COURIER_RETURN:
        try:
            shipment = order.shipment
        except ObjectDoesNotExist as exc:
            raise ReturnError("Courier Return requires a shipment linked to this Sales Order.") from exc
        if shipment.status != "returned":
            raise ReturnError("Courier Return can only be opened after the shipment is Returned to Merchant.")


def _normalize_item_rows(order, item_rows):
    locked_items = {
        row.pk: row
        for row in SalesOrderItem.objects.select_for_update()
        .select_related("variant", "variant__product")
        .filter(order=order)
    }
    if not item_rows:
        raise ReturnError("Select at least one sold item to return.")

    normalized = []
    current_qty = defaultdict(int)
    current_credit = defaultdict(lambda: ZERO)
    used_serial_ids = set()

    for index, raw in enumerate(item_rows, start=1):
        raw_item = raw.get("order_item") or raw.get("order_item_id")
        try:
            item_id = int(getattr(raw_item, "pk", raw_item))
        except (TypeError, ValueError) as exc:
            raise ReturnError(f"Return line {index} has an invalid Sales Order item.") from exc
        item = locked_items.get(item_id)
        if not item:
            raise ReturnError(f"Return line {index} does not belong to {order.order_number}.")

        try:
            quantity = int(raw.get("quantity") or 0)
        except (TypeError, ValueError) as exc:
            raise ReturnError(f"Return line {index} has an invalid quantity.") from exc
        if quantity <= 0:
            raise ReturnError("Return quantity must be greater than zero.")

        remaining_quantity = available_return_quantity(item) - current_qty[item.pk]
        if quantity > remaining_quantity:
            raise ReturnError(
                f"{item.sku_snapshot}: return quantity cannot exceed remaining sold quantity ({remaining_quantity})."
            )

        refund_amount = _decimal(raw.get("refund_amount"), "refund/credit amount")
        if refund_amount < ZERO:
            raise ReturnError("Refund/credit amount cannot be negative.")
        remaining_credit = available_return_credit(item) - current_credit[item.pk]
        proportional_cap = (
            (item.line_total * Decimal(quantity) / Decimal(item.quantity)).quantize(MONEY, rounding=ROUND_HALF_UP)
            if item.quantity
            else ZERO
        )
        line_cap = min(remaining_credit, proportional_cap)
        if refund_amount > line_cap:
            raise ReturnError(
                f"{item.sku_snapshot}: refund/credit cannot exceed {line_cap} for the selected quantity."
            )

        condition = str(raw.get("condition") or SalesReturnItem.Condition.GOOD)
        disposition = str(raw.get("disposition") or SalesReturnItem.Disposition.RESTOCK)
        if condition not in {value for value, _ in SalesReturnItem.Condition.choices}:
            raise ReturnError(f"Return line {index} has an invalid item condition.")
        if disposition not in {value for value, _ in SalesReturnItem.Disposition.choices}:
            raise ReturnError(f"Return line {index} has an invalid stock disposition.")

        unit = None
        raw_unit = raw.get("serialized_unit") or raw.get("serialized_unit_id")
        if raw_unit not in (None, ""):
            try:
                unit_id = int(getattr(raw_unit, "pk", raw_unit))
            except (TypeError, ValueError) as exc:
                raise ReturnError(f"Return line {index} has an invalid Serial/IMEI unit.") from exc
            if unit_id in used_serial_ids:
                raise ReturnError("A Serial/IMEI unit can only appear once in the same return.")
            unit = (
                SerializedUnit.objects.select_for_update()
                .select_related("variant", "warehouse")
                .filter(pk=unit_id)
                .first()
            )
            if not unit or unit.variant_id != item.variant_id:
                raise ReturnError(f"{item.sku_snapshot}: selected Serial/IMEI does not match this SKU.")
            if quantity != 1:
                raise ReturnError("A serialized return line must have quantity 1.")
            if unit.status != SerializedUnit.Status.SOLD:
                raise ReturnError(f"Serialized unit {unit.display_identifier} is not currently Sold.")
            if unit.sales_reference and unit.sales_reference != order.order_number:
                raise ReturnError(
                    f"Serialized unit {unit.display_identifier} is linked to another Sales Order ({unit.sales_reference})."
                )
            already_open = SalesReturnItem.objects.filter(
                serialized_unit=unit,
                sales_return__status__in=CONSUMING_STATUSES,
            ).exists()
            if already_open:
                raise ReturnError(f"Serialized unit {unit.display_identifier} is already part of another active return.")
            used_serial_ids.add(unit_id)

        current_qty[item.pk] += quantity
        current_credit[item.pk] += refund_amount
        normalized.append(
            {
                "order_item": item,
                "variant": item.variant,
                "quantity": quantity,
                "condition": condition,
                "disposition": disposition,
                "refund_amount": refund_amount,
                "serialized_unit": unit,
                "note": str(raw.get("note") or "").strip(),
            }
        )
    return normalized


@transaction.atomic
def create_sales_return(
    *,
    order,
    warehouse,
    source,
    resolution,
    reason_category,
    requested_date=None,
    source_reference="",
    refund_reference="",
    customer_note="",
    internal_note="",
    item_rows,
    actor="",
):
    order = SalesOrder.objects.select_for_update().select_related("customer", "warehouse").get(pk=order.pk)
    warehouse = Warehouse.objects.select_for_update().get(pk=warehouse.pk)
    if order.status != SalesOrder.Status.COMPLETED:
        raise ReturnError("Only Completed / Sold orders can enter the Returns module.")
    if not warehouse.is_active:
        raise ReturnError("Returns must be received into an active warehouse.")
    if source not in {value for value, _ in SalesReturn.Source.choices}:
        raise ReturnError("Select a valid return source.")
    if resolution not in {value for value, _ in SalesReturn.Resolution.choices}:
        raise ReturnError("Select a valid return resolution.")
    if reason_category not in {value for value, _ in SalesReturn.Reason.choices}:
        raise ReturnError("Select a valid return reason.")
    _validate_return_source(order, source)

    rows = _normalize_item_rows(order, item_rows)
    credit_total = sum((row["refund_amount"] for row in rows), ZERO)
    if resolution == SalesReturn.Resolution.NO_REFUND and credit_total != ZERO:
        raise ReturnError("No Refund returns must have zero refund/credit amount on every item.")
    if resolution == SalesReturn.Resolution.REFUND and credit_total <= ZERO:
        raise ReturnError("Refund / Credit returns require a positive approved credit amount.")

    sales_return = SalesReturn(
        order=order,
        warehouse=warehouse,
        source=source,
        resolution=resolution,
        reason_category=reason_category,
        requested_date=requested_date or timezone.localdate(),
        source_reference=str(source_reference or "").strip(),
        refund_reference=str(refund_reference or "").strip(),
        customer_note=customer_note or "",
        internal_note=internal_note or "",
        actor=actor or "",
    )
    sales_return.full_clean()
    sales_return.save()

    for row in rows:
        item = SalesReturnItem(
            sales_return=sales_return,
            order_item=row["order_item"],
            variant=row["variant"],
            product_snapshot=row["order_item"].product_snapshot,
            sku_snapshot=row["order_item"].sku_snapshot,
            quantity=row["quantity"],
            condition=row["condition"],
            disposition=row["disposition"],
            refund_amount=row["refund_amount"],
            serialized_unit=row["serialized_unit"],
            note=row["note"],
        )
        item.full_clean()
        item.save()

    _event(
        sales_return,
        SalesReturnEvent.Event.CREATED,
        new_status=sales_return.status,
        note=f"Return opened for {order.order_number}; approved credit requested: {credit_total}.",
        actor=actor,
    )
    return sales_return


ALLOWED_TRANSITIONS = {
    SalesReturn.Status.REQUESTED: {
        SalesReturn.Status.APPROVED,
        SalesReturn.Status.REJECTED,
        SalesReturn.Status.CANCELLED,
    },
    SalesReturn.Status.APPROVED: {
        SalesReturn.Status.RECEIVED,
        SalesReturn.Status.REJECTED,
        SalesReturn.Status.CANCELLED,
    },
    SalesReturn.Status.RECEIVED: {SalesReturn.Status.REJECTED},
    SalesReturn.Status.COMPLETED: set(),
    SalesReturn.Status.REJECTED: set(),
    SalesReturn.Status.CANCELLED: set(),
}


@transaction.atomic
def transition_sales_return(*, sales_return, new_status, note="", actor=""):
    sales_return = SalesReturn.objects.select_for_update().get(pk=sales_return.pk)
    old_status = sales_return.status
    if new_status == old_status:
        return sales_return
    if new_status == SalesReturn.Status.COMPLETED:
        raise ReturnError("Use complete_sales_return() to finish a return so Inventory and Payment remain atomic.")
    if new_status not in ALLOWED_TRANSITIONS.get(old_status, set()):
        label = dict(SalesReturn.Status.choices).get(new_status, str(new_status))
        raise ReturnError(f"Cannot move return from {sales_return.get_status_display()} to {label}.")
    sales_return.status = new_status
    if new_status == SalesReturn.Status.RECEIVED:
        sales_return.received_date = timezone.localdate()
    sales_return.save(update_fields=["status", "received_date", "updated_at"])
    _event(
        sales_return,
        SalesReturnEvent.Event.STATUS,
        previous_status=old_status,
        new_status=new_status,
        note=note or f"Return status changed from {old_status} to {new_status}.",
        actor=actor,
    )
    return sales_return


def approve_sales_return(*, sales_return, note="", actor=""):
    return transition_sales_return(
        sales_return=sales_return,
        new_status=SalesReturn.Status.APPROVED,
        note=note,
        actor=actor,
    )


def receive_sales_return(*, sales_return, note="", actor=""):
    return transition_sales_return(
        sales_return=sales_return,
        new_status=SalesReturn.Status.RECEIVED,
        note=note,
        actor=actor,
    )


def reject_sales_return(*, sales_return, note="", actor=""):
    return transition_sales_return(
        sales_return=sales_return,
        new_status=SalesReturn.Status.REJECTED,
        note=note,
        actor=actor,
    )


def cancel_sales_return(*, sales_return, note="", actor=""):
    return transition_sales_return(
        sales_return=sales_return,
        new_status=SalesReturn.Status.CANCELLED,
        note=note,
        actor=actor,
    )


def _process_return_item_inventory(sales_return, item, *, actor=""):
    if item.restocked_quantity:
        raise ReturnError(f"{item.sku_snapshot}: inventory has already been processed for this return line.")

    if item.serialized_unit_id:
        unit = (
            SerializedUnit.objects.select_for_update()
            .select_related("variant", "warehouse")
            .get(pk=item.serialized_unit_id)
        )
        if unit.status != SerializedUnit.Status.SOLD:
            raise ReturnError(
                f"Serialized unit {unit.display_identifier} is no longer Sold; review the Serial/IMEI lifecycle before completing this return."
            )
        target_status = {
            SalesReturnItem.Disposition.RESTOCK: SerializedUnit.Status.RETURNED,
            SalesReturnItem.Disposition.DAMAGED: SerializedUnit.Status.DAMAGED,
            SalesReturnItem.Disposition.WARRANTY: SerializedUnit.Status.WARRANTY_SERVICE,
            SalesReturnItem.Disposition.SCRAP: SerializedUnit.Status.SCRAPPED,
            SalesReturnItem.Disposition.NO_STOCK: SerializedUnit.Status.DAMAGED,
        }[item.disposition]
        if unit.warehouse_id != sales_return.warehouse_id:
            # Sold units are not stock-bearing, so their warehouse pointer can safely be moved to the physical return location.
            unit.warehouse = sales_return.warehouse
            unit.save(update_fields=["warehouse", "updated_at"])
        try:
            change_serial_unit_status(
                unit,
                target_status,
                actor=actor,
                note=f"Sales return {sales_return.return_no}: {item.get_disposition_display()}.",
                reference_no=sales_return.return_no,
            )
        except SerialTrackingError as exc:
            raise ReturnError(_error_text(exc)) from exc
        if item.disposition == SalesReturnItem.Disposition.RESTOCK:
            item.restocked_quantity = 1
            item.save(update_fields=["restocked_quantity"])
        return

    if item.disposition == SalesReturnItem.Disposition.RESTOCK:
        try:
            post_movement(
                warehouse=sales_return.warehouse,
                variant=item.variant,
                movement_type=StockMovement.Type.RETURN_IN,
                quantity_delta=item.quantity,
                reference_type="sales_return",
                reference_no=sales_return.return_no,
                note=f"Accepted sales return for {sales_return.order.order_number}. {item.note}".strip(),
                actor=actor,
            )
        except InventoryError as exc:
            raise ReturnError(_error_text(exc)) from exc
        item.restocked_quantity = item.quantity
        item.save(update_fields=["restocked_quantity"])


def _refund_sources(order):
    return list(
        PaymentTransaction.objects.select_for_update()
        .filter(
            sales_order=order,
            kind=PaymentTransaction.Kind.SALE_PAYMENT,
            status__in=[PaymentTransaction.Status.COMPLETED, PaymentTransaction.Status.REVERSED],
        )
        .order_by("transaction_date", "id")
    )


@transaction.atomic
def complete_sales_return(*, sales_return, note="", actor=""):
    sales_return = (
        SalesReturn.objects.select_for_update()
        .select_related("order", "warehouse", "order__customer")
        .prefetch_related("items__variant", "items__serialized_unit")
        .get(pk=sales_return.pk)
    )
    if sales_return.status != SalesReturn.Status.RECEIVED:
        raise ReturnError("A return must be Approved and physically Received before it can be completed.")

    order = SalesOrder.objects.select_for_update().get(pk=sales_return.order_id)
    if order.status != SalesOrder.Status.COMPLETED:
        raise ReturnError("The linked Sales Order must remain Completed / Sold while processing a return.")

    items = list(
        SalesReturnItem.objects.select_for_update()
        .select_related("variant", "serialized_unit", "order_item")
        .filter(sales_return=sales_return)
        .order_by("id")
    )
    if not items:
        raise ReturnError("Return has no items to complete.")

    credit_total = sum((item.refund_amount for item in items), ZERO)
    if sales_return.resolution == SalesReturn.Resolution.NO_REFUND:
        credit_total = ZERO
    if order.return_credit_amount + credit_total > order.grand_total:
        raise ReturnError("Completing this return would credit more than the Sales Order total.")

    _, _, net_paid_before = sales_payment_totals(order)
    new_credit_total = order.return_credit_amount + credit_total
    new_payable = max(order.grand_total - new_credit_total, ZERO)
    cash_refund_due = max(net_paid_before - new_payable, ZERO)
    cash_refund_due = min(cash_refund_due, credit_total)

    sources = _refund_sources(order) if cash_refund_due > ZERO else []
    refundable_total = sum((refundable_amount(payment) for payment in sources), ZERO)
    if cash_refund_due > refundable_total:
        raise ReturnError(
            f"Return needs a cash refund of {cash_refund_due}, but only {refundable_total} remains refundable in the Payment ledger."
        )

    for item in items:
        _process_return_item_inventory(sales_return, item, actor=actor)
    _event(
        sales_return,
        SalesReturnEvent.Event.INVENTORY,
        note=f"Return inventory processed; sellable restock quantity: {sum(item.restocked_quantity for item in items)}.",
        actor=actor,
    )

    if credit_total > ZERO:
        order.return_credit_amount = new_credit_total
        order.save(update_fields=["return_credit_amount", "updated_at"])
        _event(
            sales_return,
            SalesReturnEvent.Event.CREDIT,
            note=f"Return credit {credit_total} applied to Sales Order {order.order_number}.",
            actor=actor,
        )

    remaining_refund = cash_refund_due
    if remaining_refund > ZERO:
        for source_payment in sources:
            available = refundable_amount(source_payment)
            if available <= ZERO:
                continue
            amount = min(available, remaining_refund)
            try:
                refund = refund_sales_payment(
                    payment=source_payment,
                    amount=amount,
                    reference=sales_return.refund_reference,
                    note=f"Sales return {sales_return.return_no}. {note}".strip(),
                    actor=actor or "Returns",
                )
            except PaymentError as exc:
                raise ReturnError(_error_text(exc)) from exc
            link = SalesReturnRefund(
                sales_return=sales_return,
                source_payment=source_payment,
                refund_transaction=refund,
                amount=amount,
            )
            link.full_clean()
            link.save()
            remaining_refund -= amount
            if remaining_refund <= ZERO:
                break
        if remaining_refund > ZERO:
            raise ReturnError("Payment refund allocation did not fully cover the required refund amount.")
        _event(
            sales_return,
            SalesReturnEvent.Event.REFUND,
            note=f"Cash/payment refund {cash_refund_due} posted through the Payment ledger.",
            actor=actor,
        )

    try:
        sync_sales_order_payment(order)
    except PaymentError as exc:
        raise ReturnError(_error_text(exc)) from exc

    old_status = sales_return.status
    sales_return.status = SalesReturn.Status.COMPLETED
    sales_return.completed_date = timezone.localdate()
    sales_return.save(update_fields=["status", "completed_date", "updated_at"])
    _event(
        sales_return,
        SalesReturnEvent.Event.STATUS,
        previous_status=old_status,
        new_status=sales_return.status,
        note=note or "Return completed atomically with Inventory and Payment processing.",
        actor=actor,
    )
    return sales_return
