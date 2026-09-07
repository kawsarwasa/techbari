from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from sales.models import SalesOrder

from .models import PaymentEvent, PaymentMethodConfig, PaymentTransaction


ZERO = Decimal("0.00")


class PaymentError(ValidationError):
    pass


def _decimal(value, label="amount"):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PaymentError(f"Invalid {label}.") from exc
    return result


def _event(transaction_obj, event, *, previous_status="", new_status="", note="", actor=""):
    return PaymentEvent.objects.create(
        transaction=transaction_obj,
        event=event,
        previous_status=previous_status or "",
        new_status=new_status or "",
        note=note or "",
        actor=actor or "",
    )


def get_method_config(method):
    method = str(method or "").strip().lower()
    valid = {value for value, _ in PaymentMethodConfig.Method.choices}
    if method not in valid:
        raise PaymentError("Select a valid payment method.")
    try:
        return PaymentMethodConfig.objects.get(method=method)
    except PaymentMethodConfig.DoesNotExist as exc:
        raise PaymentError("Payment method configuration is missing. Run migrations and configure Payments.") from exc


def validate_method(method, *, channel="dashboard", reference=""):
    config = get_method_config(method)
    if not config.is_active:
        raise PaymentError(f"{config.display_name} is currently disabled.")
    allowed = {
        "dashboard": config.allow_dashboard,
        "pos": config.allow_pos,
        "storefront": config.allow_storefront,
    }.get(channel, False)
    if not allowed:
        raise PaymentError(f"{config.display_name} is not enabled for {channel} payments.")
    if config.method not in {PaymentMethodConfig.Method.CASH, PaymentMethodConfig.Method.OTHER} and not str(reference or "").strip():
        raise PaymentError(f"A transaction/reference number is required for {config.display_name}.")
    return config


def sales_payment_totals(order):
    qs = PaymentTransaction.objects.filter(sales_order=order)
    incoming = qs.filter(
        direction=PaymentTransaction.Direction.IN,
        status__in=[PaymentTransaction.Status.COMPLETED, PaymentTransaction.Status.REVERSED],
    ).aggregate(total=Sum("amount"))["total"] or ZERO
    outgoing = qs.filter(
        direction=PaymentTransaction.Direction.OUT,
        status=PaymentTransaction.Status.COMPLETED,
    ).aggregate(total=Sum("amount"))["total"] or ZERO
    return incoming, outgoing, max(incoming - outgoing, ZERO)


def _sync_sales_order(order):
    order = SalesOrder.objects.select_for_update().get(pk=order.pk)
    incoming, outgoing, net = sales_payment_totals(order)
    if net <= ZERO:
        payment_status = SalesOrder.PaymentStatus.REFUNDED if incoming > ZERO and outgoing > ZERO else SalesOrder.PaymentStatus.UNPAID
    elif net >= order.grand_total:
        payment_status = SalesOrder.PaymentStatus.PAID
    else:
        payment_status = SalesOrder.PaymentStatus.PARTIAL
    order.amount_paid = net
    order.payment_status = payment_status
    order.save(update_fields=["amount_paid", "payment_status", "updated_at"])
    return order


@transaction.atomic
def capture_sales_payment(
    *,
    order,
    amount,
    method,
    reference="",
    external_id="",
    note="",
    actor="",
    channel="dashboard",
    transaction_date=None,
    status=PaymentTransaction.Status.COMPLETED,
):
    order = SalesOrder.objects.select_for_update().get(pk=order.pk)
    if order.status in {SalesOrder.Status.DRAFT, SalesOrder.Status.CANCELLED}:
        raise PaymentError("Draft or cancelled orders cannot receive payments.")
    amount = _decimal(amount)
    if amount <= ZERO:
        raise PaymentError("Payment amount must be greater than zero.")
    config = validate_method(method, channel=channel, reference=reference)
    if status not in {PaymentTransaction.Status.PENDING, PaymentTransaction.Status.COMPLETED, PaymentTransaction.Status.FAILED}:
        raise PaymentError("Invalid initial payment status.")
    _, _, net_paid = sales_payment_totals(order)
    if status == PaymentTransaction.Status.COMPLETED and amount > max(order.grand_total - net_paid, ZERO):
        raise PaymentError(f"Payment cannot exceed outstanding amount ({max(order.grand_total - net_paid, ZERO)}).")
    payment = PaymentTransaction(
        sales_order=order,
        kind=PaymentTransaction.Kind.SALE_PAYMENT,
        direction=PaymentTransaction.Direction.IN,
        method=config.method,
        status=status,
        amount=amount,
        provider_reference=str(reference or "").strip(),
        external_id=str(external_id or "").strip(),
        transaction_date=transaction_date or timezone.localdate(),
        note=note or "",
        created_by=actor or "",
    )
    payment.full_clean()
    payment.save()
    _event(payment, PaymentEvent.Event.CREATED, new_status=payment.status, note=note, actor=actor)
    if status == PaymentTransaction.Status.COMPLETED:
        order.payment_method = config.method if hasattr(order, "payment_method") else ""
        order.payment_reference = payment.provider_reference if hasattr(order, "payment_reference") else ""
        update_fields = ["updated_at"]
        if hasattr(order, "payment_method"):
            update_fields.extend(["payment_method", "payment_reference"])
        order.save(update_fields=update_fields)
        _sync_sales_order(order)
    return payment


