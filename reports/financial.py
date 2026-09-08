from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum
from django.utils import timezone

from accounting.models import Account, JournalEntry, JournalLine
from accounting.services import trial_balance


ZERO = Decimal("0.00")
MONEY = Decimal("0.01")
CASH_EQUIVALENT_CODES = {"1000", "1010", "1020", "1030", "1040", "1090"}
OPERATING_SOURCE_TYPES = {
    JournalEntry.SourceType.SALE_PAYMENT,
    JournalEntry.SourceType.SUPPLIER_PAYMENT,
    JournalEntry.SourceType.COURIER_FEE,
    JournalEntry.SourceType.EXPENSE,
}

FINANCIAL_REPORT_KEYS = {"pnl", "balance_sheet", "cash_flow", "trial_balance"}
FINANCIAL_TABS = [
    ("pnl", "P&L"),
    ("balance_sheet", "Balance Sheet"),
    ("cash_flow", "Cash Flow"),
    ("trial_balance", "Trial Balance"),
]
FINANCIAL_META = {
    "pnl": ("Profit & Loss", "General Ledger revenue, contra-revenue, COGS and operating expense activity for the selected period."),
    "balance_sheet": ("Balance Sheet", "General Ledger assets, liabilities, equity and cumulative earnings as of the selected date."),
    "cash_flow": ("Cash Flow", "Movement in TechBari cash-equivalent General Ledger accounts, classified into operating, investing and financing activity."),
    "trial_balance": ("Trial Balance", "As-of General Ledger debit and credit balances across active Chart of Accounts accounts."),
}


def _money(value):
    return Decimal(value or ZERO).quantize(MONEY, rounding=ROUND_HALF_UP)


