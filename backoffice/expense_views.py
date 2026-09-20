from decimal import Decimal
from urllib.parse import urlencode

from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from expenses.forms import CashbookEntryForm, CashbookSettlementForm, ExpenseActionForm, ExpenseCategoryForm, ExpenseForm, ExpensePaymentForm, SimpleCategoryForm
from expenses.models import CashbookEntry, CashbookSettlement, Expense, ExpenseCategory
from expenses.services import (
    CashbookError,
    ExpenseError,
    create_simple_category,
    approve_expense,
    cancel_expense,
    pay_expense,
    register_expense,
    reject_expense,
    register_cashbook_entry,
    settle_cashbook_entry,
    submit_expense,
    update_draft_expense,
    void_cashbook_entry,
    void_paid_expense,
)

from .context import page_context


ZERO = Decimal("0.00")
NOTICE_TEXT = {
    "created": "Expense saved successfully.",
    "submitted": "Expense submitted for approval.",
    "approved": "Expense approved.",
    "rejected": "Expense rejected.",
    "paid": "Expense payment posted to Accounting.",
    "cancelled": "Expense cancelled.",
    "voided": "Paid expense voided with an Accounting reversal.",
    "category-created": "Expense category created.",
    "category-updated": "Expense category updated.",
}


def _message(exc):
    if hasattr(exc, "messages"):
        return " ".join(str(value) for value in exc.messages)
    return str(exc)


def _redirect_with(route_name, *, args=None, notice="", error=""):
    url = reverse(route_name, args=args or [])
    params = {}
    if notice:
        params["notice"] = notice
    if error:
        params["error"] = error
    return redirect(url + ("?" + urlencode(params) if params else ""))


def _base_context(request, *, tab="expenses"):
    context = page_context("expenses")
    context.update(
        expense_database=True,
        expense_tab=tab,
        expense_notice=NOTICE_TEXT.get(request.GET.get("notice", ""), ""),
        expense_error=request.GET.get("error", ""),
    )
    return context


def expenses(request):
    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    category_id = (request.GET.get("category") or "").strip()
    method = (request.GET.get("method") or "").strip()
    date_from = parse_date(request.GET.get("from") or "")
    date_to = parse_date(request.GET.get("to") or "")

    qs = Expense.objects.select_related("category", "category__account", "payment_account")
    if query:
        qs = qs.filter(
            Q(expense_no__icontains=query)
            | Q(description__icontains=query)
            | Q(payee__icontains=query)
            | Q(receipt_no__icontains=query)
            | Q(payment_reference__icontains=query)
        )
    if status in {value for value, _ in Expense.Status.choices}:
        qs = qs.filter(status=status)
    if category_id.isdigit():
        qs = qs.filter(category_id=int(category_id))
    if method in {value for value, _ in Expense.Method.choices}:
        qs = qs.filter(Q(payment_method=method) | Q(preferred_payment_method=method))
    if date_from:
        qs = qs.filter(expense_date__gte=date_from)
    if date_to:
        qs = qs.filter(expense_date__lte=date_to)

    today = timezone.localdate()
    month_paid = Expense.objects.filter(
        status=Expense.Status.PAID,
        payment_date__year=today.year,
        payment_date__month=today.month,
    ).aggregate(total=Sum("amount"))["total"] or ZERO
    year_paid = Expense.objects.filter(
        status=Expense.Status.PAID,
        payment_date__year=today.year,
    ).aggregate(total=Sum("amount"))["total"] or ZERO
    approved_unpaid = Expense.objects.filter(status=Expense.Status.APPROVED).aggregate(total=Sum("amount"))["total"] or ZERO
    pending_count = Expense.objects.filter(status=Expense.Status.PENDING).count()

    context = _base_context(request)
    context.update(
        expense_rows=qs.order_by("-expense_date", "-id"),
        expense_query=query,
        expense_status=status,
        expense_category=category_id,
        expense_method=method,
        expense_date_from=date_from,
        expense_date_to=date_to,
        expense_status_choices=Expense.Status.choices,
        expense_method_choices=Expense.Method.choices,
        expense_categories=ExpenseCategory.objects.filter(is_active=True, entry_type=ExpenseCategory.EntryType.EXPENSE).select_related("account"),
        expense_kpis={
            "month_paid": month_paid,
            "year_paid": year_paid,
            "approved_unpaid": approved_unpaid,
            "pending_count": pending_count,
        },
    )
    return render(request, "backoffice/pages/expenses/expenses.html", context)


