from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from accounting.expense_posting import post_expense
from accounting.models import Account, JournalEntry
from accounting.services import AccountingError, PAYMENT_ASSET_CODES, SYSTEM_ACCOUNTS, post_journal, reverse_journal

from .models import CashbookEntry, CashbookSettlement, Expense, ExpenseCategory, ExpenseEvent


class ExpenseError(ValidationError):
    pass


def _event(expense, event, *, previous_status="", new_status="", note="", actor=""):
    return ExpenseEvent.objects.create(
        expense=expense,
        event=event,
        previous_status=previous_status or "",
        new_status=new_status or "",
        note=note or "",
        actor=actor or "",
    )


def _error_text(exc):
    if hasattr(exc, "messages"):
        return " ".join(str(value) for value in exc.messages)
    return str(exc)


@transaction.atomic
def register_expense(expense, *, submit=False, actor="Dashboard"):
    expense.full_clean()
    is_new = expense.pk is None
    expense.created_by = expense.created_by or actor
    expense.status = Expense.Status.DRAFT
    expense.save()
    _event(
        expense,
        ExpenseEvent.Event.CREATED if is_new else ExpenseEvent.Event.UPDATED,
        new_status=expense.status,
        note="Expense record created." if is_new else "Expense draft updated.",
        actor=actor,
    )
    if submit:
        return submit_expense(expense=expense, actor=actor)
    return expense


@transaction.atomic
def update_draft_expense(*, expense, cleaned_data, actor="Dashboard"):
    expense = Expense.objects.select_for_update().get(pk=expense.pk)
    if expense.status != Expense.Status.DRAFT:
        raise ExpenseError("Only Draft expenses can be edited.")
    for field, value in cleaned_data.items():
        setattr(expense, field, value)
    expense.full_clean()
    expense.save()
    _event(expense, ExpenseEvent.Event.UPDATED, previous_status=expense.status, new_status=expense.status, note="Expense draft updated.", actor=actor)
    return expense


@transaction.atomic
def submit_expense(*, expense, note="", actor="Dashboard"):
    expense = Expense.objects.select_for_update().get(pk=expense.pk)
    if expense.status != Expense.Status.DRAFT:
        raise ExpenseError("Only Draft expenses can be submitted for approval.")
    old = expense.status
    expense.status = Expense.Status.PENDING
    expense.requested_by = actor
    expense.full_clean()
    expense.save(update_fields=["status", "requested_by", "updated_at"])
    _event(expense, ExpenseEvent.Event.SUBMITTED, previous_status=old, new_status=expense.status, note=note or "Submitted for approval.", actor=actor)
    return expense


@transaction.atomic
def approve_expense(*, expense, note="", actor="Dashboard"):
    expense = Expense.objects.select_for_update().get(pk=expense.pk)
    if expense.status != Expense.Status.PENDING:
        raise ExpenseError("Only Pending expenses can be approved.")
    old = expense.status
    expense.status = Expense.Status.APPROVED
    expense.approved_by = actor
    expense.approved_at = timezone.now()
    expense.full_clean()
    expense.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    _event(expense, ExpenseEvent.Event.APPROVED, previous_status=old, new_status=expense.status, note=note or "Expense approved.", actor=actor)
    return expense


@transaction.atomic
def reject_expense(*, expense, note="", actor="Dashboard"):
    expense = Expense.objects.select_for_update().get(pk=expense.pk)
    if expense.status != Expense.Status.PENDING:
        raise ExpenseError("Only Pending expenses can be rejected.")
    old = expense.status
    expense.status = Expense.Status.REJECTED
    expense.save(update_fields=["status", "updated_at"])
    _event(expense, ExpenseEvent.Event.REJECTED, previous_status=old, new_status=expense.status, note=note or "Expense rejected.", actor=actor)
    return expense


