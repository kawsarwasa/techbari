from decimal import Decimal
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models
import returns.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("inventory", "0002_import_catalog_opening_stock"),
        ("payments", "0002_transaction_date_default"),
        ("sales", "0003_salesorder_return_credit_amount"),
        ("serial_tracking", "0002_serializedunit_supplier_returned_status"),
    ]

    operations = [
        migrations.CreateModel(
            name="SalesReturn",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("return_no", models.CharField(default=returns.models.make_return_number, max_length=64, unique=True)),
                ("source", models.CharField(choices=[("customer", "Customer Return"), ("courier_return", "Courier Return"), ("pos", "POS / Counter Return"), ("manual", "Manual / Other")], default="customer", max_length=24)),
                ("status", models.CharField(choices=[("requested", "Requested"), ("approved", "Approved"), ("received", "Received / Inspecting"), ("completed", "Completed"), ("rejected", "Rejected"), ("cancelled", "Cancelled")], default="requested", max_length=20)),
                ("resolution", models.CharField(choices=[("refund", "Refund / Credit"), ("no_refund", "No Refund")], default="refund", max_length=20)),
                ("reason_category", models.CharField(choices=[("defective", "Defective Product"), ("damaged", "Damaged Product"), ("wrong_item", "Wrong Item"), ("not_as_described", "Not as Described"), ("changed_mind", "Changed Mind"), ("courier_return", "Courier Returned Parcel"), ("other", "Other")], default="other", max_length=32)),
                ("source_reference", models.CharField(blank=True, max_length=160)),
                ("refund_reference", models.CharField(blank=True, max_length=160)),
                ("requested_date", models.DateField(default=django.utils.timezone.localdate)),
                ("received_date", models.DateField(blank=True, null=True)),
                ("completed_date", models.DateField(blank=True, null=True)),
                ("customer_note", models.TextField(blank=True)),
                ("internal_note", models.TextField(blank=True)),
                ("actor", models.CharField(blank=True, max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sales_returns", to="sales.salesorder")),
                ("warehouse", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sales_returns", to="inventory.warehouse")),
            ],
            options={"ordering": ("-requested_date", "-id")},
        ),
        migrations.CreateModel(
            name="SalesReturnItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("product_snapshot", models.CharField(max_length=255)),
                ("sku_snapshot", models.CharField(max_length=64)),
                ("quantity", models.PositiveIntegerField()),
                ("condition", models.CharField(choices=[("sealed", "Sealed / Unopened"), ("good", "Opened but Good"), ("used", "Used"), ("defective", "Defective"), ("damaged", "Damaged")], default="good", max_length=20)),
                ("disposition", models.CharField(choices=[("restock", "Return to Sellable Stock"), ("damaged", "Damaged / Quarantine"), ("warranty", "Warranty / Service"), ("scrap", "Scrap"), ("no_stock", "Do Not Add to Stock")], default="restock", max_length=20)),
                ("refund_amount", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18)),
                ("restocked_quantity", models.PositiveIntegerField(default=0)),
                ("note", models.TextField(blank=True)),
                ("order_item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="return_items", to="sales.salesorderitem")),
                ("sales_return", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="returns.salesreturn")),
                ("serialized_unit", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="sales_return_items", to="serial_tracking.serializedunit")),
                ("variant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sales_return_items", to="catalog.productvariant")),
            ],
            options={"ordering": ("id",)},
        ),
        migrations.CreateModel(
            name="SalesReturnEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event", models.CharField(choices=[("created", "Created"), ("status", "Status Changed"), ("inventory", "Inventory Processed"), ("credit", "Return Credit Applied"), ("refund", "Cash Refund Posted"), ("note", "Note")], max_length=20)),
                ("previous_status", models.CharField(blank=True, max_length=20)),
                ("new_status", models.CharField(blank=True, max_length=20)),
                ("note", models.TextField(blank=True)),
                ("actor", models.CharField(blank=True, max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("sales_return", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="returns.salesreturn")),
            ],
            options={"ordering": ("-created_at", "-id")},
        ),
        migrations.CreateModel(
            name="SalesReturnRefund",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=18)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("refund_transaction", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="sales_return_refund", to="payments.paymenttransaction")),
                ("sales_return", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="refunds", to="returns.salesreturn")),
                ("source_payment", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="return_refund_sources", to="payments.paymenttransaction")),
            ],
            options={"ordering": ("id",)},
        ),
        migrations.AddIndex(model_name="salesreturn", index=models.Index(fields=["status", "requested_date"], name="ret_status_date_idx")),
        migrations.AddIndex(model_name="salesreturn", index=models.Index(fields=["order", "requested_date"], name="ret_order_date_idx")),
        migrations.AddIndex(model_name="salesreturn", index=models.Index(fields=["source", "requested_date"], name="ret_source_date_idx")),
        migrations.AddIndex(model_name="salesreturnitem", index=models.Index(fields=["order_item"], name="ret_item_order_item_idx")),
        migrations.AddIndex(model_name="salesreturnitem", index=models.Index(fields=["variant"], name="ret_item_variant_idx")),
        migrations.AddConstraint(model_name="salesreturnitem", constraint=models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="ret_item_quantity_positive")),
        migrations.AddConstraint(model_name="salesreturnitem", constraint=models.CheckConstraint(condition=models.Q(("refund_amount__gte", 0)), name="ret_item_refund_nonnegative")),
        migrations.AddConstraint(model_name="salesreturnitem", constraint=models.CheckConstraint(condition=models.Q(("restocked_quantity__gte", 0)), name="ret_item_restock_nonnegative")),
        migrations.AddIndex(model_name="salesreturnevent", index=models.Index(fields=["sales_return", "created_at"], name="ret_event_return_idx")),
        migrations.AddConstraint(model_name="salesreturnrefund", constraint=models.CheckConstraint(condition=models.Q(("amount__gt", 0)), name="ret_refund_amount_positive")),
    ]