def expense_add(request):
    form = ExpenseForm(request.POST or None, request.FILES or None, initial={"expense_date": timezone.localdate()})
    error = ""
    if request.method == "POST" and form.is_valid():
        try:
            expense = form.save(commit=False)
            submit_now = request.POST.get("action") == "submit"
            expense = register_expense(expense, submit=submit_now, actor="Dashboard")
            return _redirect_with(
                "backoffice:expense_detail",
                args=[expense.pk],
                notice="submitted" if submit_now else "created",
            )
        except (ExpenseError, ValidationError) as exc:
            error = _message(exc)
    elif request.method == "POST":
        error = "Please correct the highlighted expense fields."
    context = _base_context(request)
    context.update(expense_form=form, expense_error=error or context.get("expense_error", ""), expense_mode="add")
    return render(request, "backoffice/pages/expenses/expense_add.html", context)


def expense_edit(request, expense_id):
    expense = get_object_or_404(Expense, pk=expense_id)
    if expense.status != Expense.Status.DRAFT:
        return _redirect_with("backoffice:expense_detail", args=[expense.pk], error="Only Draft expenses can be edited.")
    form = ExpenseForm(request.POST or None, request.FILES or None, instance=expense)
    error = ""
    if request.method == "POST" and form.is_valid():
        try:
            expense = update_draft_expense(expense=expense, cleaned_data=form.cleaned_data, actor="Dashboard")
            if request.POST.get("action") == "submit":
                submit_expense(expense=expense, actor="Dashboard")
                notice = "submitted"
            else:
                notice = "created"
            return _redirect_with("backoffice:expense_detail", args=[expense.pk], notice=notice)
        except (ExpenseError, ValidationError) as exc:
            error = _message(exc)
    elif request.method == "POST":
        error = "Please correct the highlighted expense fields."
    context = _base_context(request)
    context.update(expense_form=form, expense=expense, expense_error=error or context.get("expense_error", ""), expense_mode="edit")
    return render(request, "backoffice/pages/expenses/expense_add.html", context)


def expense_detail(request, expense_id):
    expense = get_object_or_404(
        Expense.objects.select_related("category", "category__account", "payment_account").prefetch_related("events"),
        pk=expense_id,
    )
    context = _base_context(request)
    context.update(expense=expense, action_form=ExpenseActionForm())
    return render(request, "backoffice/pages/expenses/expense_detail.html", context)


def _post_action(request, expense_id, service, notice):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    expense = get_object_or_404(Expense, pk=expense_id)
    try:
        service(expense=expense, note=(request.POST.get("note") or "").strip(), actor="Dashboard")
        return _redirect_with("backoffice:expense_detail", args=[expense.pk], notice=notice)
    except (ExpenseError, ValidationError) as exc:
        return _redirect_with("backoffice:expense_detail", args=[expense.pk], error=_message(exc))


def expense_submit(request, expense_id):
    return _post_action(request, expense_id, submit_expense, "submitted")


def expense_approve(request, expense_id):
    return _post_action(request, expense_id, approve_expense, "approved")


def expense_reject(request, expense_id):
    return _post_action(request, expense_id, reject_expense, "rejected")


def expense_cancel(request, expense_id):
    return _post_action(request, expense_id, cancel_expense, "cancelled")


