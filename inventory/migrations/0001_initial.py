# Generated for TechBari Inventory Phase 1 v1.1.0.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("catalog", "0002_catalog_crud_expansion"),
    ]

    operations = [
        migrations.CreateModel(
            name="Warehouse",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)),
                ("code", models.CharField(max_length=32, unique=True)),
                ("address", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("is_default", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("-is_default", "name")},
        ),
        migrations.CreateModel(
            name="InventoryBalance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("on_hand", models.PositiveIntegerField(default=0)),
                ("reserved_quantity", models.PositiveIntegerField(default=0)),
                ("low_stock_threshold", models.PositiveIntegerField(default=5)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("variant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="inventory_balances", to="catalog.productvariant")),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="balances", to="inventory.warehouse")),
            ],
            options={"ordering": ("warehouse__name", "variant__product__name", "variant__sku")},
        ),
        migrations.CreateModel(
            name="StockAdjustment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference_no", models.CharField(max_length=80, unique=True)),
                ("sku_snapshot", models.CharField(max_length=64)),
                ("product_snapshot", models.CharField(max_length=255)),
                ("system_quantity", models.PositiveIntegerField()),
                ("actual_quantity", models.PositiveIntegerField()),
                ("difference", models.IntegerField()),
                ("reason", models.CharField(max_length=255)),
                ("note", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("posted", "Posted")], default="posted", max_length=20)),
                ("actor", models.CharField(blank=True, max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="stock_adjustments", to="catalog.productvariant")),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_adjustments", to="inventory.warehouse")),
            ],
            options={"ordering": ("-created_at", "-id")},
        ),
        migrations.CreateModel(
            name="StockMovement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sku_snapshot", models.CharField(max_length=64)),
                ("product_snapshot", models.CharField(max_length=255)),
                ("movement_type", models.CharField(choices=[("opening", "Opening Stock"), ("purchase_in", "Purchase In"), ("sale_out", "Online Sale Out"), ("pos_sale_out", "POS Sale Out"), ("return_in", "Sales Return In"), ("purchase_return_out", "Purchase Return Out"), ("adjustment_in", "Adjustment In"), ("adjustment_out", "Adjustment Out"), ("transfer_in", "Transfer In"), ("transfer_out", "Transfer Out"), ("damage_out", "Damage / Loss Out"), ("reserve", "Reserve Stock"), ("release", "Release Reservation"), ("reserved_sale", "Reserved Stock Sold")], max_length=32)),
                ("quantity_delta", models.IntegerField(default=0)),
                ("reserved_delta", models.IntegerField(default=0)),
                ("quantity_after", models.PositiveIntegerField(default=0)),
                ("reserved_after", models.PositiveIntegerField(default=0)),
                ("reference_type", models.CharField(blank=True, max_length=40)),
                ("reference_no", models.CharField(blank=True, max_length=80)),
                ("note", models.TextField(blank=True)),
                ("actor", models.CharField(blank=True, max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="stock_movements", to="catalog.productvariant")),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stock_movements", to="inventory.warehouse")),
            ],
            options={"ordering": ("-created_at", "-id")},
        ),
        migrations.CreateModel(
            name="StockTransfer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("transfer_no", models.CharField(max_length=80, unique=True)),
                ("status", models.CharField(choices=[("completed", "Completed")], default="completed", max_length=20)),
                ("note", models.TextField(blank=True)),
                ("actor", models.CharField(blank=True, max_length=160)),
                ("completed_at", models.DateTimeField(auto_now_add=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("from_warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="outgoing_transfers", to="inventory.warehouse")),
                ("to_warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="incoming_transfers", to="inventory.warehouse")),
            ],
            options={"ordering": ("-created_at", "-id")},
        ),
        migrations.CreateModel(
            name="StockTransferItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sku_snapshot", models.CharField(max_length=64)),
                ("product_snapshot", models.CharField(max_length=255)),
                ("quantity", models.PositiveIntegerField()),
                ("transfer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="inventory.stocktransfer")),
                ("variant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="stock_transfer_items", to="catalog.productvariant")),
            ],
            options={"ordering": ("id",)},
        ),
        migrations.AddConstraint(
            model_name="inventorybalance",
            constraint=models.UniqueConstraint(fields=("warehouse", "variant"), name="uniq_inventory_balance_wh_variant"),
        ),
        migrations.AddConstraint(
            model_name="inventorybalance",
            constraint=models.CheckConstraint(condition=models.Q(("on_hand__gte", 0)), name="inventory_on_hand_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="inventorybalance",
            constraint=models.CheckConstraint(condition=models.Q(("reserved_quantity__gte", 0)), name="inventory_reserved_nonnegative"),
        ),
        migrations.AddConstraint(
            model_name="inventorybalance",
            constraint=models.CheckConstraint(condition=models.Q(("reserved_quantity__lte", models.F("on_hand"))), name="inventory_reserved_not_above_on_hand"),
        ),
        migrations.AddIndex(
            model_name="inventorybalance",
            index=models.Index(fields=["warehouse", "variant"], name="inv_balance_wh_variant_idx"),
        ),
        migrations.AddIndex(
            model_name="inventorybalance",
            index=models.Index(fields=["warehouse", "on_hand"], name="inv_balance_wh_stock_idx"),
        ),
        migrations.AddIndex(
            model_name="stockmovement",
            index=models.Index(fields=["warehouse", "created_at"], name="inv_move_wh_created_idx"),
        ),
        migrations.AddIndex(
            model_name="stockmovement",
            index=models.Index(fields=["variant", "created_at"], name="inv_move_var_created_idx"),
        ),
        migrations.AddIndex(
            model_name="stockmovement",
            index=models.Index(fields=["movement_type", "created_at"], name="inv_move_type_created_idx"),
        ),
        migrations.AddIndex(
            model_name="stockmovement",
            index=models.Index(fields=["reference_type", "reference_no"], name="inv_move_reference_idx"),
        ),
        migrations.AddConstraint(
            model_name="stocktransferitem",
            constraint=models.UniqueConstraint(fields=("transfer", "variant"), name="uniq_transfer_variant"),
        ),
    ]
