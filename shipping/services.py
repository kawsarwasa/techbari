from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from payments.models import PaymentTransaction
from payments.services import PaymentError, capture_sales_payment, reconcile_payment, validate_method
from sales.models import SalesOrder
from sales.services import SalesOrderError, transition_order

from .models import CODSettlement, CODSettlementItem, CourierProvider, Shipment, ShipmentEvent, ZERO


class ShippingError(ValidationError):
    pass


ALLOWED_SHIPMENT_TRANSITIONS = {
    Shipment.Status.DRAFT: {Shipment.Status.READY, Shipment.Status.CANCELLED},
    Shipment.Status.READY: {Shipment.Status.HANDED_OVER, Shipment.Status.CANCELLED},
    Shipment.Status.HANDED_OVER: {
        Shipment.Status.IN_TRANSIT,
        Shipment.Status.OUT_FOR_DELIVERY,
        Shipment.Status.DELIVERED,
        Shipment.Status.FAILED,
        Shipment.Status.RETURNING,
    },
    Shipment.Status.IN_TRANSIT: {
        Shipment.Status.OUT_FOR_DELIVERY,
        Shipment.Status.DELIVERED,
        Shipment.Status.FAILED,
        Shipment.Status.RETURNING,
    },
    Shipment.Status.OUT_FOR_DELIVERY: {
        Shipment.Status.DELIVERED,
        Shipment.Status.FAILED,
        Shipment.Status.RETURNING,
    },
    Shipment.Status.FAILED: {
        Shipment.Status.OUT_FOR_DELIVERY,
        Shipment.Status.RETURNING,
        Shipment.Status.RETURNED,
    },
    Shipment.Status.RETURNING: {Shipment.Status.RETURNED},
    Shipment.Status.DELIVERED: set(),
    Shipment.Status.RETURNED: set(),
    Shipment.Status.CANCELLED: set(),
}


