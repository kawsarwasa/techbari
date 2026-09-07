from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from accounting.forms import AccountForm, AccountingPeriodForm, ManualJournalHeaderForm
from accounting.models import Account, AccountingPeriod, JournalEntry
from accounting.services import (
    AccountingError,
    account_activity,
    accounting_summary,
    close_period,
    post_journal,
    reopen_period,
    reverse_journal,
    trial_balance,
)

from .context import page_context


NOTICE_TEXT = {
    "account-created": "Account created successfully.",
    "journal-posted": "Balanced journal posted successfully.",
    "journal-reversed": "Journal reversed successfully.",
    "period-created": "Accounting period created successfully.",
    "period-closed": "Accounting period closed successfully.",
    "period-reopened": "Accounting period reopened successfully.",
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


def _base_context(request):
    context = page_context("accounts")
    context["accounting_database"] = True
    context["accounting_notice"] = NOTICE_TEXT.get(request.GET.get("notice", ""), "")
    context["accounting_error"] = request.GET.get("error", "")
    return context


def accounts(request):
    summary = accounting_summary()
    tb_rows, tb_debit, tb_credit = trial_balance()
    context = _base_context(request)
    context.update(
        accounting_summary=summary,
        recent_journals=JournalEntry.objects.prefetch_related("lines").order_by("-entry_date", "-id")[:10],
        journal_count=JournalEntry.objects.count(),
        account_count=Account.objects.filter(is_active=True).count(),
        open_period_count=AccountingPeriod.objects.filter(status=AccountingPeriod.Status.OPEN).count(),
        trial_debit=tb_debit,
        trial_credit=tb_credit,
        trial_balanced=tb_debit == tb_credit,
        trial_rows=tb_rows[:8],
    )
    return render(request, "backoffice/pages/accounts/accounts.html", context)


def chart_accounts(request):
    query = (request.GET.get("q") or "").strip()
    account_type = (request.GET.get("type") or "").strip()
    qs = Account.objects.all()
    if query:
        qs = qs.filter(Q(code__icontains=query) | Q(name__icontains=query) | Q(description__icontains=query))
    if account_type in {value for value, _ in Account.Type.choices}:
        qs = qs.filter(account_type=account_type)
    context = _base_context(request)
    context.update(
        accounts_rows=qs.order_by("code"),
        account_query=query,
        selected_account_type=account_type,
        account_type_choices=Account.Type.choices,
    )
    return render(request, "backoffice/pages/accounts/chart_of_accounts.html", context)


def account_add(request):
    form = AccountForm(request.POST or None)
    error = ""
    if request.method == "POST" and form.is_valid():
        try:
            account = form.save(commit=False)
            account.is_system = False
            account.full_clean()
            account.save()
            return _redirect_with("backoffice:chart_accounts", notice="account-created")
        except ValidationError as exc:
            error = _message(exc)
    elif request.method == "POST":
        error = "Please correct the highlighted account fields."
    context = _base_context(request)
    context.update(account_form=form, accounting_error=error or context.get("accounting_error", ""))
    return render(request, "backoffice/pages/accounts/account_add.html", context)


def journals(request):
    query = (request.GET.get("q") or "").strip()
    source = (request.GET.get("source") or "").strip()
    status = (request.GET.get("status") or "").strip()
    date_from = parse_date(request.GET.get("from") or "")
    date_to = parse_date(request.GET.get("to") or "")
    qs = JournalEntry.objects.prefetch_related("lines__account")
    if query:
        qs = qs.filter(
            Q(entry_no__icontains=query)
            | Q(source_reference__icontains=query)
            | Q(description__icontains=query)
        )
    if source in {value for value, _ in JournalEntry.SourceType.choices}:
        qs = qs.filter(source_type=source)
    if status in {value for value, _ in JournalEntry.Status.choices}:
        qs = qs.filter(status=status)
    if date_from:
        qs = qs.filter(entry_date__gte=date_from)
    if date_to:
        qs = qs.filter(entry_date__lte=date_to)
    context = _base_context(request)
    context.update(
        journal_rows=qs.order_by("-entry_date", "-id"),
        journal_query=query,
        journal_source=source,
        journal_status=status,
        journal_date_from=date_from,
        journal_date_to=date_to,
        journal_source_choices=JournalEntry.SourceType.choices,
        journal_status_choices=JournalEntry.Status.choices,
    )
    return render(request, "backoffice/pages/accounts/journals.html", context)


def _manual_lines(post):
    account_ids = post.getlist("account_id")
    debits = post.getlist("debit")
    credits = post.getlist("credit")
    memos = post.getlist("memo")
    count = max(len(account_ids), len(debits), len(credits), len(memos), 0)
    rows = []
    for index in range(count):
        account_id = (account_ids[index] if index < len(account_ids) else "").strip()
        debit_raw = (debits[index] if index < len(debits) else "").strip()
        credit_raw = (credits[index] if index < len(credits) else "").strip()
        memo = (memos[index] if index < len(memos) else "").strip()
        if not account_id and not debit_raw and not credit_raw and not memo:
            continue
        if not account_id.isdigit():
            raise AccountingError(f"Journal row {index + 1}: select an account.")
        account = Account.objects.filter(pk=int(account_id), is_active=True).first()
        if not account:
            raise AccountingError(f"Journal row {index + 1}: selected account is unavailable.")
        try:
            debit = Decimal(debit_raw or "0")
            credit = Decimal(credit_raw or "0")
        except InvalidOperation as exc:
            raise AccountingError(f"Journal row {index + 1}: enter valid debit/credit amounts.") from exc
        rows.append({"account": account, "debit": debit, "credit": credit, "memo": memo})
    return rows


def journal_add(request):
    initial = {"entry_date": timezone.localdate()}
    form = ManualJournalHeaderForm(request.POST or None, initial=initial)
    error = ""
    if request.method == "POST" and form.is_valid():
        try:
            lines = _manual_lines(request.POST)
            journal = post_journal(
                entry_date=form.cleaned_data["entry_date"],
                source_type=JournalEntry.SourceType.MANUAL,
                source_reference=form.cleaned_data["source_reference"],
                description=form.cleaned_data["description"],
                lines=lines,
                actor="Dashboard",
            )
            return _redirect_with("backoffice:journal_detail", args=[journal.pk], notice="journal-posted")
        except (AccountingError, ValidationError) as exc:
            error = _message(exc)
    elif request.method == "POST":
        error = "Please correct the journal header fields."
    context = _base_context(request)
    context.update(
        journal_form=form,
        journal_accounts=Account.objects.filter(is_active=True, allow_manual_entries=True).order_by("code"),
        accounting_error=error or context.get("accounting_error", ""),
    )
    return render(request, "backoffice/pages/accounts/journal_add.html", context)


def journal_detail(request, journal_id):
    journal = get_object_or_404(
        JournalEntry.objects.prefetch_related("lines__account", "events"),
        pk=journal_id,
    )
    context = _base_context(request)
    context.update(journal=journal)
    return render(request, "backoffice/pages/accounts/journal_detail.html", context)


def journal_reverse(request, journal_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    journal = get_object_or_404(JournalEntry, pk=journal_id)
    reversal_date = parse_date(request.POST.get("reversal_date") or "") or timezone.localdate()
    try:
        reversal = reverse_journal(
            journal=journal,
            reversal_date=reversal_date,
            reason=request.POST.get("reason", ""),
            actor="Dashboard",
        )
        return _redirect_with("backoffice:journal_detail", args=[reversal.pk], notice="journal-reversed")
    except (AccountingError, ValidationError) as exc:
        return _redirect_with("backoffice:journal_detail", args=[journal.pk], error=_message(exc))


def general_ledger(request):
    accounts = Account.objects.filter(is_active=True).order_by("code")
    account_id = request.GET.get("account") or ""
    account = accounts.filter(pk=int(account_id)).first() if str(account_id).isdigit() else accounts.first()
    date_from = parse_date(request.GET.get("from") or "")
    date_to = parse_date(request.GET.get("to") or "")
    rows = []
    running = Decimal("0.00")
    if account:
        for line in account_activity(account, start_date=date_from, end_date=date_to):
            if account.normal_balance == Account.NormalBalance.DEBIT:
                running += line.debit - line.credit
            else:
                running += line.credit - line.debit
            rows.append({"line": line, "running_balance": running})
    context = _base_context(request)
    context.update(
        ledger_accounts=accounts,
        ledger_account=account,
        ledger_rows=rows,
        ledger_date_from=date_from,
        ledger_date_to=date_to,
        ledger_balance=running,
    )
    return render(request, "backoffice/pages/accounts/general_ledger.html", context)


def trial_balance_view(request):
    as_of = parse_date(request.GET.get("as_of") or "")
    rows, debit, credit = trial_balance(as_of=as_of)
    context = _base_context(request)
    context.update(
        trial_rows=rows,
        trial_as_of=as_of,
        trial_debit=debit,
        trial_credit=credit,
        trial_balanced=debit == credit,
    )
    return render(request, "backoffice/pages/accounts/trial_balance.html", context)


def periods(request):
    form = AccountingPeriodForm(request.POST or None)
    error = ""
    if request.method == "POST" and form.is_valid():
        try:
            period = form.save(commit=False)
            period.status = AccountingPeriod.Status.OPEN
            period.full_clean()
            period.save()
            return _redirect_with("backoffice:accounting_periods", notice="period-created")
        except ValidationError as exc:
            error = _message(exc)
    elif request.method == "POST":
        error = "Please correct the accounting period fields."
    context = _base_context(request)
    context.update(
        period_form=form,
        period_rows=AccountingPeriod.objects.all(),
        accounting_error=error or context.get("accounting_error", ""),
    )
    return render(request, "backoffice/pages/accounts/periods.html", context)


def period_toggle(request, period_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    period = get_object_or_404(AccountingPeriod, pk=period_id)
    try:
        if period.status == AccountingPeriod.Status.OPEN:
            close_period(period=period, actor="Dashboard")
            notice = "period-closed"
        else:
            reopen_period(period=period, actor="Dashboard")
            notice = "period-reopened"
        return _redirect_with("backoffice:accounting_periods", notice=notice)
    except (AccountingError, ValidationError) as exc:
        return _redirect_with("backoffice:accounting_periods", error=_message(exc))
