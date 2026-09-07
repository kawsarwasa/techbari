from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import sales.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("catalog", "0002_catalog_crud_expansion"),
        ("customers", "0001_initial"),
        ("inventory", "0002_import_catalog_opening_stock"),
    ]

    operations = [
        migrations.CreateModel(
            name="SalesOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order_number", models.CharField(default=sales.models.make_order_number, max_length=50, unique=True)),
                ("channel", models.CharField(choices=[("online", "Online Store"), ("manual", "Manual Order"), ("pos", "POS")], default="online", max_length=20)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("pending", "Pending"), ("confirmed", "Confirmed"), ("processing", "Processing"), ("completed", "Completed / Sold"), ("cancelled", "Cancelled")], default="draft", max_length=20)),
                ("payment_status", models.CharField(choices=[("unpaid", "Unpaid"), ("partial", "Partial"), ("paid", "Paid"), ("refunded", "Refunded")], default="unpaid", max_length=20)),
                ("order_date", models.DateField(default=django.utils.timezone.localdate)),
                ("shipping_name", models.CharField(blank=True, max_length=180)),
                ("shipping_phone", models.CharField(blank=True, max_length=40)),
                ("shipping_email", models.EmailField(blank=True, max_length=254)),
                ("shipping_address", models.TextField(blank=True)),
                ("shipping_city", models.CharField(blank=True, max_length=120)),
                ("shipping_district", models.CharField(blank=True, max_length=120)),
                ("shipping_postal_code", models.CharField(blank=True, max_length=20)),
                ("subtotal", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18)),
                ("discount_amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18)),
                ("shipping_charge", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18)),
                ("grand_total", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18)),
                ("amount_paid", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18)),
                ("notes", models.TextField(blank=True)),
                ("created_by", models.CharField(blank=True, max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("customer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="sales_orders", to="customers.customer")),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sales_orders", to="inventory.warehouse")),
            ],
            options={
                "ordering": ("-order_date", "-id"),
                "indexes": [
                    models.Index(fields=["status", "order_date"], name="sales_order_status_date_idx"),
                    models.Index(fields=["payment_status", "order_date"], name="sales_order_pay_date_idx"),
                    models.Index(fields=["customer", "order_date"], name="sales_order_customer_idx"),
                    models.Index(fields=["warehouse", "status"], name="sales_order_wh_status_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="SalesOrderItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("product_snapshot", models.CharField(max_length=255)),
                ("variant_snapshot", models.CharField(max_length=120)),
                ("sku_snapshot", models.CharField(max_length=64)),
                ("quantity", models.PositiveIntegerField()),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=18)),
                ("discount_amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18)),
                ("reserved_quantity", models.PositiveIntegerField(default=0)),
                ("issued_quantity", models.PositiveIntegerField(default=0)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="sales.salesorder")),
                ("variant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sales_order_items", to="catalog.productvariant")),
            ],
            options={
                "ordering": ("id",),
                "constraints": [
                    models.UniqueConstraint(fields=("order", "variant"), name="uniq_sales_order_variant"),
                    models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="sales_item_quantity_positive"),
                    models.CheckConstraint(condition=models.Q(("reserved_quantity__gte", 0)), name="sales_item_reserved_nonnegative"),
                    models.CheckConstraint(condition=models.Q(("issued_quantity__gte", 0)), name="sales_item_issued_nonnegative"),
                ],
            },
        ),
        migrations.CreateModel(
            name="SalesOrderHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event", models.CharField(choices=[("created", "Created"), ("updated", "Updated"), ("status", "Status Changed"), ("payment", "Payment Updated"), ("stock", "Stock Updated")], max_length=20)),
                ("previous_status", models.CharField(blank=True, max_length=20)),
                ("new_status", models.CharField(blank=True, max_length=20)),
                ("note", models.TextField(blank=True)),
                ("actor", models.CharField(blank=True, max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="history", to="sales.salesorder")),
            ],
            options={
                "ordering": ("-created_at", "-id"),
                "indexes": [models.Index(fields=["order", "created_at"], name="sales_history_order_idx")],
            },
        ),
    ]
