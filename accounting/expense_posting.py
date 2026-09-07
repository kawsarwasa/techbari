from .models import JournalEntry, ZERO
from .services import payment_asset_code, post_journal


def post_expense(expense, *, actor="Accounting"):
    """Translate one approved/paid operating expense into the double-entry ledger."""
    account = expense.category.account
    amount = expense.amount or ZERO
    return post_journal(
        entry_date=expense.payment_date or expense.expense_date,
        source_type=JournalEntry.SourceType.EXPENSE,
        source_key=expense.accounting_source_key,
        source_reference=expense.expense_no,
        description=f"Business expense {expense.expense_no} — {expense.description}",
        lines=[
            {
                "account": account,
                "debit": amount,
                "credit": ZERO,
                "memo": expense.payee or expense.category.name,
            },
            {
                "account": payment_asset_code(expense.payment_method),
                "debit": ZERO,
                "credit": amount,
                "memo": expense.payment_reference or expense.get_payment_method_display(),
            },
        ],
        actor=actor,
    )
