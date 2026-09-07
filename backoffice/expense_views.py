from decimal import Decimal
from urllib.parse import urlencode

from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from expenses.forms import ExpenseActionForm, ExpenseCategoryForm, ExpenseForm, ExpensePaymentForm
from expenses.models import Expense, ExpenseCategory
from expenses.services import (
    ExpenseError,
    approve_expense,
    cancel_expense,
    pay_expense,
    register_expense,
    reject_expense,
    submit_expense,
    update_draft_expense,
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

    qs = Expense.objects.select_related("category", "category__account")
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
        expense_categories=ExpenseCategory.objects.filter(is_active=True).select_related("account"),
        expense_kpis={
            "month_paid": month_paid,
            "year_paid": year_paid,
            "approved_unpaid": approved_unpaid,
            "pending_count": pending_count,
        },
    )
    return render(request, "backoffice/pages/expenses/expenses.html", context)


def expense_add(request):
    form = ExpenseForm(request.POST or None, initial={"expense_date": timezone.localdate()})
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
    form = ExpenseForm(request.POST or None, instance=expense)
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
        Expense.objects.select_related("category", "category__account").prefetch_related("events"),
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
        category_rows=ExpenseCategory.objects.select_related("account").order_by("sort_order", "name"),
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
