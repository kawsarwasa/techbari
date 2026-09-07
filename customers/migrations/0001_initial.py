from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion
import customers.models


def seed_customer_groups(apps, schema_editor):
    CustomerGroup = apps.get_model("customers", "CustomerGroup")
    defaults = [
        ("Retail", "RETAIL", Decimal("0.00")),
        ("Wholesale", "WHOLESALE", Decimal("0.00")),
        ("VIP", "VIP", Decimal("0.00")),
    ]
    for name, code, discount in defaults:
        CustomerGroup.objects.get_or_create(
            code=code,
            defaults={"name": name, "discount_percent": discount, "is_active": True},
        )


def unseed_customer_groups(apps, schema_editor):
    CustomerGroup = apps.get_model("customers", "CustomerGroup")
    CustomerGroup.objects.filter(code__in=["RETAIL", "WHOLESALE", "VIP"], customers__isnull=True).delete()


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="CustomerGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("code", models.CharField(max_length=40, unique=True)),
                ("discount_percent", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=5)),
                ("is_active", models.BooleanField(default=True)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("name",)},
        ),
        migrations.CreateModel(
            name="Customer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("customer_no", models.CharField(default=customers.models.make_customer_number, editable=False, max_length=40, unique=True)),
                ("name", models.CharField(max_length=180)),
                ("phone", models.CharField(max_length=40, unique=True)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("source", models.CharField(choices=[("online", "Online Store"), ("facebook", "Facebook"), ("pos", "POS / Walk-in"), ("referral", "Referral"), ("phone", "Phone Order"), ("other", "Other")], default="online", max_length=24)),
                ("address", models.TextField(blank=True)),
                ("district", models.CharField(blank=True, max_length=120)),
                ("city", models.CharField(blank=True, max_length=120)),
                ("postal_code", models.CharField(blank=True, max_length=20)),
                ("credit_limit", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18)),
                ("opening_due", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18)),
                ("notes", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("group", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="customers", to="customers.customergroup")),
            ],
            options={
                "ordering": ("name", "customer_no"),
                "indexes": [
                    models.Index(fields=["phone"], name="crm_customer_phone_idx"),
                    models.Index(fields=["is_active", "created_at"], name="crm_customer_active_idx"),
                    models.Index(fields=["source", "created_at"], name="crm_customer_source_idx"),
                ],
            },
        ),
        migrations.RunPython(seed_customer_groups, reverse_code=unseed_customer_groups),
    ]
