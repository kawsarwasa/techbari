from django.db import connection
from django.db.models.signals import post_save
from django.dispatch import receiver

from payments.models import PaymentTransaction
from purchasing.models import PurchaseOrder, PurchaseReceiptItem, PurchaseReturnItem
from returns.models import SalesReturn
from sales.models import SalesOrder
from shipping.models import CODSettlement


def _accounting_tables_ready():
    try:
        names = set(connection.introspection.table_names())
        return {
            "accounting_account",
            "accounting_journalentry",
            "accounting_journalline",
        }.issubset(names)
    except Exception:
        return False


@receiver(post_save, sender=SalesOrder)
def account_completed_sale(sender, instance, raw=False, **kwargs):
    if raw or not _accounting_tables_ready() or instance.status != SalesOrder.Status.COMPLETED:
        return
    from .services import post_sales_order

    post_sales_order(instance, actor=instance.created_by or "Sales")


@receiver(post_save, sender=PaymentTransaction)
def account_payment_transaction(sender, instance, raw=False, **kwargs):
    if raw or not _accounting_tables_ready():
        return
    if instance.status not in {PaymentTransaction.Status.COMPLETED, PaymentTransaction.Status.REVERSED}:
        return
    from .services import post_payment_transaction

    post_payment_transaction(instance, actor=instance.created_by or "Payments")


@receiver(post_save, sender=PurchaseReceiptItem)
def account_purchase_receipt_item(sender, instance, created, raw=False, **kwargs):
    if raw or not created or not _accounting_tables_ready():
        return
    from .services import post_purchase_receipt_item

    post_purchase_receipt_item(instance, actor=instance.receipt.actor or "Purchasing")


@receiver(post_save, sender=PurchaseOrder)
def account_purchase_overhead(sender, instance, raw=False, **kwargs):
    if raw or not _accounting_tables_ready() or instance.status != PurchaseOrder.Status.RECEIVED:
        return
    from .services import post_purchase_overhead

    post_purchase_overhead(instance, actor=instance.actor or "Purchasing")


@receiver(post_save, sender=PurchaseReturnItem)
def account_purchase_return_item(sender, instance, created, raw=False, **kwargs):
    if raw or not created or not _accounting_tables_ready():
        return
    from .services import post_purchase_return_item

    post_purchase_return_item(instance, actor=instance.purchase_return.actor or "Purchasing")


@receiver(post_save, sender=SalesReturn)
def account_completed_sales_return(sender, instance, raw=False, **kwargs):
    if raw or not _accounting_tables_ready() or instance.status != SalesReturn.Status.COMPLETED:
        return
    from .services import post_sales_return

    post_sales_return(instance, actor=instance.actor or "Returns")


@receiver(post_save, sender=CODSettlement)
def account_courier_deduction(sender, instance, raw=False, **kwargs):
    if raw or not _accounting_tables_ready() or not instance.courier_deduction:
        return
    from .services import post_cod_settlement

    post_cod_settlement(instance, actor=instance.actor or "Shipping")
