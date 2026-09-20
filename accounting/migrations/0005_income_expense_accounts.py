from django.db import migrations, models


CASHBOOK_SYSTEM_ACCOUNTS = [
    ("1150", "Other Receivables", "asset", "debit", "Amounts due from non-sales income entries."),
    ("2050", "Other Payables", "liability", "credit", "Amounts due for non-purchase business expenses."),
]


def seed_cashbook_system_accounts(apps, schema_editor):
    Account = apps.get_model("accounting", "Account")
    for code, name, account_type, normal_balance, description in CASHBOOK_SYSTEM_ACCOUNTS:
        Account.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "account_type": account_type,
                "normal_balance": normal_balance,
                "description": description,
                "is_system": True,
                "allow_manual_entries": False,
                "is_active": True,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("accounting", "0004_replay_business_history_after_purchase_snapshots")]

    operations = [
        migrations.RunPython(seed_cashbook_system_accounts, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="journalentry",
            name="source_type",
            field=models.CharField(
                choices=[
                    ("sale", "Sales Order"),
                    ("sale_return", "Sales Return"),
                    ("sale_payment", "Sale Payment"),
                    ("supplier_payment", "Supplier Payment"),
                    ("purchase_receipt", "Purchase Receipt"),
                    ("purchase_overhead", "Purchase Overhead"),
                    ("purchase_return", "Purchase Return"),
                    ("courier_fee", "Courier / Collection Fee"),
                    ("expense", "Business Expense"),
                    ("cashbook", "Income & Expense"),
                    ("cashbook_settlement", "Income & Expense Settlement"),
                    ("opening_balance", "Opening Balance"),
                    ("manual", "Manual Journal"),
                    ("reversal", "Journal Reversal"),
                ],
                default="manual",
                max_length=24,
            ),
        ),
    ]
