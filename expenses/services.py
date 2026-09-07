from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounting.expense_posting import post_expense
from accounting.models import Account, JournalEntry
from accounting.services import AccountingError, reverse_journal

from .models import Expense, ExpenseEvent


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
