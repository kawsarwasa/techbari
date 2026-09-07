from django.db import migrations, models
import django.db.models.deletion
import payments.models


def seed_payment_methods_and_import(apps, schema_editor):
    PaymentMethodConfig = apps.get_model("payments", "PaymentMethodConfig")
    PaymentTransaction = apps.get_model("payments", "PaymentTransaction")
    PaymentEvent = apps.get_model("payments", "PaymentEvent")
    SalesOrder = apps.get_model("sales", "SalesOrder")
    PurchasePayment = apps.get_model("purchasing", "PurchasePayment")

    configs = [
        ("cash", "Cash", "cash", True, True, False),
        ("bank", "Bank Transfer", "bank", True, True, False),
        ("card", "Card", "manual_card", True, True, False),
        ("bkash", "bKash", "manual_bkash", True, True, False),
        ("nagad", "Nagad", "manual_nagad", True, True, False),
        ("other", "Other", "manual", True, True, False),
    ]
    for method, display_name, provider_code, allow_dashboard, allow_pos, allow_storefront in configs:
        PaymentMethodConfig.objects.update_or_create(
            method=method,
            defaults={
                "display_name": display_name,
                "provider_code": provider_code,
                "is_active": True,
                "allow_dashboard": allow_dashboard,
                "allow_pos": allow_pos,
                "allow_storefront": allow_storefront,
                "is_test_mode": True,
            },
        )

    for order in SalesOrder.objects.filter(amount_paid__gt=0).iterator():
        method = (getattr(order, "payment_method", "") or "other").lower()
        if method not in {"cash", "bank", "card", "bkash", "nagad", "other"}:
            method = "other"
        payment = PaymentTransaction.objects.create(
            transaction_no=f"IMP-SALE-{order.pk}",
            sales_order_id=order.pk,
            kind="sale_payment",
            direction="in",
            method=method,
            status="completed",
            amount=order.amount_paid,
            provider_reference=getattr(order, "payment_reference", "") or "",
            transaction_date=order.order_date,
            note="Imported from pre-v1.8 SalesOrder paid amount.",
            created_by="v1.8 migration",
        )
        PaymentEvent.objects.create(
            transaction_id=payment.pk,
            event="created",
            new_status="completed",
            note="Opening payment imported during v1.8 migration.",
            actor="v1.8 migration",
        )

    for purchase_payment in PurchasePayment.objects.all().iterator():
        method = (purchase_payment.method or "other").lower()
        if method not in {"cash", "bank", "card", "bkash", "nagad", "other"}:
            method = "other"
        payment = PaymentTransaction.objects.create(
            transaction_no=f"IMP-PUR-{purchase_payment.pk}",
            purchase_payment_id=purchase_payment.pk,
            kind="supplier_payment",
            direction="out",
            method=method,
            status="completed",
            amount=purchase_payment.amount,
            provider_reference=purchase_payment.reference or "",
            transaction_date=purchase_payment.payment_date,
            note=purchase_payment.note or "Imported supplier payment from pre-v1.8 purchasing ledger.",
            created_by=purchase_payment.actor or "v1.8 migration",
        )
        PaymentEvent.objects.create(
            transaction_id=payment.pk,
            event="created",
            new_status="completed",
            note="Opening supplier payment imported during v1.8 migration.",
            actor="v1.8 migration",
        )