@transaction.atomic
def complete_pending_payment(*, payment, reference="", external_id="", actor="", note=""):
    payment = PaymentTransaction.objects.select_for_update().select_related("sales_order").get(pk=payment.pk)
    if payment.kind != PaymentTransaction.Kind.SALE_PAYMENT or payment.status != PaymentTransaction.Status.PENDING:
        raise PaymentError("Only pending sale payments can be completed.")
    order = SalesOrder.objects.select_for_update().get(pk=payment.sales_order_id)
    _, _, net_paid = sales_payment_totals(order)
    if payment.amount > max(order.grand_total - net_paid, ZERO):
        raise PaymentError("Completing this transaction would overpay the order.")
    previous = payment.status
    if reference:
        payment.provider_reference = str(reference).strip()
    if external_id:
        payment.external_id = str(external_id).strip()
    validate_method(payment.method, channel="dashboard", reference=payment.provider_reference)
    payment.status = PaymentTransaction.Status.COMPLETED
    payment.save(update_fields=["provider_reference", "external_id", "status", "updated_at"])
    _event(payment, PaymentEvent.Event.STATUS, previous_status=previous, new_status=payment.status, note=note or "Pending payment completed.", actor=actor)
    _sync_sales_order(order)
    return payment


@transaction.atomic
def fail_pending_payment(*, payment, actor="", note=""):
    payment = PaymentTransaction.objects.select_for_update().get(pk=payment.pk)
    if payment.status != PaymentTransaction.Status.PENDING:
        raise PaymentError("Only pending payments can be marked failed.")
    previous = payment.status
    payment.status = PaymentTransaction.Status.FAILED
    payment.save(update_fields=["status", "updated_at"])
    _event(payment, PaymentEvent.Event.STATUS, previous_status=previous, new_status=payment.status, note=note or "Payment marked failed.", actor=actor)
    return payment


def refundable_amount(payment):
    if payment.kind != PaymentTransaction.Kind.SALE_PAYMENT:
        return ZERO
    used = payment.child_transactions.filter(
        kind__in=[PaymentTransaction.Kind.REFUND, PaymentTransaction.Kind.REVERSAL],
        status=PaymentTransaction.Status.COMPLETED,
    ).aggregate(total=Sum("amount"))["total"] or ZERO
    return max(payment.amount - used, ZERO)


@transaction.atomic
def refund_sales_payment(*, payment, amount, reference="", note="", actor=""):
    payment = PaymentTransaction.objects.select_for_update().select_related("sales_order").get(pk=payment.pk)
    if payment.kind != PaymentTransaction.Kind.SALE_PAYMENT or payment.status not in {PaymentTransaction.Status.COMPLETED, PaymentTransaction.Status.REVERSED}:
        raise PaymentError("Only a completed sale payment can be refunded.")
    amount = _decimal(amount, "refund amount")
    if amount <= ZERO:
        raise PaymentError("Refund amount must be greater than zero.")
    available = refundable_amount(payment)
    if amount > available:
        raise PaymentError(f"Refund cannot exceed the remaining refundable amount ({available}).")
    validate_method(payment.method, channel="dashboard", reference=reference or payment.provider_reference)
    refund = PaymentTransaction(
        sales_order=payment.sales_order,
        parent_transaction=payment,
        kind=PaymentTransaction.Kind.REFUND,
        direction=PaymentTransaction.Direction.OUT,
        method=payment.method,
        status=PaymentTransaction.Status.COMPLETED,
        amount=amount,
        provider_reference=str(reference or payment.provider_reference or "").strip(),
        transaction_date=timezone.localdate(),
        note=note or f"Refund against {payment.transaction_no}.",
        created_by=actor or "",
    )
    refund.full_clean()
    refund.save()
    _event(refund, PaymentEvent.Event.CREATED, new_status=refund.status, note=refund.note, actor=actor)
    _event(payment, PaymentEvent.Event.REFUND, note=f"Refund {refund.transaction_no} created for {amount}.", actor=actor)
    _sync_sales_order(payment.sales_order)
    return refund


