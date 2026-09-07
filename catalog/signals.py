from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import Brand, Category, ProductImage


def _schedule_delete(field_file):
    if not field_file or not getattr(field_file, "name", ""):
        return
    storage = field_file.storage
    name = field_file.name
    transaction.on_commit(lambda: storage.delete(name))


def _remember_replaced_file(instance, model, field_name):
    if not instance.pk:
        return
    previous = model.objects.filter(pk=instance.pk).only(field_name).first()
    if not previous:
        return
    old_file = getattr(previous, field_name)
    new_file = getattr(instance, field_name)
    old_name = getattr(old_file, "name", "")
    new_name = getattr(new_file, "name", "")
    if old_name and old_name != new_name:
        setattr(instance, f"_replaced_{field_name}", old_file)


def _delete_remembered_file(instance, field_name):
    previous = getattr(instance, f"_replaced_{field_name}", None)
    if previous:
        _schedule_delete(previous)
        delattr(instance, f"_replaced_{field_name}")


@receiver(pre_save, sender=ProductImage)
def remember_product_image_replacement(sender, instance, **kwargs):
    _remember_replaced_file(instance, ProductImage, "image")


@receiver(post_save, sender=ProductImage)
def cleanup_replaced_product_image(sender, instance, **kwargs):
    _delete_remembered_file(instance, "image")


@receiver(post_delete, sender=ProductImage)
def cleanup_deleted_product_image(sender, instance, **kwargs):
    _schedule_delete(instance.image)


@receiver(pre_save, sender=Category)
def remember_category_image_replacement(sender, instance, **kwargs):
    _remember_replaced_file(instance, Category, "image")


@receiver(post_save, sender=Category)
def cleanup_replaced_category_image(sender, instance, **kwargs):
    _delete_remembered_file(instance, "image")


@receiver(post_delete, sender=Category)
def cleanup_deleted_category_image(sender, instance, **kwargs):
    _schedule_delete(instance.image)


@receiver(pre_save, sender=Brand)
def remember_brand_logo_replacement(sender, instance, **kwargs):
    _remember_replaced_file(instance, Brand, "logo")


@receiver(post_save, sender=Brand)
def cleanup_replaced_brand_logo(sender, instance, **kwargs):
    _delete_remembered_file(instance, "logo")


@receiver(post_delete, sender=Brand)
def cleanup_deleted_brand_logo(sender, instance, **kwargs):
    _schedule_delete(instance.logo)
