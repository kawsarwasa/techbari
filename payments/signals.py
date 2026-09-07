from django.db import connection
from django.db.models.signals import post_save
from django.dispatch import receiver

from purchasing.models import PurchasePayment


def _payment_table_ready():
    try:
        return "payments_paymenttransaction" in connection.introspection.table_names()
    except Exception:
        return False


@receiver(post_save, sender=PurchasePayment)
def mirror_supplier_payment(sender, instance, created, **kwargs):
    if not created or not _payment_table_ready():
        return
    from .services import record_supplier_payment

    record_supplier_payment(purchase_payment=instance, actor=instance.actor or "Purchasing")