@transaction.atomic
def cancel_expense(*, expense, note="", actor="Dashboard"):
    expense = Expense.objects.select_for_update().get(pk=expense.pk)
    if expense.status not in {Expense.Status.DRAFT, Expense.Status.PENDING, Expense.Status.APPROVED}:
        raise ExpenseError("Only Draft, Pending or Approved expenses can be cancelled.")
    old = expense.status
    expense.status = Expense.Status.CANCELLED
    expense.save(update_fields=["status", "updated_at"])
    _event(expense, ExpenseEvent.Event.CANCELLED, previous_status=old, new_status=expense.status, note=note or "Expense cancelled.", actor=actor)
    return expense


@transaction.atomic
def pay_expense(*, expense, payment_method, payment_account, payment_reference="", payment_date=None, note="", actor="Dashboard"):
    expense = Expense.objects.select_for_update().select_related("category__account").get(pk=expense.pk)
    if expense.status != Expense.Status.APPROVED:
        raise ExpenseError("Only Approved expenses can be paid.")
    payment_method = str(payment_method or "").strip().lower()
    valid_methods = {value for value, _ in Expense.Method.choices}
    if payment_method not in valid_methods:
        raise ExpenseError("Select a valid expense payment method.")
    try:
        payment_account = Account.objects.get(pk=getattr(payment_account, "pk", payment_account))
    except (Account.DoesNotExist, TypeError, ValueError) as exc:
        raise ExpenseError("Select a valid payment account.") from exc
    if payment_account.account_type != Account.Type.ASSET or not payment_account.is_active or not payment_account.allow_manual_entries:
        raise ExpenseError("Select an active cash/bank/payment Asset account.")
    payment_reference = str(payment_reference or "").strip()
    if payment_method != Expense.Method.CASH and not payment_reference:
        raise ExpenseError("Non-cash expense payments require a transaction/reference number.")
    if not expense.category.is_active:
        raise ExpenseError("The linked expense category is inactive.")
    if not expense.category.account.is_active:
        raise ExpenseError("The linked accounting expense account is inactive.")

    payment_date = payment_date or timezone.localdate()
    expense.payment_method = payment_method
    expense.payment_account = payment_account
    expense.payment_reference = payment_reference
    expense.payment_date = payment_date
    expense.paid_by = actor
    expense.paid_at = timezone.now()
    old = expense.status
    expense.status = Expense.Status.PAID
    expense.full_clean()

    try:
        journal = post_expense(expense, actor=actor)
    except AccountingError as exc:
        raise ExpenseError(_error_text(exc)) from exc

    expense.save(update_fields=[
        "payment_method",
        "payment_account",
        "payment_reference",
        "payment_date",
        "paid_by",
        "paid_at",
        "status",
        "updated_at",
    ])
    _event(
        expense,
        ExpenseEvent.Event.PAID,
        previous_status=old,
        new_status=expense.status,
        note=note or f"Paid via {expense.get_payment_method_display()} from {payment_account.code} {payment_account.name}; journal {journal.entry_no}.",
        actor=actor,
    )
    return expense


@transaction.atomic
def void_paid_expense(*, expense, reason="", actor="Dashboard", reversal_date=None):
    expense = Expense.objects.select_for_update().get(pk=expense.pk)
    if expense.status != Expense.Status.PAID:
        raise ExpenseError("Only Paid expenses can be voided.")
    if not reason.strip():
        raise ExpenseError("A void reason is required.")
    journal = JournalEntry.objects.filter(source_key=expense.accounting_source_key).first()
    if not journal:
        raise ExpenseError("The accounting journal for this paid expense could not be found.")
    try:
        reversal = reverse_journal(
            journal=journal,
            reversal_date=reversal_date or timezone.localdate(),
            reason=reason,
            actor=actor,
        )
    except AccountingError as exc:
        raise ExpenseError(_error_text(exc)) from exc
    old = expense.status
    expense.status = Expense.Status.VOIDED
    expense.save(update_fields=["status", "updated_at"])
    _event(
        expense,
        ExpenseEvent.Event.VOIDED,
        previous_status=old,
        new_status=expense.status,
        note=f"{reason.strip()} Reversal journal: {reversal.entry_no}.",
        actor=actor,
    )
    return expense


class CashbookError(ValidationError):
    pass


