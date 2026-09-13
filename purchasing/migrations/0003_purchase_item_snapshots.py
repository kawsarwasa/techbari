from django.db import migrations, models


def backfill_purchase_item_snapshots(apps, schema_editor):
    PurchaseOrderItem = apps.get_model("purchasing", "PurchaseOrderItem")
    items = PurchaseOrderItem.objects.select_related("variant", "variant__product").all()
    pending = []
    for item in items.iterator():
        variant = item.variant
        item.product_snapshot = variant.product.name
        item.variant_snapshot = variant.name
        item.sku_snapshot = variant.sku
        pending.append(item)
        if len(pending) >= 500:
            PurchaseOrderItem.objects.bulk_update(
                pending,
                ["product_snapshot", "variant_snapshot", "sku_snapshot"],
            )
            pending = []
    if pending:
        PurchaseOrderItem.objects.bulk_update(
            pending,
            ["product_snapshot", "variant_snapshot", "sku_snapshot"],
        )


class Migration(migrations.Migration):

    dependencies = [
        ("purchasing", "0002_remove_purchase_item_discount"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchaseorderitem",
            name="product_snapshot",
            field=models.CharField(blank=True, default="", max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="purchaseorderitem",
            name="variant_snapshot",
            field=models.CharField(blank=True, default="", max_length=120),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="purchaseorderitem",
            name="sku_snapshot",
            field=models.CharField(blank=True, default="", max_length=64),
            preserve_default=False,
        ),
        migrations.RunPython(backfill_purchase_item_snapshots, migrations.RunPython.noop),
    ]