def expense_pay(request, expense_id):
    expense = get_object_or_404(Expense.objects.select_related("category", "category__account"), pk=expense_id)
    if expense.status != Expense.Status.APPROVED:
        return _redirect_with("backoffice:expense_detail", args=[expense.pk], error="Only Approved expenses can be paid.")
    initial = {
        "payment_method": expense.preferred_payment_method or Expense.Method.CASH,
        "payment_date": timezone.localdate(),
    }
    form = ExpensePaymentForm(request.POST or None, initial=initial)
    error = ""
    if request.method == "POST" and form.is_valid():
        try:
            pay_expense(
                expense=expense,
                payment_method=form.cleaned_data["payment_method"],
                payment_account=form.cleaned_data["payment_account"],
                payment_reference=form.cleaned_data["payment_reference"],
                payment_date=form.cleaned_data["payment_date"],
                note=form.cleaned_data["note"],
                actor="Dashboard",
            )
            return _redirect_with("backoffice:expense_detail", args=[expense.pk], notice="paid")
        except (ExpenseError, ValidationError) as exc:
            error = _message(exc)
    elif request.method == "POST":
        error = "Please correct the payment fields."
    context = _base_context(request)
    context.update(expense=expense, payment_form=form, expense_error=error or context.get("expense_error", ""))
    return render(request, "backoffice/pages/expenses/expense_pay.html", context)