def _cashbook_method_for_account(account):
    reverse_map = {code: method for method, code in PAYMENT_ASSET_CODES.items()}
    return reverse_map.get(account.code, CashbookSettlement.Method.OTHER)


def _cashbook_category_code(entry_type, name):
    prefix = "INC" if entry_type == ExpenseCategory.EntryType.INCOME else "EXP"
    stem = slugify(name).replace("-", "").upper()[:16] or "CATEGORY"
    base = f"{prefix}-{stem}"[:24]
    candidate = base
    counter = 2
    while ExpenseCategory.objects.filter(code=candidate).exists():
        suffix = f"-{counter}"
        candidate = f"{base[:24-len(suffix)]}{suffix}"
        counter += 1
    return candidate


def _next_category_account_code(entry_type):
    if entry_type == ExpenseCategory.EntryType.INCOME:
        candidates = range(4100, 4900, 10)
    else:
        candidates = range(6400, 6990, 10)
    used = set(Account.objects.values_list("code", flat=True))
    for value in candidates:
        code = str(value)
        if code not in used:
            return code
    raise CashbookError("No free automatic account code is available for this category.")


@transaction.atomic
def create_simple_category(*, entry_type, name, description="", actor="Dashboard"):
    entry_type = str(entry_type or "").strip().lower()
    if entry_type not in ExpenseCategory.EntryType.values:
        raise CashbookError("Select Income or Expense.")
    name = str(name or "").strip()
    if not name:
        raise CashbookError("Category name is required.")
    if ExpenseCategory.objects.filter(name__iexact=name).exists():
        raise CashbookError("A category with this name already exists.")

    account_type = Account.Type.REVENUE if entry_type == ExpenseCategory.EntryType.INCOME else Account.Type.EXPENSE
    normal = Account.NormalBalance.CREDIT if entry_type == ExpenseCategory.EntryType.INCOME else Account.NormalBalance.DEBIT
    account_code = _next_category_account_code(entry_type)
    account = Account.objects.create(
        code=account_code,
        name=name,
        account_type=account_type,
        normal_balance=normal,
        description=str(description or "").strip() or f"Auto-created for Income & Expense category: {name}.",
        is_system=False,
        allow_manual_entries=False,
        is_active=True,
    )
    category = ExpenseCategory(
        code=_cashbook_category_code(entry_type, name),
        entry_type=entry_type,
        name=name,
        account=account,
        description=str(description or "").strip(),
        is_active=True,
        sort_order=500,
    )
    category.full_clean()
    category.save()
    return category


def _post_cashbook_recognition(entry, *, actor="Dashboard"):
    if entry.entry_type == CashbookEntry.EntryType.EXPENSE:
        lines = [
            {"account": entry.category.account, "debit": entry.amount, "credit": Decimal("0.00"), "memo": entry.counterparty or entry.category.name},
            {"account": SYSTEM_ACCOUNTS["other_payable"], "debit": Decimal("0.00"), "credit": entry.amount, "memo": entry.entry_no},
        ]
    else:
        lines = [
            {"account": SYSTEM_ACCOUNTS["other_receivable"], "debit": entry.amount, "credit": Decimal("0.00"), "memo": entry.entry_no},
            {"account": entry.category.account, "debit": Decimal("0.00"), "credit": entry.amount, "memo": entry.counterparty or entry.category.name},
        ]
    return post_journal(
        entry_date=entry.entry_date,
        source_type=JournalEntry.SourceType.CASHBOOK,
        source_key=entry.accounting_source_key,
        source_reference=entry.entry_no,
        description=f"{entry.get_entry_type_display()} — {entry.category.name}" + (f" — {entry.description}" if entry.description else ""),
        lines=lines,
        actor=actor,
    )


@transaction.atomic
def register_cashbook_entry(*, entry, initial_amount=Decimal("0.00"), payment_account=None, reference="", actor="Dashboard"):
    initial_amount = Decimal(initial_amount or 0)
    if initial_amount < Decimal("0.00"):
        raise CashbookError("Initial payment cannot be negative.")
    entry.created_by = entry.created_by or actor
    entry.full_clean()
    entry.save()
    try:
        _post_cashbook_recognition(entry, actor=actor)
        if initial_amount > Decimal("0.00"):
            settle_cashbook_entry(
                entry=entry,
                amount=initial_amount,
                payment_account=payment_account,
                settlement_date=entry.entry_date,
                reference=reference,
                actor=actor,
            )
    except (AccountingError, ValidationError) as exc:
        raise CashbookError(_error_text(exc)) from exc
    return CashbookEntry.objects.get(pk=entry.pk)