def _decimal(value, label):
    try:
        return Decimal(str(value if value not in (None, "") else "0"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ShippingError(f"Invalid {label}.") from exc


def _error_text(exc):
    if hasattr(exc, "messages"):
        return " ".join(str(message) for message in exc.messages)
    return str(exc)


def allowed_statuses(shipment):
    return tuple(ALLOWED_SHIPMENT_TRANSITIONS.get(shipment.status, set()))


def _event(
    shipment,
    event,
    *,
    previous_status="",
    new_status="",
    location="",
    note="",
    actor="",
    occurred_at=None,
):
    return ShipmentEvent.objects.create(
        shipment=shipment,
        event=event,
        previous_status=previous_status or "",
        new_status=new_status or "",
        location=location or "",
        note=note or "",
        actor=actor or "",
        occurred_at=occurred_at or timezone.now(),
    )


def _shipment_cod_status(shipment):
    if shipment.cod_expected <= ZERO:
        return Shipment.CODStatus.NOT_APPLICABLE
    if shipment.cod_collected <= ZERO:
        return Shipment.CODStatus.PENDING
    if shipment.cod_collected < shipment.cod_expected:
        return Shipment.CODStatus.DISPUTED
    if shipment.cod_settled >= shipment.cod_collected:
        return Shipment.CODStatus.SETTLED
    if shipment.cod_settled > ZERO:
        return Shipment.CODStatus.PARTIALLY_SETTLED
    return Shipment.CODStatus.COLLECTED


@transaction.atomic
def create_shipment(
    *,
    order,
    courier,
    shipment_date=None,
    expected_delivery_date=None,
    tracking_id="",
    courier_reference="",
    parcel_count=1,
    weight_kg=ZERO,
    courier_fee=None,
    cod_expected=None,
    notes="",
    actor="",
):
    order = SalesOrder.objects.select_for_update().select_related("customer", "warehouse").get(pk=order.pk)
    courier = CourierProvider.objects.select_for_update().get(pk=courier.pk)
    if Shipment.objects.filter(order=order).exists():
        raise ShippingError("This order already has a shipment. v1.9.0 keeps one fulfillment shipment per order.")
    if order.channel == SalesOrder.Channel.POS:
        raise ShippingError("POS counter sales do not require courier shipment records.")
    if order.status not in {SalesOrder.Status.CONFIRMED, SalesOrder.Status.PROCESSING, SalesOrder.Status.COMPLETED}:
        raise ShippingError("Only Confirmed, Processing or already Completed orders can be assigned to shipping.")
    if not courier.is_active:
        raise ShippingError("Select an active courier provider.")

    due = order.outstanding_amount
    cod_value = due if cod_expected in (None, "") else _decimal(cod_expected, "COD expected")
    if cod_value < ZERO:
        raise ShippingError("COD expected cannot be negative.")
    if cod_value > due:
        raise ShippingError(f"COD expected cannot exceed current order due ({due}).")
    if cod_value > ZERO and not courier.supports_cod:
        raise ShippingError("Selected courier is not configured for COD shipments.")

    fee = courier.default_courier_fee if courier_fee in (None, "") else _decimal(courier_fee, "courier fee")
    weight = _decimal(weight_kg, "weight")
    try:
        parcel_count = int(parcel_count or 1)
    except (TypeError, ValueError) as exc:
        raise ShippingError("Parcel count must be a whole number.") from exc
    if parcel_count <= 0:
        raise ShippingError("Parcel count must be greater than zero.")

    shipment = Shipment(
        order=order,
        courier=courier,
        shipment_date=shipment_date or timezone.localdate(),
        expected_delivery_date=expected_delivery_date,
        tracking_id=str(tracking_id or "").strip(),
        courier_reference=str(courier_reference or "").strip(),
        parcel_count=parcel_count,
        weight_kg=weight,
        courier_fee=fee,
        cod_expected=cod_value,
        cod_status=Shipment.CODStatus.PENDING if cod_value > ZERO else Shipment.CODStatus.NOT_APPLICABLE,
        notes=notes or "",
        actor=actor or "",
    )
    shipment.full_clean()
    shipment.save()
    _event(
        shipment,
        ShipmentEvent.Event.CREATED,
        new_status=shipment.status,
        note=f"Shipment created for {order.order_number} with {courier.name}.",
        actor=actor,
    )
    if shipment.tracking_id:
        _event(
            shipment,
            ShipmentEvent.Event.TRACKING,
            note=f"Tracking ID assigned: {shipment.tracking_id}.",
            actor=actor,
        )
    return shipment


def _complete_sales_fulfillment(order, *, actor=""):
    if order.status == SalesOrder.Status.COMPLETED:
        return order
    if order.status not in {SalesOrder.Status.CONFIRMED, SalesOrder.Status.PROCESSING}:
        raise ShippingError("The linked Sales Order is not ready for courier handover.")
    try:
        return transition_order(
            order=order,
            new_status=SalesOrder.Status.COMPLETED,
            actor=actor or "Shipping",
            note="Inventory issued when parcel was handed to courier.",
        )
    except (SalesOrderError, ValidationError) as exc:
        raise ShippingError(_error_text(exc)) from exc


@transaction.atomic
def change_shipment_status(
    *,
    shipment,
    new_status,
    cod_collected=None,
    location="",
    failure_reason="",
    note="",
    actor="",
):
    shipment = (
        Shipment.objects.select_for_update()
        .select_related("order", "courier", "order__warehouse")
        .get(pk=shipment.pk)
    )
    old_status = shipment.status
    if new_status == old_status:
        return shipment
    if new_status not in ALLOWED_SHIPMENT_TRANSITIONS.get(old_status, set()):
        label = dict(Shipment.Status.choices).get(new_status, str(new_status))
        raise ShippingError(f"Cannot move shipment from {shipment.get_status_display()} to {label}.")

    now = timezone.now()
    if new_status in {
        Shipment.Status.HANDED_OVER,
        Shipment.Status.IN_TRANSIT,
        Shipment.Status.OUT_FOR_DELIVERY,
        Shipment.Status.DELIVERED,
    }:
        _complete_sales_fulfillment(shipment.order, actor=actor)
        if not shipment.handed_over_at:
            shipment.handed_over_at = now

    if new_status == Shipment.Status.DELIVERED:
        if shipment.cod_expected > ZERO:
            if cod_collected in (None, "") and shipment.cod_collected <= ZERO:
                raise ShippingError("Enter the COD amount collected by the courier before marking this parcel Delivered.")
            collected = shipment.cod_collected if cod_collected in (None, "") else _decimal(cod_collected, "COD collected")
            if collected <= ZERO:
                raise ShippingError("COD collected must be greater than zero for a COD shipment.")
            if collected > shipment.cod_expected:
                raise ShippingError("COD collected cannot exceed expected COD.")
            if collected < shipment.cod_collected:
                raise ShippingError("COD collected cannot be reduced after it has been recorded.")
            shipment.cod_collected = collected
        shipment.delivered_at = now
        shipment.failure_reason = ""

    if new_status == Shipment.Status.FAILED:
        reason = str(failure_reason or note or "").strip()
        if not reason:
            raise ShippingError("Provide a delivery failure reason.")
        shipment.failure_reason = reason
        _event(
            shipment,
            ShipmentEvent.Event.DELIVERY_ATTEMPT,
            previous_status=old_status,
            new_status=new_status,
            location=location,
            note=reason,
            actor=actor,
        )

    if new_status in {Shipment.Status.RETURNING, Shipment.Status.RETURNED} and shipment.cod_expected > ZERO:
        shipment.cod_status = Shipment.CODStatus.DISPUTED
    if new_status == Shipment.Status.RETURNED:
        shipment.returned_at = now

    shipment.status = new_status
    if location:
        shipment.last_location = str(location).strip()
    shipment.cod_status = _shipment_cod_status(shipment) if new_status != Shipment.Status.RETURNING else shipment.cod_status
    shipment.full_clean()
    shipment.save()
    _event(
        shipment,
        ShipmentEvent.Event.STATUS,
        previous_status=old_status,
        new_status=new_status,
        location=location,
        note=note or f"Shipment status changed from {old_status} to {new_status}.",
        actor=actor,
    )
    if new_status == Shipment.Status.DELIVERED and shipment.cod_expected > ZERO:
        _event(
            shipment,
            ShipmentEvent.Event.COD_COLLECTION,
            location=location,
            note=f"Courier reported COD collection of {shipment.cod_collected} against expected {shipment.cod_expected}.",
            actor=actor,
        )
    return shipment


@transaction.atomic
def update_tracking(
    *,
    shipment,
    tracking_id="",
    courier_reference="",
    location="",
    note="",
    actor="",
):
    shipment = Shipment.objects.select_for_update().select_related("courier").get(pk=shipment.pk)
    old_tracking = shipment.tracking_id
    shipment.tracking_id = str(tracking_id or "").strip()
    shipment.courier_reference = str(courier_reference or "").strip()
    if location:
        shipment.last_location = str(location).strip()
    shipment.full_clean()
    shipment.save(update_fields=["tracking_id", "courier_reference", "last_location", "updated_at"])
    _event(
        shipment,
        ShipmentEvent.Event.TRACKING,
        location=location,
        note=note or f"Tracking changed from {old_tracking or '—'} to {shipment.tracking_id or '—'}.",
        actor=actor,
    )
    return shipment


@transaction.atomic
def record_delivery_attempt(*, shipment, location="", successful=False, reason="", note="", actor=""):
    shipment = Shipment.objects.select_for_update().get(pk=shipment.pk)
    text = note or reason or ("Successful delivery attempt." if successful else "Delivery attempt recorded.")
    return _event(
        shipment,
        ShipmentEvent.Event.DELIVERY_ATTEMPT,
        previous_status=shipment.status,
        new_status=shipment.status,
        location=location,
        note=text,
        actor=actor,
    )


@transaction.atomic
def post_cod_settlement(
    *,
    courier,
    settlement_date,
    payment_method,
    reference="",
    shipment_amounts,
    courier_deduction=ZERO,
    note="",
    actor="",
):
    courier = CourierProvider.objects.select_for_update().get(pk=courier.pk)
    if not shipment_amounts:
        raise ShippingError("Select at least one delivered COD shipment to settle.")
    try:
        validate_method(payment_method, channel="dashboard", reference=reference)
    except PaymentError as exc:
        raise ShippingError(_error_text(exc)) from exc

    normalized = []
    seen = set()
    for shipment_id, raw_amount in shipment_amounts.items():
        try:
            shipment_id = int(shipment_id)
        except (TypeError, ValueError) as exc:
            raise ShippingError("Invalid shipment selected for COD settlement.") from exc
        if shipment_id in seen:
            raise ShippingError("A shipment can appear only once in a settlement.")
        seen.add(shipment_id)
        amount = _decimal(raw_amount, "settlement amount")
        if amount <= ZERO:
            continue
        normalized.append((shipment_id, amount))
    if not normalized:
        raise ShippingError("Enter a positive settlement amount for at least one shipment.")

    shipments = {
        row.pk: row
        for row in Shipment.objects.select_for_update()
        .select_related("order", "courier")
        .filter(pk__in=[shipment_id for shipment_id, _ in normalized])
    }
    if len(shipments) != len(normalized):
        raise ShippingError("One or more selected shipments no longer exist.")

    gross = ZERO
    rows = []
    for shipment_id, amount in normalized:
        shipment = shipments[shipment_id]
        if shipment.courier_id != courier.pk:
            raise ShippingError(f"{shipment.shipment_no} belongs to another courier.")
        if shipment.status != Shipment.Status.DELIVERED:
            raise ShippingError(f"{shipment.shipment_no} is not Delivered and cannot be COD-settled.")
        if shipment.cod_collected <= ZERO:
            raise ShippingError(f"{shipment.shipment_no} has no recorded COD collection.")
        if amount > shipment.unsettled_cod:
            raise ShippingError(
                f"{shipment.shipment_no}: settlement cannot exceed unsettled COD ({shipment.unsettled_cod})."
            )
        shipment.order.refresh_from_db()
        if amount > shipment.order.outstanding_amount:
            raise ShippingError(
                f"{shipment.shipment_no}: settlement would overpay order {shipment.order.order_number}; current due is {shipment.order.outstanding_amount}."
            )
        gross += amount
        rows.append((shipment, amount))

    deduction = _decimal(courier_deduction, "courier deduction")
    if deduction < ZERO:
        raise ShippingError("Courier deduction cannot be negative.")
    if deduction > gross:
        raise ShippingError("Courier deduction cannot exceed gross COD settlement.")
    net = gross - deduction

    settlement = CODSettlement(
        courier=courier,
        settlement_date=settlement_date or timezone.localdate(),
        payment_method=payment_method,
        reference=str(reference or "").strip(),
        gross_amount=gross,
        courier_deduction=deduction,
        net_received=net,
        note=note or "",
        actor=actor or "",
    )
    settlement.full_clean()
    settlement.save()

    try:
        for shipment, amount in rows:
            payment = capture_sales_payment(
                order=shipment.order,
                amount=amount,
                method=payment_method,
                reference=settlement.reference,
                external_id=settlement.settlement_no,
                note=f"Courier COD settlement {settlement.settlement_no} via {courier.name}.",
                actor=actor or "Shipping COD",
                channel="dashboard",
                transaction_date=settlement.settlement_date,
                status=PaymentTransaction.Status.COMPLETED,
            )
            reconcile_payment(
                payment=payment,
                status=PaymentTransaction.ReconciliationStatus.RECONCILED,
                actor=actor or "Shipping COD",
                note=f"Reconciled from courier settlement {settlement.settlement_no}.",
            )
            CODSettlementItem.objects.create(
                settlement=settlement,
                shipment=shipment,
                amount=amount,
                payment_transaction=payment,
            )
            shipment.cod_settled += amount
            shipment.cod_status = _shipment_cod_status(shipment)
            shipment.full_clean()
            shipment.save(update_fields=["cod_settled", "cod_status", "updated_at"])
            _event(
                shipment,
                ShipmentEvent.Event.COD_SETTLEMENT,
                note=f"COD {amount} settled under {settlement.settlement_no}; Payment {payment.transaction_no} reconciled.",
                actor=actor,
            )
    except (PaymentError, ValidationError) as exc:
        raise ShippingError(_error_text(exc)) from exc
    return settlement
