from django.db.models.signals import post_save
from django.dispatch import receiver

from catalog.models import ProductVariant
from .compat import reconcile_catalog_stock


@receiver(post_save, sender=ProductVariant)
def reconcile_variant_inventory(sender, instance, raw=False, **kwargs):
    if raw:
        return
    reconcile_catalog_stock(instance)
