import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from inventory.models import InventoryBalance

from .services import enqueue_low_stock_event

logger = logging.getLogger(__name__)


@receiver(post_save, sender=InventoryBalance, dispatch_uid="integrations.inventory_low_stock")
def inventory_low_stock(sender, instance, **kwargs):
    try:
        enqueue_low_stock_event(instance)
    except Exception:
        # Notifications must never make stock posting fail. Dedicated integration
        # tests cover the queue path; runtime failures remain visible in logs.
        logger.exception("Could not enqueue low-stock notification for balance %s", instance.pk)
