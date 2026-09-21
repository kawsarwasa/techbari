from django.db import migrations


EXPENSE_ACCOUNTS = (
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
    ("6300", "Salaries & Wages", "Employee salaries, wages, allowances and payroll-related operating costs."),
)

DEFAULT_CATEGORIES = (
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
    ("SALARY", "Salary & Wages", "6300", 110),
    ("COURIER", "Courier Expense", "6100", 120),
    ("OTHER", "Other Expense", "6990", 999),
)


def restore_default_expense_categories(apps, schema_editor):
    Account = apps.get_model("accounting", "Account")
    ExpenseCategory = apps.get_model("expenses", "ExpenseCategory")

    # These rows were originally seeded by older migrations. A manual-data reset
    # can remove them without rerunning those already-applied migrations, so
    # restore the canonical defaults idempotently.
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

    # 6100 and 6990 are core accounting accounts and should already exist.
    # Recreate them only if they are missing; do not rename/overwrite an
    # existing canonical account during this recovery migration.
    courier_account, _ = Account.objects.get_or_create(
        code="6100",
        defaults={
            "name": "Courier & Collection Fees",
            "account_type": "expense",
            "normal_balance": "debit",
            "description": "Courier, delivery collection and related fees.",
            "is_system": True,
            "allow_manual_entries": False,
            "is_active": True,
        },
    )
    other_account, _ = Account.objects.get_or_create(
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

    account_codes = [row[2] for row in DEFAULT_CATEGORIES]
    accounts = {
        account.code: account
        for account in Account.objects.filter(code__in=account_codes)
    }
    # Explicit assignments above make the intent clear and protect against an
    # unusual database where the query cache was built before get_or_create.
    accounts["6100"] = courier_account
    accounts["6990"] = other_account

    for code, name, account_code, sort_order in DEFAULT_CATEGORIES:
        ExpenseCategory.objects.update_or_create(
            code=code,
            defaults={
                "entry_type": "expense",
                "name": name,
                "account": accounts[account_code],
                "description": f"Default {name} expense category.",
                "is_active": True,
                "sort_order": sort_order,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("expenses", "0003_income_expense_cashbook"),
    ]

    operations = [
        migrations.RunPython(
            restore_default_expense_categories,
            migrations.RunPython.noop,
        ),
    ]