def reverse_import(apps, schema_editor):
    PaymentTransaction = apps.get_model("payments", "PaymentTransaction")
    PaymentTransaction.objects.filter(transaction_no__startswith="IMP-").delete()


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("sales", "0002_pos_tender_fields"),
        ("purchasing", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentMethodConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("method", models.CharField(choices=[("cash", "Cash"), ("bank", "Bank Transfer"), ("card", "Card"), ("bkash", "bKash"), ("nagad", "Nagad"), ("other", "Other")], max_length=20, unique=True)),
                ("display_name", models.CharField(max_length=80)),
                ("provider_code", models.CharField(blank=True, max_length=80)),
                ("merchant_label", models.CharField(blank=True, max_length=120)),
                ("is_active", models.BooleanField(default=True)),
                ("allow_dashboard", models.BooleanField(default=True)),
                ("allow_pos", models.BooleanField(default=True)),
                ("allow_storefront", models.BooleanField(default=False)),
                ("is_test_mode", models.BooleanField(default=True)),
                ("instructions", models.TextField(blank=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("id",)},
        ),
        migrations.CreateModel(
            name="PaymentTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("transaction_no", models.CharField(default=payments.models.make_payment_number, max_length=64, unique=True)),
                ("kind", models.CharField(choices=[("sale_payment", "Sale Payment"), ("supplier_payment", "Supplier Payment"), ("refund", "Customer Refund"), ("reversal", "Payment Reversal")], max_length=24)),
                ("direction", models.CharField(choices=[("in", "Money In"), ("out", "Money Out")], max_length=8)),
                ("method", models.CharField(choices=[("cash", "Cash"), ("bank", "Bank Transfer"), ("card", "Card"), ("bkash", "bKash"), ("nagad", "Nagad"), ("other", "Other")], max_length=20)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("completed", "Completed"), ("failed", "Failed"), ("reversed", "Reversed")], default="completed", max_length=20)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=18)),
                ("provider_reference", models.CharField(blank=True, max_length=160)),
                ("external_id", models.CharField(blank=True, max_length=160)),
                ("transaction_date", models.DateField()),
                ("note", models.TextField(blank=True)),
                ("reconciliation_status", models.CharField(choices=[("unreconciled", "Unreconciled"), ("reconciled", "Reconciled"), ("disputed", "Disputed")], default="unreconciled", max_length=20)),
                ("reconciled_at", models.DateTimeField(blank=True, null=True)),
                ("reconciled_by", models.CharField(blank=True, max_length=160)),
                ("created_by", models.CharField(blank=True, max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("parent_transaction", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="child_transactions", to="payments.paymenttransaction")),
                ("purchase_payment", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="ledger_transaction", to="purchasing.purchasepayment")),
                ("sales_order", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="payment_transactions", to="sales.salesorder")),
            ],
            options={"ordering": ("-transaction_date", "-id")},
        ),
        migrations.CreateModel(
            name="PaymentEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event", models.CharField(choices=[("created", "Created"), ("status", "Status Changed"), ("refund", "Refund Created"), ("reversal", "Reversal Created"), ("reconciliation", "Reconciliation Updated")], max_length=24)),
                ("previous_status", models.CharField(blank=True, max_length=20)),
                ("new_status", models.CharField(blank=True, max_length=20)),
                ("note", models.TextField(blank=True)),
                ("actor", models.CharField(blank=True, max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("transaction", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="payments.paymenttransaction")),
            ],
            options={"ordering": ("-created_at", "-id")},
        ),
        migrations.AddIndex(model_name="paymenttransaction", index=models.Index(fields=["status", "transaction_date"], name="payment_status_date_idx")),
        migrations.AddIndex(model_name="paymenttransaction", index=models.Index(fields=["method", "transaction_date"], name="payment_method_date_idx")),
        migrations.AddIndex(model_name="paymenttransaction", index=models.Index(fields=["reconciliation_status", "transaction_date"], name="payment_recon_date_idx")),
        migrations.AddIndex(model_name="paymenttransaction", index=models.Index(fields=["sales_order", "transaction_date"], name="payment_sales_date_idx")),
        migrations.AddIndex(model_name="paymentevent", index=models.Index(fields=["transaction", "created_at"], name="payment_event_txn_idx")),
        migrations.AddConstraint(model_name="paymenttransaction", constraint=models.CheckConstraint(condition=models.Q(("amount__gt", 0)), name="payment_amount_positive")),
        migrations.RunPython(seed_payment_methods_and_import, reverse_import),
    ]
