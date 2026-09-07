from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("catalog", "0002_catalog_crud_expansion"),
        ("inventory", "0002_import_catalog_opening_stock"),
    ]

    operations = [
        migrations.CreateModel(
            name="SerializedUnit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("serial_number", models.CharField(blank=True, max_length=120, null=True, unique=True)),
                ("imei1", models.CharField(blank=True, max_length=15, null=True, unique=True)),
                ("imei2", models.CharField(blank=True, max_length=15, null=True, unique=True)),
                ("status", models.CharField(choices=[("available", "Available"), ("reserved", "Reserved"), ("sold", "Sold"), ("returned", "Returned"), ("damaged", "Damaged"), ("warranty_service", "Warranty Service"), ("scrapped", "Scrapped")], default="available", max_length=32)),
                ("supplier_reference", models.CharField(blank=True, max_length=160)),
                ("purchase_reference", models.CharField(blank=True, max_length=160)),
                ("purchase_date", models.DateField(blank=True, null=True)),
                ("purchase_cost", models.DecimalField(blank=True, decimal_places=2, max_digits=18, null=True)),
                ("received_date", models.DateField(blank=True, null=True)),
                ("sales_reference", models.CharField(blank=True, max_length=160)),
                ("customer_reference", models.CharField(blank=True, max_length=160)),
                ("sold_at", models.DateField(blank=True, null=True)),
                ("warranty_type", models.CharField(blank=True, max_length=120)),
                ("warranty_start_date", models.DateField(blank=True, null=True)),
                ("warranty_end_date", models.DateField(blank=True, null=True)),
                ("supplier_warranty_reference", models.CharField(blank=True, max_length=160)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("variant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="serialized_units", to="catalog.productvariant")),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="serialized_units", to="inventory.warehouse")),
            ],
            options={"ordering": ("-created_at", "-id")},
        ),
        migrations.CreateModel(
            name="SerializedUnitEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(choices=[("registered", "Registered"), ("identifiers_updated", "Identifiers Updated"), ("transferred", "Warehouse Transferred"), ("status_changed", "Status Changed"), ("warranty_opened", "Warranty Claim Opened"), ("warranty_updated", "Warranty Claim Updated"), ("warranty_replaced", "Warranty Replacement")], max_length=32)),
                ("from_status", models.CharField(blank=True, max_length=32)),
                ("to_status", models.CharField(blank=True, max_length=32)),
                ("reference_no", models.CharField(blank=True, max_length=160)),
                ("note", models.TextField(blank=True)),
                ("actor", models.CharField(blank=True, max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("from_warehouse", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="serialized_events_from", to="inventory.warehouse")),
                ("to_warehouse", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="serialized_events_to", to="inventory.warehouse")),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="serial_tracking.serializedunit")),
            ],
            options={"ordering": ("-created_at", "-id")},
        ),
        migrations.CreateModel(
            name="WarrantyClaim",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("claim_no", models.CharField(max_length=80, unique=True)),
                ("customer_name", models.CharField(blank=True, max_length=160)),
                ("customer_phone", models.CharField(blank=True, max_length=40)),
                ("order_reference", models.CharField(blank=True, max_length=160)),
                ("claim_date", models.DateField()),
                ("issue", models.TextField()),
                ("status", models.CharField(choices=[("open", "Open"), ("in_service", "In Service"), ("resolved", "Resolved"), ("replaced", "Replaced"), ("rejected", "Rejected")], default="open", max_length=20)),
                ("resolution", models.TextField(blank=True)),
                ("service_reference", models.CharField(blank=True, max_length=160)),
                ("resolved_at", models.DateField(blank=True, null=True)),
                ("unit_status_before_claim", models.CharField(blank=True, max_length=32)),
                ("notes", models.TextField(blank=True)),
                ("actor", models.CharField(blank=True, max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("replacement_unit", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="replacement_for_claims", to="serial_tracking.serializedunit")),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="warranty_claims", to="serial_tracking.serializedunit")),
            ],
            options={"ordering": ("-claim_date", "-id")},
        ),
        migrations.AddIndex(model_name="serializedunit", index=models.Index(fields=["variant", "status"], name="ser_unit_variant_status_idx")),
        migrations.AddIndex(model_name="serializedunit", index=models.Index(fields=["warehouse", "status"], name="ser_unit_wh_status_idx")),
        migrations.AddIndex(model_name="serializedunit", index=models.Index(fields=["status", "created_at"], name="ser_unit_status_created_idx")),
        migrations.AddIndex(model_name="serializedunitevent", index=models.Index(fields=["unit", "created_at"], name="ser_event_unit_created_idx")),
        migrations.AddIndex(model_name="serializedunitevent", index=models.Index(fields=["event_type", "created_at"], name="ser_event_type_created_idx")),
        migrations.AddIndex(model_name="warrantyclaim", index=models.Index(fields=["status", "claim_date"], name="ser_claim_status_date_idx")),
        migrations.AddIndex(model_name="warrantyclaim", index=models.Index(fields=["unit", "claim_date"], name="ser_claim_unit_date_idx")),
    ]