@transaction.atomic
def settle_cashbook_entry(*, entry, amount, payment_account, settlement_date=None, reference="", note="", actor="Dashboard"):
    entry = CashbookEntry.objects.select_for_update().select_related("category__account").get(pk=entry.pk)
    if entry.is_voided:
        raise CashbookError("A voided entry cannot receive another payment.")
    amount = Decimal(amount or 0)
    if amount <= Decimal("0.00"):
        raise CashbookError("Payment amount must be greater than zero.")
    due = entry.due_amount
    if amount > due:
        raise CashbookError("Payment amount cannot exceed the remaining due.")
    try:
        payment_account = Account.objects.get(pk=getattr(payment_account, "pk", payment_account))
    except (Account.DoesNotExist, TypeError, ValueError) as exc:
        raise CashbookError("Choose a valid payment account.") from exc

    settlement = CashbookSettlement(
        entry=entry,
        amount=amount,
        payment_account=payment_account,
        method=_cashbook_method_for_account(payment_account),
        settlement_date=settlement_date or timezone.localdate(),
        reference=str(reference or "").strip(),
        note=str(note or "").strip(),
        actor=actor or "",
    )
    settlement.full_clean()
    settlement.save()

    if entry.entry_type == CashbookEntry.EntryType.EXPENSE:
        lines = [
            {"account": SYSTEM_ACCOUNTS["other_payable"], "debit": amount, "credit": Decimal("0.00"), "memo": entry.entry_no},
            {"account": payment_account, "debit": Decimal("0.00"), "credit": amount, "memo": settlement.reference or settlement.get_method_display()},
        ]
    else:
        lines = [
            {"account": payment_account, "debit": amount, "credit": Decimal("0.00"), "memo": settlement.reference or settlement.get_method_display()},
            {"account": SYSTEM_ACCOUNTS["other_receivable"], "debit": Decimal("0.00"), "credit": amount, "memo": entry.entry_no},
        ]

    try:
        post_journal(
            entry_date=settlement.settlement_date,
            source_type=JournalEntry.SourceType.CASHBOOK_SETTLEMENT,
            source_key=settlement.accounting_source_key,
            source_reference=entry.entry_no,
            description=f"{entry.get_entry_type_display()} settlement — {entry.entry_no}",
            lines=lines,
            actor=actor,
        )
    except (AccountingError, ValidationError) as exc:
        raise CashbookError(_error_text(exc)) from exc
    return settlement


@transaction.atomic
def void_cashbook_entry(*, entry, reason, reversal_date=None, actor="Dashboard"):
    entry = CashbookEntry.objects.select_for_update().get(pk=entry.pk)
    if entry.is_voided:
        return entry
    reason = str(reason or "").strip()
    if not reason:
        raise CashbookError("A void reason is required.")
    reversal_date = reversal_date or timezone.localdate()

    source_keys = [entry.accounting_source_key]
    source_keys.extend(
        settlement.accounting_source_key
        for settlement in entry.settlements.all()
    )
    journals = JournalEntry.objects.filter(source_key__in=source_keys).order_by("-entry_date", "-id")
    try:
        for journal in journals:
            if journal.status == JournalEntry.Status.POSTED:
                reverse_journal(
                    journal=journal,
                    reversal_date=reversal_date,
                    reason=reason,
                    actor=actor,
                )
    except (AccountingError, ValidationError) as exc:
        raise CashbookError(_error_text(exc)) from exc

    entry.is_voided = True
    entry.void_reason = reason
    entry.voided_by = actor or ""
    entry.voided_at = timezone.now()
    entry.save(update_fields=["is_voided", "void_reason", "voided_by", "voided_at", "updated_at"])
    return entry