def expense_void(request, expense_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    expense = get_object_or_404(Expense, pk=expense_id)
    try:
        void_paid_expense(
            expense=expense,
            reason=(request.POST.get("reason") or "").strip(),
            reversal_date=parse_date(request.POST.get("reversal_date") or "") or timezone.localdate(),
            actor="Dashboard",
        )
        return _redirect_with("backoffice:expense_detail", args=[expense.pk], notice="voided")
    except (ExpenseError, ValidationError) as exc:
        return _redirect_with("backoffice:expense_detail", args=[expense.pk], error=_message(exc))


def expense_categories(request):
    edit_id = (request.GET.get("edit") or "").strip()
    instance = ExpenseCategory.objects.filter(pk=int(edit_id)).first() if edit_id.isdigit() else None
    form = ExpenseCategoryForm(request.POST or None, instance=instance)
    error = ""
    if request.method == "POST" and form.is_valid():
        try:
            category = form.save(commit=False)
            category.full_clean()
            category.save()
            return _redirect_with(
                "backoffice:expense_categories",
                notice="category-updated" if instance else "category-created",
            )
        except ValidationError as exc:
            error = _message(exc)
    elif request.method == "POST":
        error = "Please correct the category fields."
    context = _base_context(request, tab="categories")
    context.update(
        category_form=form,
        category_rows=ExpenseCategory.objects.filter(entry_type=ExpenseCategory.EntryType.EXPENSE).select_related("account").order_by("sort_order", "name"),
        editing_category=instance,
        expense_error=error or context.get("expense_error", ""),
    )
    return render(request, "backoffice/pages/expenses/expense_categories.html", context)


def expense_category_toggle(request, category_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    category = get_object_or_404(ExpenseCategory, pk=category_id)
    category.is_active = not category.is_active
    try:
        category.full_clean()
        category.save(update_fields=["is_active", "updated_at"])
        return _redirect_with("backoffice:expense_categories", notice="category-updated")
    except ValidationError as exc:
        return _redirect_with("backoffice:expense_categories", error=_message(exc))


CASHBOOK_NOTICE_TEXT = {
    "created": "Entry saved and posted to Accounting.",
    "settled": "Payment recorded successfully.",
    "voided": "Entry voided and Accounting reversals posted.",
    "category-created": "Category created successfully.",
    "category-updated": "Category updated successfully.",
}


def _cashbook_actor(request):
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return user.get_full_name() or user.get_username()
    return "Dashboard"


def _cashbook_context(request, *, tab="transactions"):
    context = page_context("expenses")
    context.update(
        active_section="income_expense",
        cashbook_tab=tab,
        cashbook_notice=CASHBOOK_NOTICE_TEXT.get(request.GET.get("notice", ""), ""),
        cashbook_error=request.GET.get("error", ""),
    )
    return context


def income_expense(request):
    query = (request.GET.get("q") or "").strip()
    entry_type = (request.GET.get("type") or "").strip().lower()
    category_id = (request.GET.get("category") or "").strip()
    payment_status = (request.GET.get("status") or "").strip().lower()
    method = (request.GET.get("method") or "").strip().lower()
    date_from = parse_date(request.GET.get("from") or "")
    date_to = parse_date(request.GET.get("to") or "")

    qs = CashbookEntry.objects.select_related("category", "category__account").prefetch_related(
        "settlements", "settlements__payment_account"
    )
    if query:
        qs = qs.filter(
            Q(entry_no__icontains=query)
            | Q(category__name__icontains=query)
            | Q(counterparty__icontains=query)
            | Q(description__icontains=query)
        )
    if entry_type in CashbookEntry.EntryType.values:
        qs = qs.filter(entry_type=entry_type)
    if category_id.isdigit():
        qs = qs.filter(category_id=int(category_id))
    if date_from:
        qs = qs.filter(entry_date__gte=date_from)
    if date_to:
        qs = qs.filter(entry_date__lte=date_to)
    if method in CashbookSettlement.Method.values:
        qs = qs.filter(settlements__method=method).distinct()

    rows = list(qs.order_by("-entry_date", "-id"))
    if payment_status:
        def matches_status(entry):
            if payment_status == "overdue":
                return entry.is_overdue
            if payment_status == "voided":
                return entry.is_voided
            return entry.payment_status.lower() == payment_status
        rows = [entry for entry in rows if matches_status(entry)]

    active_rows = [entry for entry in rows if not entry.is_voided]
    income_rows = [entry for entry in active_rows if entry.entry_type == CashbookEntry.EntryType.INCOME]
    expense_rows = [entry for entry in active_rows if entry.entry_type == CashbookEntry.EntryType.EXPENSE]
    income_received = sum((entry.settled_amount for entry in income_rows), ZERO)
    expense_paid = sum((entry.settled_amount for entry in expense_rows), ZERO)
    income_due = sum((entry.due_amount for entry in income_rows), ZERO)
    expense_due = sum((entry.due_amount for entry in expense_rows), ZERO)

    context = _cashbook_context(request)
    context.update(
        cashbook_rows=rows,
        cashbook_query=query,
        cashbook_type=entry_type,
        cashbook_category=category_id,
        cashbook_status=payment_status,
        cashbook_method=method,
        cashbook_date_from=date_from,
        cashbook_date_to=date_to,
        cashbook_categories=ExpenseCategory.objects.filter(is_active=True).order_by("entry_type", "sort_order", "name"),
        cashbook_type_choices=CashbookEntry.EntryType.choices,
        cashbook_method_choices=CashbookSettlement.Method.choices,
        cashbook_status_choices=[
            ("paid", "Paid / Received"),
            ("partial", "Partial"),
            ("due", "Due"),
            ("overdue", "Overdue"),
            ("voided", "Voided"),
        ],
        cashbook_kpis={
            "income_received": income_received,
            "expense_paid": expense_paid,
            "income_due": income_due,
            "expense_due": expense_due,
            "net_cash": income_received - expense_paid,
            "entries": len(rows),
        },
    )
    return render(request, "backoffice/pages/income_expense/transactions.html", context)


def income_expense_add(request):
    form = CashbookEntryForm(
        request.POST or None,
        request.FILES or None,
        initial={"entry_date": timezone.localdate(), "entry_type": CashbookEntry.EntryType.EXPENSE},
    )
    error = ""
    if request.method == "POST" and form.is_valid():
        try:
            entry = form.save(commit=False)
            entry = register_cashbook_entry(
                entry=entry,
                initial_amount=form.cleaned_data["initial_amount"],
                payment_account=form.cleaned_data.get("payment_account"),
                reference=form.cleaned_data.get("reference", ""),
                actor=_cashbook_actor(request),
            )
            return _redirect_with("backoffice:income_expense_detail", args=[entry.pk], notice="created")
        except (CashbookError, ValidationError) as exc:
            error = _message(exc)
    elif request.method == "POST":
        error = "Please correct the highlighted fields."

    context = _cashbook_context(request, tab="add")
    context.update(cashbook_form=form, cashbook_error=error or context.get("cashbook_error", ""))
    return render(request, "backoffice/pages/income_expense/entry_add.html", context)


def income_expense_detail(request, entry_id):
    entry = get_object_or_404(
        CashbookEntry.objects.select_related("category", "category__account").prefetch_related(
            "settlements", "settlements__payment_account"
        ),
        pk=entry_id,
    )
    context = _cashbook_context(request)
    context.update(cashbook_entry=entry)
    return render(request, "backoffice/pages/income_expense/entry_detail.html", context)


def income_expense_settle(request, entry_id):
    entry = get_object_or_404(
        CashbookEntry.objects.select_related("category").prefetch_related("settlements"),
        pk=entry_id,
    )
    if entry.is_voided or entry.due_amount <= ZERO:
        return _redirect_with("backoffice:income_expense_detail", args=[entry.pk], error="This entry has no remaining due.")
    form = CashbookSettlementForm(
        request.POST or None,
        entry=entry,
        initial={"settlement_date": timezone.localdate()},
    )
    error = ""
    if request.method == "POST" and form.is_valid():
        try:
            settle_cashbook_entry(
                entry=entry,
                amount=form.cleaned_data["amount"],
                payment_account=form.cleaned_data["payment_account"],
                settlement_date=form.cleaned_data["settlement_date"],
                reference=form.cleaned_data["reference"],
                note=form.cleaned_data["note"],
                actor=_cashbook_actor(request),
            )
            return _redirect_with("backoffice:income_expense_detail", args=[entry.pk], notice="settled")
        except (CashbookError, ValidationError) as exc:
            error = _message(exc)
    elif request.method == "POST":
        error = "Please correct the payment fields."

    context = _cashbook_context(request)
    context.update(cashbook_entry=entry, settlement_form=form, cashbook_error=error or context.get("cashbook_error", ""))
    return render(request, "backoffice/pages/income_expense/settle.html", context)


def income_expense_void(request, entry_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    entry = get_object_or_404(CashbookEntry, pk=entry_id)
    try:
        void_cashbook_entry(
            entry=entry,
            reason=(request.POST.get("reason") or "").strip(),
            reversal_date=parse_date(request.POST.get("reversal_date") or "") or timezone.localdate(),
            actor=_cashbook_actor(request),
        )
        return _redirect_with("backoffice:income_expense_detail", args=[entry.pk], notice="voided")
    except (CashbookError, ValidationError) as exc:
        return _redirect_with("backoffice:income_expense_detail", args=[entry.pk], error=_message(exc))


def income_expense_categories(request):
    form = SimpleCategoryForm(request.POST or None, initial={"entry_type": ExpenseCategory.EntryType.EXPENSE})
    error = ""
    if request.method == "POST" and form.is_valid():
        try:
            create_simple_category(
                entry_type=form.cleaned_data["entry_type"],
                name=form.cleaned_data["name"],
                description=form.cleaned_data["description"],
                actor=_cashbook_actor(request),
            )
            return _redirect_with("backoffice:income_expense_categories", notice="category-created")
        except (CashbookError, ValidationError) as exc:
            error = _message(exc)
    elif request.method == "POST":
        error = "Please correct the category fields."

    context = _cashbook_context(request, tab="categories")
    context.update(
        cashbook_category_form=form,
        cashbook_category_rows=ExpenseCategory.objects.select_related("account").order_by("entry_type", "sort_order", "name"),
        cashbook_error=error or context.get("cashbook_error", ""),
    )
    return render(request, "backoffice/pages/income_expense/categories.html", context)


def income_expense_category_toggle(request, category_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    category = get_object_or_404(ExpenseCategory, pk=category_id)
    category.is_active = not category.is_active
    category.save(update_fields=["is_active", "updated_at"])
    return _redirect_with("backoffice:income_expense_categories", notice="category-updated")
