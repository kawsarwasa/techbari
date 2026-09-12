from decimal import Decimal

from django.db import migrations
from django.db.models import Sum


ZERO = Decimal("0.00")


def move_line_discounts_to_order_discount(apps, schema_editor):
    PurchaseOrder = apps.get_model("purchasing", "PurchaseOrder")
    PurchaseOrderItem = apps.get_model("purchasing", "PurchaseOrderItem")
    db_alias = schema_editor.connection.alias

    for purchase in PurchaseOrder.objects.using(db_alias).all().iterator():
        line_discount = (
            PurchaseOrderItem.objects.using(db_alias)
            .filter(purchase_id=purchase.pk)
            .aggregate(total=Sum("discount_amount"))["total"]
            or ZERO
        )
        if line_discount:
            purchase.discount_amount = (purchase.discount_amount or ZERO) + line_discount
            purchase.save(using=db_alias, update_fields=["discount_amount"])


class Migration(migrations.Migration):
    dependencies = [
        ("purchasing", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            move_line_discounts_to_order_discount,
            migrations.RunPython.noop,
        ),
        migrations.RemoveConstraint(
            model_name="purchaseorderitem",
            name="purchase_line_discount_nonnegative",
        ),
        migrations.RemoveField(
            model_name="purchaseorderitem",
            name="discount_amount",
        ),
    ]