def _parse_date(value):
    value = str(value or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def parse_financial_filters(params):
    today = timezone.localdate()
    start_date = _parse_date(params.get("date_from")) or today.replace(day=1)
    end_date = _parse_date(params.get("date_to")) or today
    if end_date < start_date:
        start_date, end_date = end_date, start_date
    report_key = str(params.get("report") or "pnl").strip().lower()
    if report_key not in FINANCIAL_REPORT_KEYS:
        report_key = "pnl"
    return {
        "date_from": start_date,
        "date_to": end_date,
        "report": report_key,
        "channel": "",
        "warehouse": None,
        "movement_type": "",
    }


def _cell(value, kind="text"):
    return {"value": value, "kind": kind}


def _posted_lines(*, start_date=None, end_date=None, as_of=None):
    qs = JournalLine.objects.select_related("account", "entry", "entry__reversal_of").filter(
        entry__status__in=[JournalEntry.Status.POSTED, JournalEntry.Status.REVERSED],
    )
    if start_date:
        qs = qs.filter(entry__entry_date__gte=start_date)
    if end_date:
        qs = qs.filter(entry__entry_date__lte=end_date)
    if as_of:
        qs = qs.filter(entry__entry_date__lte=as_of)
    return qs


def _account_activity_map(*, start_date=None, end_date=None, as_of=None):
    qs = _posted_lines(start_date=start_date, end_date=end_date, as_of=as_of)
    data = {}
    for row in qs.values(
        "account_id", "account__code", "account__name", "account__account_type", "account__normal_balance"
    ).annotate(debit=Sum("debit"), credit=Sum("credit")).order_by("account__code"):
        debit = _money(row["debit"])
        credit = _money(row["credit"])
        if row["account__normal_balance"] == Account.NormalBalance.DEBIT:
            natural = _money(debit - credit)
        else:
            natural = _money(credit - debit)
        data[row["account_id"]] = {
            "id": row["account_id"],
            "code": row["account__code"],
            "name": row["account__name"],
            "type": row["account__account_type"],
            "normal": row["account__normal_balance"],
            "debit": debit,
            "credit": credit,
            "natural": natural,
        }
    return data


def _pnl_components(*, start_date=None, end_date=None, as_of=None):
    activity = _account_activity_map(start_date=start_date, end_date=end_date, as_of=as_of)
    revenue = []
    contra_revenue = []
    cogs = []
    operating_expenses = []
    for account in activity.values():
        if account["type"] == Account.Type.REVENUE:
            if account["normal"] == Account.NormalBalance.DEBIT:
                contra_revenue.append(account)
            else:
                revenue.append(account)
        elif account["type"] == Account.Type.EXPENSE:
            if account["code"] == "5000":
                cogs.append(account)
            else:
                operating_expenses.append(account)
    gross_revenue = _money(sum((row["natural"] for row in revenue), ZERO))
    returns = _money(sum((row["natural"] for row in contra_revenue), ZERO))
    net_revenue = _money(gross_revenue - returns)
    cogs_total = _money(sum((row["natural"] for row in cogs), ZERO))
    gross_profit = _money(net_revenue - cogs_total)
    operating_total = _money(sum((row["natural"] for row in operating_expenses), ZERO))
    net_profit = _money(gross_profit - operating_total)
    return {
        "revenue": revenue,
        "contra_revenue": contra_revenue,
        "cogs": cogs,
        "operating_expenses": operating_expenses,
        "gross_revenue": gross_revenue,
        "returns": returns,
        "net_revenue": net_revenue,
        "cogs_total": cogs_total,
        "gross_profit": gross_profit,
        "operating_total": operating_total,
        "net_profit": net_profit,
    }


def _statement_row(section, label, amount, *, code="", csv_label=None):
    return {
        "cells": [_cell(section), _cell(code or "—"), _cell(label), _cell(_money(amount), "money")],
        "csv": [section, code, csv_label or label, _money(amount)],
    }


def _pnl_report(filters):
    data = _pnl_components(start_date=filters["date_from"], end_date=filters["date_to"])
    rows = []
    for account in data["revenue"]:
        rows.append(_statement_row("Revenue", account["name"], account["natural"], code=account["code"]))
    for account in data["contra_revenue"]:
        rows.append(_statement_row("Less: Contra Revenue", account["name"], -account["natural"], code=account["code"]))
    rows.append(_statement_row("Subtotal", "Net Revenue", data["net_revenue"]))
    for account in data["cogs"]:
        rows.append(_statement_row("Cost of Goods Sold", account["name"], -account["natural"], code=account["code"]))
    rows.append(_statement_row("Subtotal", "Gross Profit", data["gross_profit"]))
    for account in data["operating_expenses"]:
        rows.append(_statement_row("Operating Expense", account["name"], -account["natural"], code=account["code"]))
    rows.append(_statement_row("Result", "Net Profit / (Loss)", data["net_profit"]))
    kpis = [
        {"label": "Net Revenue", "value": data["net_revenue"], "kind": "money"},
        {"label": "COGS", "value": data["cogs_total"], "kind": "money"},
        {"label": "Gross Profit", "value": data["gross_profit"], "kind": "money"},
        {"label": "Operating Expense", "value": data["operating_total"], "kind": "money"},
        {"label": "Net Profit", "value": data["net_profit"], "kind": "money"},
    ]
    return ["Section", "Code", "Account / Total", "Amount"], rows, kpis, "Range", "No General Ledger P&L activity found for this period."


def _balance_sheet_report(filters):
    as_of = filters["date_to"]
    activity = _account_activity_map(as_of=as_of)
    assets = [row for row in activity.values() if row["type"] == Account.Type.ASSET and row["natural"] != ZERO]
    liabilities = [row for row in activity.values() if row["type"] == Account.Type.LIABILITY and row["natural"] != ZERO]
    equity = [row for row in activity.values() if row["type"] == Account.Type.EQUITY and row["natural"] != ZERO]
    earnings = _pnl_components(as_of=as_of)["net_profit"]
    total_assets = _money(sum((row["natural"] for row in assets), ZERO))
    total_liabilities = _money(sum((row["natural"] for row in liabilities), ZERO))
    base_equity = _money(sum((row["natural"] for row in equity), ZERO))
    total_equity = _money(base_equity + earnings)
    equation_difference = _money(total_assets - total_liabilities - total_equity)

    rows = []
    for account in assets:
        rows.append(_statement_row("Assets", account["name"], account["natural"], code=account["code"]))
    rows.append(_statement_row("Assets", "Total Assets", total_assets))
    for account in liabilities:
        rows.append(_statement_row("Liabilities", account["name"], account["natural"], code=account["code"]))
    rows.append(_statement_row("Liabilities", "Total Liabilities", total_liabilities))
    for account in equity:
        rows.append(_statement_row("Equity", account["name"], account["natural"], code=account["code"]))
    rows.append(_statement_row("Equity", "Cumulative Earnings from GL", earnings))
    rows.append(_statement_row("Equity", "Total Equity", total_equity))
    rows.append(_statement_row("Check", "Liabilities + Equity", total_liabilities + total_equity))
    rows.append(_statement_row("Check", "Accounting Equation Difference", equation_difference))

    kpis = [
        {"label": "Total Assets", "value": total_assets, "kind": "money"},
        {"label": "Total Liabilities", "value": total_liabilities, "kind": "money"},
        {"label": "Total Equity", "value": total_equity, "kind": "money"},
        {"label": "Cumulative Earnings", "value": earnings, "kind": "money"},
        {"label": "Equation Difference", "value": equation_difference, "kind": "money"},
    ]
    return ["Section", "Code", "Account / Total", "Amount"], rows, kpis, "As of", "No General Ledger balance-sheet balances found as of this date."


def _cash_balance(as_of):
    if as_of is None:
        return ZERO
    qs = _posted_lines(as_of=as_of).filter(account__code__in=CASH_EQUIVALENT_CODES)
    totals = qs.aggregate(debit=Sum("debit"), credit=Sum("credit"))
    return _money((totals["debit"] or ZERO) - (totals["credit"] or ZERO))


def _effective_source(entry):
    if entry.source_type == JournalEntry.SourceType.REVERSAL and entry.reversal_of_id:
        return entry.reversal_of.source_type
    return entry.source_type


def _cash_flow_category(entry, lines):
    source = _effective_source(entry)
    if source in OPERATING_SOURCE_TYPES:
        return "Operating"
    if source == JournalEntry.SourceType.OPENING_BALANCE:
        return "Financing"
    non_cash = [line for line in lines if line.account.code not in CASH_EQUIVALENT_CODES]
    if source == JournalEntry.SourceType.MANUAL:
        if any(line.account.account_type == Account.Type.EQUITY for line in non_cash):
            return "Financing"
        if any(line.account.account_type == Account.Type.LIABILITY for line in non_cash):
            return "Financing"
        if any(
            line.account.account_type == Account.Type.ASSET and line.account.code not in {"1100", "1200"}
            for line in non_cash
        ):
            return "Investing"
    return "Operating"


def _cash_flow_report(filters):
    journals = JournalEntry.objects.filter(
        status__in=[JournalEntry.Status.POSTED, JournalEntry.Status.REVERSED],
        entry_date__range=(filters["date_from"], filters["date_to"]),
        lines__account__code__in=CASH_EQUIVALENT_CODES,
    ).select_related("reversal_of").prefetch_related("lines__account").distinct().order_by("entry_date", "id")

    rows = []
    totals = {"Operating": ZERO, "Investing": ZERO, "Financing": ZERO}
    for entry in journals:
        lines = list(entry.lines.all())
        cash_lines = [line for line in lines if line.account.code in CASH_EQUIVALENT_CODES]
        net = _money(sum(((line.debit or ZERO) - (line.credit or ZERO) for line in cash_lines), ZERO))
        if net == ZERO:
            continue
        category = _cash_flow_category(entry, lines)
        totals[category] = _money(totals[category] + net)
        cash_in = net if net > ZERO else ZERO
        cash_out = abs(net) if net < ZERO else ZERO
        rows.append({
            "cells": [
                _cell(entry.entry_date, "date"), _cell(entry.entry_no), _cell(category),
                _cell(entry.get_source_type_display()), _cell(entry.source_reference or "—"),
                _cell(cash_in, "money"), _cell(cash_out, "money"), _cell(net, "money"),
            ],
            "csv": [entry.entry_date.isoformat(), entry.entry_no, category, entry.get_source_type_display(), entry.source_reference, cash_in, cash_out, net],
        })

    opening_date = filters["date_from"] - timedelta(days=1)
    opening_cash = _cash_balance(opening_date)
    closing_cash = _cash_balance(filters["date_to"])
    net_change = _money(sum(totals.values(), ZERO))
    reconciliation_difference = _money(opening_cash + net_change - closing_cash)
    kpis = [
        {"label": "Opening Cash", "value": opening_cash, "kind": "money"},
        {"label": "Operating Cash Flow", "value": totals["Operating"], "kind": "money"},
        {"label": "Investing Cash Flow", "value": totals["Investing"], "kind": "money"},
        {"label": "Financing Cash Flow", "value": totals["Financing"], "kind": "money"},
        {"label": "Closing Cash", "value": closing_cash, "kind": "money"},
        {"label": "Reconciliation Difference", "value": reconciliation_difference, "kind": "money"},
    ]
    return ["Date", "Journal", "Activity", "Source", "Reference", "Cash In", "Cash Out", "Net"], rows, kpis, "Range", "No cash-equivalent General Ledger movement found for this period."


def _trial_balance_report(filters):
    rows_data, total_debit, total_credit = trial_balance(as_of=filters["date_to"])
    rows = []
    nonzero = 0
    for item in rows_data:
        if item["debit"] != ZERO or item["credit"] != ZERO:
            nonzero += 1
        rows.append({
            "cells": [
                _cell(item["account"].code), _cell(item["account"].name),
                _cell(item["account"].get_account_type_display()),
                _cell(item["debit_activity"], "money"), _cell(item["credit_activity"], "money"),
                _cell(item["debit"], "money"), _cell(item["credit"], "money"),
            ],
            "csv": [
                item["account"].code, item["account"].name, item["account"].get_account_type_display(),
                _money(item["debit_activity"]), _money(item["credit_activity"]), _money(item["debit"]), _money(item["credit"]),
            ],
        })
    difference = _money(total_debit - total_credit)
    kpis = [
        {"label": "Active Accounts", "value": len(rows_data), "kind": "number"},
        {"label": "Non-zero Balances", "value": nonzero, "kind": "number"},
        {"label": "Total Debit", "value": total_debit, "kind": "money"},
        {"label": "Total Credit", "value": total_credit, "kind": "money"},
        {"label": "Difference", "value": difference, "kind": "money"},
    ]
    return ["Code", "Account", "Type", "Debit Activity", "Credit Activity", "Ending Debit", "Ending Credit"], rows, kpis, "As of", "No Chart of Accounts rows are available."


def build_financial_report(params):
    filters = parse_financial_filters(params)
    report_key = filters["report"]
    if report_key == "balance_sheet":
        columns, rows, kpis, date_scope, empty = _balance_sheet_report(filters)
    elif report_key == "cash_flow":
        columns, rows, kpis, date_scope, empty = _cash_flow_report(filters)
    elif report_key == "trial_balance":
        columns, rows, kpis, date_scope, empty = _trial_balance_report(filters)
    else:
        columns, rows, kpis, date_scope, empty = _pnl_report(filters)
    title, description = FINANCIAL_META[report_key]
    return {
        "report_key": report_key,
        "report_title": title,
        "report_description": description,
        "filters": filters,
        "columns": columns,
        "rows": rows,
        "kpis": kpis,
        "csv_headers": columns,
        "csv_rows": [row["csv"] for row in rows],
        "extra_filters": [],
        "show_channel_filter": False,
        "show_warehouse_filter": False,
        "show_movement_filter": False,
        "warehouse_choices": [],
        "movement_choices": [],
        "date_scope_label": date_scope,
        "empty_message": empty,
    }
