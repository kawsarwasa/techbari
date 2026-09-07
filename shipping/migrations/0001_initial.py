from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import shipping.models


def seed_couriers(apps, schema_editor):
    CourierProvider = apps.get_model("shipping", "CourierProvider")
    rows = [
        ("MANUAL", "Manual / Own Delivery"),
        ("PATHAO", "Pathao Courier"),
        ("STEADFAST", "Steadfast Courier"),
        ("REDX", "RedX Courier"),
    ]
    for code, name in rows:
        CourierProvider.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "supports_cod": True,
                "default_courier_fee": Decimal("0.00"),
                "is_active": True,
                "api_enabled": False,
                "is_test_mode": True,
                "notes": "Seeded in v1.9.0. Configure real account/API details before enabling integration.",
            },
        )


def reverse_seed(apps, schema_editor):
    CourierProvider = apps.get_model("shipping", "CourierProvider")
    CourierProvider.objects.filter(code__in=["MANUAL", "PATHAO", "STEADFAST", "REDX"], shipments__isnull=True).delete()


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("payments", "0002_transaction_date_default"),
        ("sales", "0002_pos_tender_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="CourierProvider",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=40, unique=True)),
                ("name", models.CharField(max_length=160)),
                ("contact_person", models.CharField(blank=True, max_length=160)),
                ("phone", models.CharField(blank=True, max_length=40)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("website", models.URLField(blank=True)),
                ("tracking_url_template", models.CharField(blank=True, help_text="Optional URL containing {tracking_id}.", max_length=500)),
                ("supports_cod", models.BooleanField(default=True)),
                ("default_courier_fee", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("is_active", models.BooleanField(default=True)),
                ("api_enabled", models.BooleanField(default=False)),
                ("is_test_mode", models.BooleanField(default=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("name", "code")},
        ),
        migrations.CreateModel(
            name="Shipment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("shipment_no", models.CharField(default=shipping.models.make_shipment_number, max_length=64, unique=True)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("ready", "Ready for Handover"), ("handed_over", "Handed Over"), ("in_transit", "In Transit"), ("out_for_delivery", "Out for Delivery"), ("delivered", "Delivered"), ("failed", "Delivery Failed"), ("returning", "Returning to Merchant"), ("returned", "Returned to Merchant"), ("cancelled", "Cancelled")], default="draft", max_length=24)),
                ("tracking_id", models.CharField(blank=True, max_length=160)),
                ("courier_reference", models.CharField(blank=True, max_length=160)),
                ("shipment_date", models.DateField(default=django.utils.timezone.localdate)),
                ("expected_delivery_date", models.DateField(blank=True, null=True)),
                ("parcel_count", models.PositiveIntegerField(default=1)),
                ("weight_kg", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=8)),
                ("courier_fee", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=14)),
                ("cod_expected", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18)),
                ("cod_collected", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18)),
                ("cod_settled", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18)),
                ("cod_status", models.CharField(choices=[("not_applicable", "Not Applicable"), ("pending", "Pending Collection"), ("collected", "Collected"), ("partially_settled", "Partially Settled"), ("settled", "Settled"), ("disputed", "Disputed / Short")], default="not_applicable", max_length=24)),
                ("last_location", models.CharField(blank=True, max_length=180)),
                ("failure_reason", models.CharField(blank=True, max_length=255)),
                ("handed_over_at", models.DateTimeField(blank=True, null=True)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                ("returned_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.TextField(blank=True)),
                ("actor", models.CharField(blank=True, max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("courier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="shipments", to="shipping.courierprovider")),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="shipment", to="sales.salesorder")),
            ],
            options={"ordering": ("-shipment_date", "-id")},
        ),
        migrations.CreateModel(
            name="ShipmentEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event", models.CharField(choices=[("created", "Created"), ("status", "Status Changed"), ("tracking", "Tracking Updated"), ("delivery_attempt", "Delivery Attempt"), ("cod_collection", "COD Collection"), ("cod_settlement", "COD Settlement"), ("note", "Note")], max_length=24)),
                ("previous_status", models.CharField(blank=True, max_length=24)),
                ("new_status", models.CharField(blank=True, max_length=24)),
                ("location", models.CharField(blank=True, max_length=180)),
                ("note", models.TextField(blank=True)),
                ("actor", models.CharField(blank=True, max_length=160)),
                ("occurred_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("shipment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="shipping.shipment")),
            ],
            options={"ordering": ("-occurred_at", "-id")},
        ),
        migrations.CreateModel(
            name="CODSettlement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("settlement_no", models.CharField(default=shipping.models.make_settlement_number, max_length=64, unique=True)),
                ("settlement_date", models.DateField(default=django.utils.timezone.localdate)),
                ("payment_method", models.CharField(choices=[("cash", "Cash"), ("bank", "Bank Transfer"), ("card", "Card"), ("bkash", "bKash"), ("nagad", "Nagad"), ("other", "Other")], max_length=20)),
                ("reference", models.CharField(blank=True, max_length=160)),
                ("gross_amount", models.DecimalField(decimal_places=2, max_digits=18)),
                ("courier_deduction", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18)),
                ("net_received", models.DecimalField(decimal_places=2, max_digits=18)),
                ("note", models.TextField(blank=True)),
                ("actor", models.CharField(blank=True, max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("courier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cod_settlements", to="shipping.courierprovider")),
            ],
            options={"ordering": ("-settlement_date", "-id")},
        ),
        migrations.CreateModel(
            name="CODSettlementItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=18)),
                ("payment_transaction", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="cod_settlement_item", to="payments.paymenttransaction")),
                ("settlement", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="shipping.codsettlement")),
                ("shipment", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="settlement_items", to="shipping.shipment")),
            ],
            options={"ordering": ("id",)},
        ),
        migrations.AddIndex(model_name="courierprovider", index=models.Index(fields=["is_active", "name"], name="ship_courier_active_idx")),
        migrations.AddConstraint(model_name="courierprovider", constraint=models.CheckConstraint(condition=models.Q(("default_courier_fee__gte", 0)), name="ship_courier_fee_nonnegative")),
        migrations.AddIndex(model_name="shipment", index=models.Index(fields=["status", "shipment_date"], name="ship_status_date_idx")),
        migrations.AddIndex(model_name="shipment", index=models.Index(fields=["courier", "status"], name="ship_courier_status_idx")),
        migrations.AddIndex(model_name="shipment", index=models.Index(fields=["tracking_id"], name="ship_tracking_idx")),
        migrations.AddIndex(model_name="shipment", index=models.Index(fields=["cod_status", "shipment_date"], name="ship_cod_status_idx")),
        migrations.AddConstraint(model_name="shipment", constraint=models.CheckConstraint(condition=models.Q(("parcel_count__gt", 0)), name="ship_parcel_count_positive")),
        migrations.AddConstraint(model_name="shipment", constraint=models.CheckConstraint(condition=models.Q(("weight_kg__gte", 0)), name="ship_weight_nonnegative")),
        migrations.AddConstraint(model_name="shipment", constraint=models.CheckConstraint(condition=models.Q(("courier_fee__gte", 0)), name="ship_fee_nonnegative")),
        migrations.AddConstraint(model_name="shipment", constraint=models.CheckConstraint(condition=models.Q(("cod_expected__gte", 0)), name="ship_cod_expected_nonnegative")),
        migrations.AddConstraint(model_name="shipment", constraint=models.CheckConstraint(condition=models.Q(("cod_collected__gte", 0)), name="ship_cod_collected_nonnegative")),
        migrations.AddConstraint(model_name="shipment", constraint=models.CheckConstraint(condition=models.Q(("cod_settled__gte", 0)), name="ship_cod_settled_nonnegative")),
        migrations.AddIndex(model_name="shipmentevent", index=models.Index(fields=["shipment", "occurred_at"], name="ship_event_time_idx")),
        migrations.AddIndex(model_name="codsettlement", index=models.Index(fields=["courier", "settlement_date"], name="ship_settle_courier_idx")),
        migrations.AddIndex(model_name="codsettlement", index=models.Index(fields=["settlement_date"], name="ship_settle_date_idx")),
        migrations.AddConstraint(model_name="codsettlement", constraint=models.CheckConstraint(condition=models.Q(("gross_amount__gt", 0)), name="ship_settle_gross_positive")),
        migrations.AddConstraint(model_name="codsettlement", constraint=models.CheckConstraint(condition=models.Q(("courier_deduction__gte", 0)), name="ship_settle_deduct_nonnegative")),
        migrations.AddConstraint(model_name="codsettlement", constraint=models.CheckConstraint(condition=models.Q(("net_received__gte", 0)), name="ship_settle_net_nonnegative")),
        migrations.AddConstraint(model_name="codsettlementitem", constraint=models.UniqueConstraint(fields=("settlement", "shipment"), name="uniq_ship_settlement_item")),
        migrations.AddConstraint(model_name="codsettlementitem", constraint=models.CheckConstraint(condition=models.Q(("amount__gt", 0)), name="ship_settlement_item_positive")),
        migrations.RunPython(seed_couriers, reverse_seed),
    ]
