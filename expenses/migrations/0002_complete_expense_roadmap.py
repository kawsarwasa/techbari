import django.db.models.deletion
from django.db import migrations, models


NEW_EXPENSE_ACCOUNTS = [
    ("6300", "Salaries & Wages", "Employee salaries, wages, allowances and payroll-related operating costs."),
]

NEW_CATEGORIES = [
    ("SALARY", "Salary & Wages", "6300", 110),
    ("COURIER", "Courier Expense", "6100", 120),
]


def seed_expense_completion(apps, schema_editor):
    Account = apps.get_model("accounting", "Account")
    ExpenseCategory = apps.get_model("expenses", "ExpenseCategory")

    for code, name, description in NEW_EXPENSE_ACCOUNTS:
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

    for code, name, account_code, sort_order in NEW_CATEGORIES:
        account = Account.objects.get(code=account_code)
        ExpenseCategory.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "account": account,
                "description": f"Default {name} expense category.",
                "is_active": True,
                "sort_order": sort_order,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("expenses", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="expense",
            name="attachment",
            field=models.FileField(blank=True, upload_to="expenses/attachments/%Y/%m/"),
        ),
        migrations.AddField(
            model_name="expense",
            name="payment_account",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="expense_payments",
                to="accounting.account",
            ),
        ),
        migrations.AddIndex(
            model_name="expense",
            index=models.Index(fields=["payment_account", "payment_date"], name="expense_payacct_date_idx"),
        ),
        migrations.RunPython(seed_expense_completion, migrations.RunPython.noop),
    ]