@transaction.atomic
def reverse_sales_payment(*, payment, reference="", note="", actor=""):
    payment = PaymentTransaction.objects.select_for_update().select_related("sales_order").get(pk=payment.pk)
    if payment.kind != PaymentTransaction.Kind.SALE_PAYMENT or payment.status != PaymentTransaction.Status.COMPLETED:
        raise PaymentError("Only a completed sale payment can be reversed.")
    if payment.reconciliation_status == PaymentTransaction.ReconciliationStatus.RECONCILED:
        raise PaymentError("A reconciled transaction cannot be reversed. Create a refund instead.")
    if refundable_amount(payment) != payment.amount:
        raise PaymentError("A payment with an existing refund/reversal cannot be fully reversed.")
    validate_method(payment.method, channel="dashboard", reference=reference or payment.provider_reference)
    reversal = PaymentTransaction(
        sales_order=payment.sales_order,
        parent_transaction=payment,
        kind=PaymentTransaction.Kind.REVERSAL,
        direction=PaymentTransaction.Direction.OUT,
        method=payment.method,
        status=PaymentTransaction.Status.COMPLETED,
        amount=payment.amount,
        provider_reference=str(reference or payment.provider_reference or "").strip(),
        transaction_date=timezone.localdate(),
        note=note or f"Reversal of {payment.transaction_no}.",
        created_by=actor or "",
    )
    reversal.full_clean()
    reversal.save()
    previous = payment.status
    payment.status = PaymentTransaction.Status.REVERSED
    payment.save(update_fields=["status", "updated_at"])
    _event(reversal, PaymentEvent.Event.CREATED, new_status=reversal.status, note=reversal.note, actor=actor)
    _event(payment, PaymentEvent.Event.REVERSAL, previous_status=previous, new_status=payment.status, note=f"Reversed by {reversal.transaction_no}.", actor=actor)
    _sync_sales_order(payment.sales_order)
    return reversal


@transaction.atomic
def reconcile_payment(*, payment, status=PaymentTransaction.ReconciliationStatus.RECONCILED, actor="", note=""):
    payment = PaymentTransaction.objects.select_for_update().get(pk=payment.pk)
    valid = {value for value, _ in PaymentTransaction.ReconciliationStatus.choices}
    if status not in valid:
        raise PaymentError("Invalid reconciliation status.")
    payment.reconciliation_status = status
    if status == PaymentTransaction.ReconciliationStatus.RECONCILED:
        payment.reconciled_at = timezone.now()
        payment.reconciled_by = actor or "Dashboard"
    else:
        payment.reconciled_at = None
        payment.reconciled_by = ""
    payment.save(update_fields=["reconciliation_status", "reconciled_at", "reconciled_by", "updated_at"])
    _event(payment, PaymentEvent.Event.RECONCILIATION, note=note or f"Reconciliation set to {payment.get_reconciliation_status_display()}.", actor=actor)
    return payment


@transaction.atomic
def record_supplier_payment(*, purchase_payment, actor=""):
    existing = PaymentTransaction.objects.filter(purchase_payment=purchase_payment).first()
    if existing:
        return existing
    method = purchase_payment.method if purchase_payment.method in {value for value, _ in PaymentMethodConfig.Method.choices} else PaymentMethodConfig.Method.OTHER
    config = get_method_config(method)
    payment = PaymentTransaction(
        purchase_payment=purchase_payment,
        kind=PaymentTransaction.Kind.SUPPLIER_PAYMENT,
        direction=PaymentTransaction.Direction.OUT,
        method=config.method,
        status=PaymentTransaction.Status.COMPLETED,
        amount=purchase_payment.amount,
        provider_reference=purchase_payment.reference,
        transaction_date=purchase_payment.payment_date,
        note=purchase_payment.note or f"Supplier payment for {purchase_payment.purchase.po_number}.",
        created_by=actor or purchase_payment.actor,
    )
    payment.full_clean()
    payment.save()
    _event(payment, PaymentEvent.Event.CREATED, new_status=payment.status, note=payment.note, actor=actor or purchase_payment.actor)
    return payment
