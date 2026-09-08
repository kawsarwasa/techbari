import logging

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from inventory.models import InventoryBalance
from payments.models import PaymentTransaction
from sales.models import SalesOrder
from shipping.models import Shipment

from .services import enqueue_low_stock_event, enqueue_order_event, enqueue_payment_event, enqueue_shipping_event

logger = logging.getLogger(__name__)


def _old_value(model, instance, field):
    if not instance.pk:
        return None
    return model.objects.filter(pk=instance.pk).values_list(field, flat=True).first()


def _after_commit(callback, *args):
    def runner():
        try:
            callback(*args)
        except Exception:
            logger.exception("Integration event enqueue failed: %s %s", getattr(callback, "__name__", callback), args)
    transaction.on_commit(runner)


def _load_order(pk, event):
    order = SalesOrder.objects.select_related("customer", "warehouse").prefetch_related("items").get(pk=pk)
    enqueue_order_event(order, event)


def _load_payment(pk, event):
    payment = PaymentTransaction.objects.select_related("sales_order").get(pk=pk)
    enqueue_payment_event(payment, event)


def _load_shipment(pk, event):
    shipment = Shipment.objects.select_related("order", "courier").get(pk=pk)
    enqueue_shipping_event(shipment, event)


@receiver(pre_save, sender=SalesOrder, dispatch_uid="integrations.order_pre_save")
def order_pre_save(sender, instance, **kwargs):
    instance._integration_old_status = _old_value(SalesOrder, instance, "status")


@receiver(post_save, sender=SalesOrder, dispatch_uid="integrations.order_post_save")
def order_post_save(sender, instance, created, **kwargs):
    old_status = getattr(instance, "_integration_old_status", None)
    if created:
        _after_commit(_load_order, instance.pk, "created")
    elif old_status is not None and old_status != instance.status:
        _after_commit(_load_order, instance.pk, f"status_{instance.status}")


@receiver(pre_save, sender=PaymentTransaction, dispatch_uid="integrations.payment_pre_save")
def payment_pre_save(sender, instance, **kwargs):
    instance._integration_old_status = _old_value(PaymentTransaction, instance, "status")


@receiver(post_save, sender=PaymentTransaction, dispatch_uid="integrations.payment_post_save")
def payment_post_save(sender, instance, created, **kwargs):
    old_status = getattr(instance, "_integration_old_status", None)
    if created and instance.status == PaymentTransaction.Status.COMPLETED:
        _after_commit(_load_payment, instance.pk, f"created_{instance.kind}")
    elif old_status != instance.status and instance.status in {PaymentTransaction.Status.COMPLETED, PaymentTransaction.Status.FAILED, PaymentTransaction.Status.REVERSED}:
        _after_commit(_load_payment, instance.pk, f"status_{instance.status}")


@receiver(pre_save, sender=Shipment, dispatch_uid="integrations.shipment_pre_save")
def shipment_pre_save(sender, instance, **kwargs):
    instance._integration_old_status = _old_value(Shipment, instance, "status")


@receiver(post_save, sender=Shipment, dispatch_uid="integrations.shipment_post_save")
def shipment_post_save(sender, instance, created, **kwargs):
    old_status = getattr(instance, "_integration_old_status", None)
    if created:
        _after_commit(_load_shipment, instance.pk, "created")
    elif old_status is not None and old_status != instance.status:
        _after_commit(_load_shipment, instance.pk, f"status_{instance.status}")


@receiver(post_save, sender=InventoryBalance, dispatch_uid="integrations.inventory_low_stock")
def inventory_low_stock(sender, instance, **kwargs):
    if not instance.is_low_stock:
        return
    _after_commit(lambda pk: enqueue_low_stock_event(InventoryBalance.objects.get(pk=pk)), instance.pk)
