from decimal import Decimal

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models

import accounting.models


SYSTEM_ACCOUNTS = [
    ("1000", "Cash", "asset", "debit", "Cash on hand and cash counter balance."),
    ("1010", "Bank", "asset", "debit", "Bank account and bank-transfer clearing balance."),
    ("1020", "Card Clearing", "asset", "debit", "Card receipts awaiting or completing settlement."),
    ("1030", "bKash", "asset", "debit", "bKash merchant/wallet funds."),
    ("1040", "Nagad", "asset", "debit", "Nagad merchant/wallet funds."),
    ("1090", "Other Funds / Clearing", "asset", "debit", "Other payment methods and temporary clearing."),
    ("1100", "Accounts Receivable", "asset", "debit", "Amounts receivable from customers and sales orders."),
    ("1200", "Inventory Asset", "asset", "debit", "Cost value of inventory recognized by procurement and sales."),
    ("2000", "Accounts Payable", "liability", "credit", "Amounts owed to suppliers."),
    ("3000", "Opening Balance Equity", "equity", "credit", "Counter-account for migrated opening balances."),
    ("4000", "Product Sales Revenue", "revenue", "credit", "Product revenue from completed sales."),
    ("4010", "Shipping Revenue", "revenue", "credit", "Shipping/delivery charges billed to customers."),
    ("4090", "Sales Returns & Allowances", "revenue", "debit", "Contra-revenue for approved completed return credits."),
    ("5000", "Cost of Goods Sold", "expense", "debit", "Recognized inventory cost of completed sales."),
    ("6100", "Courier & Collection Fees", "expense", "debit", "Courier/COD deductions and collection costs."),
    ("6990", "Other Expense", "expense", "debit", "General manual expense account until the Expense module is introduced."),
]


def seed_system_accounts(apps, schema_editor):
    Account = apps.get_model("accounting", "Account")
    for code, name, account_type, normal_balance, description in SYSTEM_ACCOUNTS:
        Account.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "account_type": account_type,
                "normal_balance": normal_balance,
                "description": description,
                "is_system": True,
                "allow_manual_entries": code in {"1000", "1010", "1020", "1030", "1040", "1090", "3000", "6990"},
                "is_active": True,
            },
        )


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("catalog", "0002_catalog_crud_expansion"),
        ("customers", "0001_initial"),
        ("inventory", "0002_import_catalog_opening_stock"),
        ("payments", "0002_transaction_date_default"),
        ("purchasing", "0001_initial"),
        ("returns", "0001_initial"),
        ("sales", "0003_salesorder_return_credit_amount"),
        ("serial_tracking", "0002_serializedunit_supplier_returned_status"),
        ("shipping", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Account",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=20, unique=True)),
                ("name", models.CharField(max_length=160)),
                ("account_type", models.CharField(choices=[("asset", "Asset"), ("liability", "Liability"), ("equity", "Equity"), ("revenue", "Revenue"), ("expense", "Expense")], max_length=16)),
                ("normal_balance", models.CharField(choices=[("debit", "Debit"), ("credit", "Credit")], max_length=8)),
                ("description", models.TextField(blank=True)),
                ("is_system", models.BooleanField(default=False)),
                ("allow_manual_entries", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("code",)},
        ),
        migrations.CreateModel(
            name="AccountingPeriod",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("status", models.CharField(choices=[("open", "Open"), ("closed", "Closed")], default="open", max_length=12)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("closed_by", models.CharField(blank=True, max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("-start_date", "-id")},
        ),
        migrations.CreateModel(
            name="JournalEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("entry_no", models.CharField(default=accounting.models.make_journal_number, max_length=64, unique=True)),
                ("entry_date", models.DateField(default=django.utils.timezone.localdate)),
                ("source_type", models.CharField(choices=[("sale", "Sales Order"), ("sale_return", "Sales Return"), ("sale_payment", "Sale Payment"), ("supplier_payment", "Supplier Payment"), ("purchase_receipt", "Purchase Receipt"), ("purchase_overhead", "Purchase Overhead"), ("purchase_return", "Purchase Return"), ("courier_fee", "Courier / Collection Fee"), ("opening_balance", "Opening Balance"), ("manual", "Manual Journal"), ("reversal", "Journal Reversal")], default="manual", max_length=24)),
                ("source_key", models.CharField(blank=True, max_length=190, null=True, unique=True)),
                ("source_reference", models.CharField(blank=True, max_length=160)),
                ("description", models.TextField()),
                ("status", models.CharField(choices=[("draft", "Draft"), ("posted", "Posted"), ("reversed", "Reversed")], default="draft", max_length=12)),
                ("created_by", models.CharField(blank=True, max_length=160)),
                ("posted_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("reversal_of", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="reversal_entry", to="accounting.journalentry")),
            ],
            options={"ordering": ("-entry_date", "-id")},
        ),
        migrations.CreateModel(
            name="JournalLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("debit", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18)),
                ("credit", models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18)),
                ("memo", models.CharField(blank=True, max_length=255)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lines", to="accounting.account")),
                ("entry", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="accounting.journalentry")),
            ],
            options={"ordering": ("id",)},
        ),
        migrations.CreateModel(
            name="AccountingEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event", models.CharField(choices=[("created", "Journal Created"), ("posted", "Journal Posted"), ("reversed", "Journal Reversed"), ("period", "Period Updated")], max_length=20)),
                ("note", models.TextField(blank=True)),
                ("actor", models.CharField(blank=True, max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("journal", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="events", to="accounting.journalentry")),
            ],
            options={"ordering": ("-created_at", "-id")},
        ),
        migrations.AddIndex(model_name="account", index=models.Index(fields=["account_type", "is_active"], name="acct_type_active_idx")),
        migrations.AddIndex(model_name="accountingperiod", index=models.Index(fields=["status", "start_date", "end_date"], name="acct_period_status_idx")),
        migrations.AddIndex(model_name="journalentry", index=models.Index(fields=["status", "entry_date"], name="acct_journal_status_idx")),
        migrations.AddIndex(model_name="journalentry", index=models.Index(fields=["source_type", "entry_date"], name="acct_journal_source_idx")),
        migrations.AddIndex(model_name="journalentry", index=models.Index(fields=["source_reference"], name="acct_journal_ref_idx")),
        migrations.AddIndex(model_name="journalline", index=models.Index(fields=["account", "id"], name="acct_line_account_idx")),
        migrations.AddConstraint(model_name="journalline", constraint=models.CheckConstraint(condition=models.Q(("debit__gte", 0)), name="acct_line_debit_nonnegative")),
        migrations.AddConstraint(model_name="journalline", constraint=models.CheckConstraint(condition=models.Q(("credit__gte", 0)), name="acct_line_credit_nonnegative")),
        migrations.AddConstraint(
            model_name="journalline",
            constraint=models.CheckConstraint(
                condition=(models.Q(("credit", 0), ("debit__gt", 0)) | models.Q(("credit__gt", 0), ("debit", 0))),
                name="acct_line_one_side_positive",
            ),
        ),
        migrations.AddIndex(model_name="accountingevent", index=models.Index(fields=["journal", "created_at"], name="acct_event_journal_idx")),
        migrations.RunPython(seed_system_accounts, migrations.RunPython.noop),
    ]
