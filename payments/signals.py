from decimal import Decimal

from django.db import connection
from django.db.models.signals import post_save
from django.dispatch import receiver

from purchasing.models import PurchasePayment
from sales.models import SalesOrder


def _payment_table_ready():
    try:
        return "payments_paymenttransaction" in connection.introspection.table_names()
    except Exception:
        return False


@receiver(post_save, sender=PurchasePayment)
def mirror_supplier_payment(sender, instance, created, raw=False, **kwargs):
    if raw or not created or not _payment_table_ready():
        return
    from .services import record_supplier_payment

    record_supplier_payment(purchase_payment=instance, actor=instance.actor or "Purchasing")


@receiver(post_save, sender=SalesOrder)
def mirror_legacy_sales_paid_amount(sender, instance, raw=False, **kwargs):
    """Keep pre-v1.8 code paths compatible without allowing a second payment truth.

    Existing Sales/POS code may still write ``SalesOrder.amount_paid`` directly. When that
    happens, mirror only the delta into the transaction ledger. Native v1.8 payment writes
    already have matching ledger totals, so this receiver becomes a no-op.
    """
    if raw or not instance.pk or not _payment_table_ready():
        return

    from .models import PaymentMethodConfig, PaymentTransaction
    from .services import capture_sales_payment, refundable_amount, refund_sales_payment, sales_payment_totals

    _, _, ledger_net = sales_payment_totals(instance)
    desired = Decimal(instance.amount_paid or 0)
    if desired == ledger_net:
        return

    if desired > ledger_net:
        method = (getattr(instance, "payment_method", "") or PaymentMethodConfig.Method.OTHER).lower()
        valid = {value for value, _ in PaymentMethodConfig.Method.choices}
        if method not in valid:
            method = PaymentMethodConfig.Method.OTHER
        capture_sales_payment(
            order=instance,
            amount=desired - ledger_net,
            method=method,
            reference=getattr(instance, "payment_reference", "") or "",
            note="Compatibility sync from SalesOrder.amount_paid.",
            actor="Sales compatibility",
            channel="dashboard",
        )
        return

    remaining = ledger_net - desired
    candidates = PaymentTransaction.objects.filter(
        sales_order=instance,
        kind=PaymentTransaction.Kind.SALE_PAYMENT,
        status__in=[PaymentTransaction.Status.COMPLETED, PaymentTransaction.Status.REVERSED],
    ).order_by("-transaction_date", "-id")
    for payment in candidates:
        available = refundable_amount(payment)
        if available <= 0:
            continue
        refund_amount = min(available, remaining)
        refund_sales_payment(
            payment=payment,
            amount=refund_amount,
            reference=payment.provider_reference,
            note="Compatibility refund from SalesOrder.amount_paid reduction.",
            actor="Sales compatibility",
        )
        remaining -= refund_amount
        if remaining <= 0:
            break
