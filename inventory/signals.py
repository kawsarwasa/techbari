from django.db.models.signals import post_save
from django.dispatch import receiver

from catalog.models import ProductVariant
from .services import bootstrap_variant_stock


@receiver(post_save, sender=ProductVariant)
def create_opening_inventory_for_new_variant(sender, instance, created, raw=False, **kwargs):
    if raw or not created:
        return
    bootstrap_variant_stock(instance)
