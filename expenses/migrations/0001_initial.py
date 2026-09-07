from decimal import Decimal

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models

import expenses.models


EXPENSE_ACCOUNTS = [
    ("6200", "Rent & Premises", "Rent, office and premises costs."),
    ("6210", "Utilities", "Electricity, water, gas and utility costs."),
    ("6220", "Marketing & Advertising", "Advertising, promotion and campaign costs."),
    ("6230", "Office Supplies", "Stationery, office consumables and small supplies."),
    ("6240", "Internet & Communication", "Internet, phone and communication costs."),
    ("6250", "Transport & Travel", "Local transport, travel and business conveyance."),
    ("6260", "Repairs & Maintenance", "Repairs and maintenance of business assets/premises."),
    ("6270", "Bank & MFS Charges", "Bank, card, bKash/Nagad and financial service charges."),
    ("6280", "Professional Services", "Professional, legal, consulting and outsourced services."),
    ("6290", "Staff Welfare", "Staff welfare, refreshments and related operating costs."),
]

DEFAULT_CATEGORIES = [
    ("RENT", "Rent & Premises", "6200", 10),
    ("UTIL", "Utilities", "6210", 20),
    ("MKT", "Marketing & Advertising", "6220", 30),
    ("OFFICE", "Office Supplies", "6230", 40),
    ("COMMS", "Internet & Communication", "6240", 50),
    ("TRAVEL", "Transport & Travel", "6250", 60),
    ("REPAIR", "Repairs & Maintenance", "6260", 70),
    ("BANKFEE", "Bank & MFS Charges", "6270", 80),
    ("PRO", "Professional Services", "6280", 90),
    ("STAFF", "Staff Welfare", "6290", 100),
    ("OTHER", "Other Expense", "6990", 999),
]


def seed_expense_categories(apps, schema_editor):
    Account = apps.get_model("accounting", "Account")
    ExpenseCategory = apps.get_model("expenses", "ExpenseCategory")

    for code, name, description in EXPENSE_ACCOUNTS:
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

    other_account, _ = Account.objects.update_or_create(
        code="6990",
        defaults={
            "name": "Other Expense",
            "account_type": "expense",
            "normal_balance": "debit",
            "description": "General operating expenses not assigned to a dedicated category.",
            "is_system": True,
            "allow_manual_entries": True,
            "is_active": True,
        },
    )

    accounts = {row.code: row for row in Account.objects.filter(code__in=[code for code, _, _ in EXPENSE_ACCOUNTS] + [other_account.code])}
    for code, name, account_code, sort_order in DEFAULT_CATEGORIES:
        ExpenseCategory.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "account": accounts[account_code],
                "description": f"Default {name} expense category.",
                "is_active": True,
                "sort_order": sort_order,
            },
        )


class Migration(migrations.Migration):
    initial = True

    dependencies = [("accounting", "0003_expense_source")]

    operations = [
        migrations.CreateModel(
            name="ExpenseCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=24, unique=True)),
                ("name", models.CharField(max_length=120, unique=True)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="expense_categories", to="accounting.account")),
            ],
            options={"ordering": ("sort_order", "name")},
        ),
        migrations.CreateModel(
            name="Expense",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("expense_no", models.CharField(default=expenses.models.make_expense_number, max_length=64, unique=True)),
                ("expense_date", models.DateField(default=django.utils.timezone.localdate)),
                ("payee", models.CharField(blank=True, max_length=160)),
                ("description", models.CharField(max_length=255)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=18)),
                ("preferred_payment_method", models.CharField(blank=True, choices=[("cash", "Cash"), ("bank", "Bank Transfer"), ("card", "Card"), ("bkash", "bKash"), ("nagad", "Nagad"), ("other", "Other")], max_length=20)),
                ("payment_method", models.CharField(blank=True, choices=[("cash", "Cash"), ("bank", "Bank Transfer"), ("card", "Card"), ("bkash", "bKash"), ("nagad", "Nagad"), ("other", "Other")], max_length=20)),
                ("payment_reference", models.CharField(blank=True, max_length=160)),
                ("payment_date", models.DateField(blank=True, null=True)),
                ("receipt_no", models.CharField(blank=True, max_length=120)),
                ("notes", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("pending", "Pending Approval"), ("approved", "Approved"), ("paid", "Paid"), ("rejected", "Rejected"), ("cancelled", "Cancelled"), ("voided", "Voided")], default="draft", max_length=16)),
                ("requested_by", models.CharField(blank=True, max_length=160)),
                ("approved_by", models.CharField(blank=True, max_length=160)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("paid_by", models.CharField(blank=True, max_length=160)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.CharField(blank=True, max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("category", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="expenses", to="expenses.expensecategory")),
            ],
            options={"ordering": ("-expense_date", "-id")},
        ),
        migrations.CreateModel(
            name="ExpenseEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event", models.CharField(choices=[("created", "Created"), ("updated", "Updated"), ("submitted", "Submitted"), ("approved", "Approved"), ("rejected", "Rejected"), ("paid", "Paid"), ("cancelled", "Cancelled"), ("voided", "Voided")], max_length=20)),
                ("previous_status", models.CharField(blank=True, max_length=16)),
                ("new_status", models.CharField(blank=True, max_length=16)),
                ("note", models.TextField(blank=True)),
                ("actor", models.CharField(blank=True, max_length=160)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expense", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="expenses.expense")),
            ],
            options={"ordering": ("-created_at", "-id")},
        ),
        migrations.AddIndex(model_name="expensecategory", index=models.Index(fields=["is_active", "sort_order"], name="expense_cat_active_idx")),
        migrations.AddIndex(model_name="expense", index=models.Index(fields=["status", "expense_date"], name="expense_status_date_idx")),
        migrations.AddIndex(model_name="expense", index=models.Index(fields=["category", "expense_date"], name="expense_cat_date_idx")),
        migrations.AddIndex(model_name="expense", index=models.Index(fields=["payment_method", "expense_date"], name="expense_method_date_idx")),
        migrations.AddConstraint(model_name="expense", constraint=models.CheckConstraint(condition=models.Q(("amount__gt", Decimal("0"))), name="expense_amount_positive")),
        migrations.AddIndex(model_name="expenseevent", index=models.Index(fields=["expense", "created_at"], name="expense_event_exp_idx")),
        migrations.RunPython(seed_expense_categories, migrations.RunPython.noop),
    ]
