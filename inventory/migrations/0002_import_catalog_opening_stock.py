from django.db import migrations


def import_catalog_opening_stock(apps, schema_editor):
    Warehouse = apps.get_model("inventory", "Warehouse")
    InventoryBalance = apps.get_model("inventory", "InventoryBalance")
    StockMovement = apps.get_model("inventory", "StockMovement")
    ProductVariant = apps.get_model("catalog", "ProductVariant")

    warehouse, _ = Warehouse.objects.get_or_create(
        code="MAIN",
        defaults={
            "name": "Main Warehouse",
            "address": "Primary stock location",
            "is_active": True,
            "is_default": True,
        },
    )
    if not warehouse.is_active or not warehouse.is_default:
        Warehouse.objects.filter(is_default=True).exclude(pk=warehouse.pk).update(is_default=False)
        warehouse.is_active = True
        warehouse.is_default = True
        warehouse.save(update_fields=["is_active", "is_default", "updated_at"])

    for variant in ProductVariant.objects.select_related("product").all().iterator():
        opening_quantity = int(variant.stock_quantity or 0)
        balance, created = InventoryBalance.objects.get_or_create(
            warehouse=warehouse,
            variant=variant,
            defaults={
                "on_hand": opening_quantity,
                "reserved_quantity": 0,
                "low_stock_threshold": variant.low_stock_alert,
            },
        )
        if created and opening_quantity:
            StockMovement.objects.create(
                warehouse=warehouse,
                variant=variant,
                sku_snapshot=variant.sku,
                product_snapshot=variant.product.name,
                movement_type="opening",
                quantity_delta=opening_quantity,
                reserved_delta=0,
                quantity_after=opening_quantity,
                reserved_after=0,
                reference_type="migration",
                reference_no="catalog-v1.0.10",
                note="Opening stock imported from ProductVariant.stock_quantity during Inventory Phase 1 migration.",
                actor="System Migration",
            )


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(import_catalog_opening_stock, migrations.RunPython.noop),
    ]
