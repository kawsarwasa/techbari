from decimal import Decimal

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models

import expenses.models


DEFAULT_REVENUE_ACCOUNTS = [
    ("4020", "Service Income", "Service, setup, installation and other paid service income."),
    ("4030", "Commission Income", "Commission earned outside normal product sales."),
    ("4040", "Supplier Incentive", "Supplier rebate, target bonus and incentive income."),
    ("4050", "Affiliate & Referral Income", "Affiliate and referral income."),
    ("4080", "Other Operating Income", "Other non-sales operating income."),
]

EXTRA_EXPENSE_ACCOUNTS = [
    ("6310", "Packaging Expense", "Boxes, polybags, bubble wrap, tape and packing materials."),
    ("6320", "Software & Hosting", "Hosting, domain, software subscriptions and online tools."),
]

DEFAULT_CATEGORIES = [
    ("SERVICE", "income", "Service Income", "4020", 10),
    ("COMMISSION", "income", "Commission Income", "4030", 20),
    ("INCENTIVE", "income", "Supplier Incentive", "4040", 30),
    ("AFFILIATE", "income", "Affiliate & Referral Income", "4050", 40),
    ("OTHERINC", "income", "Other Income", "4080", 999),
    ("PACK", "expense", "Packaging Expense", "6310", 130),
    ("SOFTWARE", "expense", "Software & Hosting", "6320", 140),
]


def seed_income_expense_defaults(apps, schema_editor):
    Account = apps.get_model("accounting", "Account")
    ExpenseCategory = apps.get_model("expenses", "ExpenseCategory")

    for code, name, description in DEFAULT_REVENUE_ACCOUNTS:
        Account.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "account_type": "revenue",
                "normal_balance": "credit",
                "description": description,
                "is_system": True,
                "allow_manual_entries": False,
                "is_active": True,
            },
        )
    for code, name, description in EXTRA_EXPENSE_ACCOUNTS:
        Account.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "account_type": "expense",
                "normal_balance": "debit",
                "description": description,
                "is_system": True,
                "allow_manual_entries": False,
                "is_active": True,
            },
        )

    accounts = {
        row.code: row
        for row in Account.objects.filter(code__in=[row[3] for row in DEFAULT_CATEGORIES])
    }
    for code, entry_type, name, account_code, sort_order in DEFAULT_CATEGORIES:
        ExpenseCategory.objects.update_or_create(
            code=code,
            defaults={
                "entry_type": entry_type,
                "name": name,
                "account": accounts[account_code],
                "description": f"Default {name} category.",
                "is_active": True,
                "sort_order": sort_order,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounting", "0005_income_expense_accounts"),
        ("expenses", "0002_complete_expense_roadmap"),
    ]

    operations = [
        migrations.AddField(
            model_name="expensecategory",
            name="entry_type",
            field=models.CharField(
                choices=[("expense", "Expense"), ("income", "Income")],
                default="expense",
                max_length=12,
            ),
        ),
        migrations.CreateModel(
            name="CashbookEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("entry_no", models.CharField(default=expenses.models.make_cashbook_number, max_length=64, unique=True)),
                ("entry_date", models.DateField(default=django.utils.timezone.localdate)),
                ("entry_type", models.CharField(choices=[("income", "Income"), ("expense", "Expense")], max_length=12)),
                ("counterparty", models.CharField(blank=True, max_length=160)),
                ("description", models.CharField(blank=True, max_length=255)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=18)),
                ("due_date", models.DateField(blank=True, null=True)),
                ("attachment", models.FileField(blank=True, upload_to="income_expense/attachments/%Y/%m/")),
                ("is_voided", models.BooleanField(default=False)),
                ("void_reason", models.TextField(blank=True)),
                ("voided_by", models.CharField(blank=True, max_length=160)),
                ("voided_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.CharField(blank=True, max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("category", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cashbook_entries", to="expenses.expensecategory")),
            ],
            options={"ordering": ("-entry_date", "-id")},
        ),
        migrations.CreateModel(
            name="CashbookSettlement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=18)),
                ("method", models.CharField(choices=[("cash", "Cash"), ("bank", "Bank"), ("card", "Card"), ("bkash", "bKash"), ("nagad", "Nagad"), ("other", "Other")], max_length=20)),
                ("settlement_date", models.DateField(default=django.utils.timezone.localdate)),
                ("reference", models.CharField(blank=True, max_length=160)),
                ("note", models.TextField(blank=True)),
                ("actor", models.CharField(blank=True, max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("entry", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="settlements", to="expenses.cashbookentry")),
                ("payment_account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cashbook_settlements", to="accounting.account")),
            ],
            options={"ordering": ("settlement_date", "id")},
        ),
        migrations.AddIndex(model_name="cashbookentry", index=models.Index(fields=["entry_type", "entry_date"], name="cashbook_type_date_idx")),
        migrations.AddIndex(model_name="cashbookentry", index=models.Index(fields=["category", "entry_date"], name="cashbook_cat_date_idx")),
        migrations.AddIndex(model_name="cashbookentry", index=models.Index(fields=["due_date", "is_voided"], name="cashbook_due_date_idx")),
        migrations.AddIndex(model_name="cashbooksettlement", index=models.Index(fields=["entry", "settlement_date"], name="cashbook_settle_date_idx")),
        migrations.AddIndex(model_name="cashbooksettlement", index=models.Index(fields=["payment_account", "settlement_date"], name="cashbook_payacct_date_idx")),
        migrations.AddConstraint(model_name="cashbookentry", constraint=models.CheckConstraint(condition=models.Q(("amount__gt", 0)), name="cashbook_amount_positive")),
        migrations.AddConstraint(model_name="cashbooksettlement", constraint=models.CheckConstraint(condition=models.Q(("amount__gt", 0)), name="cashbook_settle_positive")),
        migrations.RunPython(seed_income_expense_defaults, migrations.RunPython.noop),
    ]
