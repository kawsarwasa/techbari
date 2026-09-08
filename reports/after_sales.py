from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from expenses.models import Expense, ExpenseCategory
from inventory.models import Warehouse
from payments.models import PaymentMethodConfig, PaymentTransaction
from returns.models import SalesReturn
from serial_tracking.models import SerializedUnit, WarrantyClaim


ZERO = Decimal("0.00")
MONEY = Decimal("0.01")

AFTER_SALES_REPORT_KEYS = {
    "payment",
    "expense",
    "returns",
    "warranty",
    "serial_imei",
}

AFTER_SALES_TABS = [
    ("payment", "Payment"),
    ("expense", "Expense"),
    ("returns", "Returns"),
    ("warranty", "Warranty"),
    ("serial_imei", "Serial / IMEI"),
]

AFTER_SALES_META = {
    "payment": ("Payment Report", "Payment-ledger activity across sales, supplier payments, refunds and reversals."),
    "expense": ("Expense Report", "Business expense lifecycle, category, payment method and payment-account reporting."),
    "returns": ("Returns Report", "Customer/POS/courier return cases with credit, refund and restock outcomes."),
    "warranty": ("Warranty Report", "Warranty/RMA claims with service status, coverage and replacement outcome."),
    "serial_imei": ("Serial / IMEI Report", "Serialized-unit registry with current warehouse, lifecycle status and warranty references."),
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


def _positive_int(value):
    value = str(value or "").strip()
    return int(value) if value.isdigit() and int(value) > 0 else None


def _valid_choice(value, choices):
    value = str(value or "").strip().lower()
    return value if value in set(choices) else ""


def parse_after_sales_filters(params):
    today = timezone.localdate()
    start_date = _parse_date(params.get("date_from")) or today.replace(day=1)
    end_date = _parse_date(params.get("date_to")) or today
    if end_date < start_date:
        start_date, end_date = end_date, start_date

    report_key = str(params.get("report") or "payment").strip().lower()
    if report_key not in AFTER_SALES_REPORT_KEYS:
        report_key = "payment"

    expense_category = _positive_int(params.get("expense_category"))
    if expense_category and not ExpenseCategory.objects.filter(pk=expense_category).exists():
        expense_category = None

    warehouse = _positive_int(params.get("warehouse"))
    if warehouse and not Warehouse.objects.filter(pk=warehouse).exists():
        warehouse = None

    return {
        "date_from": start_date,
        "date_to": end_date,
        "report": report_key,
        "channel": "",
        "warehouse": warehouse,
        "movement_type": "",
        "payment_kind": _valid_choice(params.get("payment_kind"), PaymentTransaction.Kind.values),
        "payment_method": _valid_choice(params.get("payment_method"), PaymentMethodConfig.Method.values),
        "payment_status": _valid_choice(params.get("payment_status"), PaymentTransaction.Status.values),
        "expense_status": _valid_choice(params.get("expense_status"), Expense.Status.values),
        "expense_category": expense_category,
        "expense_method": _valid_choice(params.get("expense_method"), Expense.Method.values),
        "return_status": _valid_choice(params.get("return_status"), SalesReturn.Status.values),
        "return_source": _valid_choice(params.get("return_source"), SalesReturn.Source.values),
        "return_reason": _valid_choice(params.get("return_reason"), SalesReturn.Reason.values),
        "warranty_status": _valid_choice(params.get("warranty_status"), WarrantyClaim.Status.values),
        "serial_status": _valid_choice(params.get("serial_status"), SerializedUnit.Status.values),
    }


def _cell(value, kind="text"):
    return {"value": value, "kind": kind}


def _date_cell(value):
    return _cell(value, "date") if value else _cell("—")


def _choices(values, *, all_label="All"):
    return [("", all_label), *[(str(value), str(label)) for value, label in values]]


def _filter(name, label, selected, choices):
    return {
        "name": name,
        "label": label,
        "selected": "" if selected in (None, "") else str(selected),
        "choices": choices,
    }


def _payment_report(filters):
    qs = PaymentTransaction.objects.filter(
        transaction_date__range=(filters["date_from"], filters["date_to"])
    ).select_related(
        "sales_order__customer",
        "purchase_payment__supplier",
        "purchase_payment__purchase",
    )
    if filters["payment_kind"]:
        qs = qs.filter(kind=filters["payment_kind"])
    if filters["payment_method"]:
        qs = qs.filter(method=filters["payment_method"])
    if filters["payment_status"]:
        qs = qs.filter(status=filters["payment_status"])
    transactions = list(qs.order_by("-transaction_date", "-id"))

    columns = ["Date", "Transaction", "Kind", "Direction", "Method", "Status", "Counterparty", "Reference", "Amount", "Reconciliation"]
    rows = []
    for transaction in transactions:
        rows.append({
            "cells": [
                _cell(transaction.transaction_date, "date"),
                _cell(transaction.transaction_no),
                _cell(transaction.get_kind_display()),
                _cell(transaction.get_direction_display()),
                _cell(transaction.get_method_display()),
                _cell(transaction.get_status_display()),
                _cell(transaction.counterparty),
                _cell(transaction.source_reference or transaction.provider_reference or "—"),
                _cell(transaction.amount, "money"),
                _cell(transaction.get_reconciliation_status_display()),
            ],
            "csv": [
                transaction.transaction_date.isoformat(),
                transaction.transaction_no,
                transaction.get_kind_display(),
                transaction.get_direction_display(),
                transaction.get_method_display(),
                transaction.get_status_display(),
                transaction.counterparty,
                transaction.source_reference or transaction.provider_reference,
                _money(transaction.amount),
                transaction.get_reconciliation_status_display(),
            ],
        })

    completed = [row for row in transactions if row.status == PaymentTransaction.Status.COMPLETED]
    money_in = _money(sum((row.amount for row in completed if row.direction == PaymentTransaction.Direction.IN), ZERO))
    money_out = _money(sum((row.amount for row in completed if row.direction == PaymentTransaction.Direction.OUT), ZERO))
    reconciled = sum(row.reconciliation_status == PaymentTransaction.ReconciliationStatus.RECONCILED for row in transactions)
    kpis = [
        {"label": "Transactions", "value": len(transactions), "kind": "number"},
        {"label": "Completed Money In", "value": money_in, "kind": "money"},
        {"label": "Completed Money Out", "value": money_out, "kind": "money"},
        {"label": "Net Cash Flow", "value": _money(money_in - money_out), "kind": "money"},
        {"label": "Reconciled", "value": reconciled, "kind": "number"},
    ]
    extra_filters = [
        _filter("payment_kind", "Kind", filters["payment_kind"], _choices(PaymentTransaction.Kind.choices)),
        _filter("payment_method", "Method", filters["payment_method"], _choices(PaymentMethodConfig.Method.choices)),
        _filter("payment_status", "Status", filters["payment_status"], _choices(PaymentTransaction.Status.choices)),
    ]
    return columns, rows, kpis, extra_filters, "Range", "No payment transactions found for this filter."


def _expense_report(filters):
    qs = Expense.objects.filter(
        expense_date__range=(filters["date_from"], filters["date_to"])
    ).select_related("category", "payment_account")
    if filters["expense_status"]:
        qs = qs.filter(status=filters["expense_status"])
    if filters["expense_category"]:
        qs = qs.filter(category_id=filters["expense_category"])
    if filters["expense_method"]:
        qs = qs.filter(payment_method=filters["expense_method"])
    expenses = list(qs.order_by("-expense_date", "-id"))

    columns = ["Date", "Expense", "Category", "Payee", "Description", "Status", "Amount", "Payment Method", "Payment Account", "Payment Date", "Reference"]
    rows = []
    for expense in expenses:
        rows.append({
            "cells": [
                _cell(expense.expense_date, "date"),
                _cell(expense.expense_no),
                _cell(expense.category.name),
                _cell(expense.payee or "—"),
                _cell(expense.description),
                _cell(expense.get_status_display()),
                _cell(expense.amount, "money"),
                _cell(expense.get_payment_method_display() if expense.payment_method else "—"),
                _cell(str(expense.payment_account) if expense.payment_account_id else "—"),
                _date_cell(expense.payment_date),
                _cell(expense.payment_reference or expense.receipt_no or "—"),
            ],
            "csv": [
                expense.expense_date.isoformat(), expense.expense_no, expense.category.name, expense.payee,
                expense.description, expense.get_status_display(), _money(expense.amount),
                expense.get_payment_method_display() if expense.payment_method else "",
                str(expense.payment_account) if expense.payment_account_id else "",
                expense.payment_date.isoformat() if expense.payment_date else "",
                expense.payment_reference or expense.receipt_no,
            ],
        })

    inactive = {Expense.Status.REJECTED, Expense.Status.CANCELLED, Expense.Status.VOIDED}
    active_amount = _money(sum((row.amount for row in expenses if row.status not in inactive), ZERO))
    paid_amount = _money(sum((row.amount for row in expenses if row.status == Expense.Status.PAID), ZERO))
    kpis = [
        {"label": "Expense Records", "value": len(expenses), "kind": "number"},
        {"label": "Active Amount", "value": active_amount, "kind": "money"},
        {"label": "Paid Amount", "value": paid_amount, "kind": "money"},
        {"label": "Pending Approval", "value": sum(row.status == Expense.Status.PENDING for row in expenses), "kind": "number"},
        {"label": "Approved / Unpaid", "value": sum(row.status == Expense.Status.APPROVED for row in expenses), "kind": "number"},
    ]
    category_choices = [("", "All"), *[(str(row.pk), row.name) for row in ExpenseCategory.objects.order_by("sort_order", "name")]]
    extra_filters = [
        _filter("expense_status", "Status", filters["expense_status"], _choices(Expense.Status.choices)),
        _filter("expense_category", "Category", filters["expense_category"], category_choices),
        _filter("expense_method", "Payment Method", filters["expense_method"], _choices(Expense.Method.choices)),
    ]
    return columns, rows, kpis, extra_filters, "Range", "No expenses found for this filter."


def _returns_report(filters):
    qs = SalesReturn.objects.filter(
        requested_date__range=(filters["date_from"], filters["date_to"])
    ).select_related("order__customer", "warehouse").prefetch_related("items", "refunds")
    if filters["return_status"]:
        qs = qs.filter(status=filters["return_status"])
    if filters["return_source"]:
        qs = qs.filter(source=filters["return_source"])
    if filters["return_reason"]:
        qs = qs.filter(reason_category=filters["return_reason"])
    returns = list(qs.order_by("-requested_date", "-id"))

    columns = ["Requested", "Return", "Order", "Customer", "Source", "Reason", "Status", "Units", "Restocked", "Credit", "Refunded", "Completed"]
    rows = []
    metrics = []
    for sales_return in returns:
        items = list(sales_return.items.all())
        refunds = list(sales_return.refunds.all())
        units = sum(int(item.quantity or 0) for item in items)
        restocked = sum(int(item.restocked_quantity or 0) for item in items)
        credit = _money(sum((item.refund_amount for item in items), ZERO))
        refunded = _money(sum((refund.amount for refund in refunds), ZERO))
        metrics.append((sales_return, units, restocked, credit, refunded))
        rows.append({
            "cells": [
                _cell(sales_return.requested_date, "date"), _cell(sales_return.return_no), _cell(sales_return.order.order_number),
                _cell(sales_return.customer_name), _cell(sales_return.get_source_display()), _cell(sales_return.get_reason_category_display()),
                _cell(sales_return.get_status_display()), _cell(units, "number"), _cell(restocked, "number"),
                _cell(credit, "money"), _cell(refunded, "money"), _date_cell(sales_return.completed_date),
            ],
            "csv": [
                sales_return.requested_date.isoformat(), sales_return.return_no, sales_return.order.order_number,
                sales_return.customer_name, sales_return.get_source_display(), sales_return.get_reason_category_display(),
                sales_return.get_status_display(), units, restocked, credit, refunded,
                sales_return.completed_date.isoformat() if sales_return.completed_date else "",
            ],
        })

    completed = [row for row in metrics if row[0].status == SalesReturn.Status.COMPLETED]
    kpis = [
        {"label": "Return Cases", "value": len(metrics), "kind": "number"},
        {"label": "Completed", "value": len(completed), "kind": "number"},
        {"label": "Returned Units", "value": sum(row[1] for row in metrics), "kind": "number"},
        {"label": "Restocked Units", "value": sum(row[2] for row in completed), "kind": "number"},
        {"label": "Completed Credit", "value": _money(sum((row[3] for row in completed), ZERO)), "kind": "money"},
        {"label": "Cash Refunds", "value": _money(sum((row[4] for row in completed), ZERO)), "kind": "money"},
    ]
    extra_filters = [
        _filter("return_status", "Status", filters["return_status"], _choices(SalesReturn.Status.choices)),
        _filter("return_source", "Source", filters["return_source"], _choices(SalesReturn.Source.choices)),
        _filter("return_reason", "Reason", filters["return_reason"], _choices(SalesReturn.Reason.choices)),
    ]
    return columns, rows, kpis, extra_filters, "Requested Range", "No return cases found for this requested-date range."


def _warranty_report(filters):
    qs = WarrantyClaim.objects.filter(
        claim_date__range=(filters["date_from"], filters["date_to"])
    ).select_related("unit__variant__product", "unit__warehouse", "replacement_unit")
    if filters["warranty_status"]:
        qs = qs.filter(status=filters["warranty_status"])
    if filters["warehouse"]:
        qs = qs.filter(unit__warehouse_id=filters["warehouse"])
    claims = list(qs.order_by("-claim_date", "-id"))

    columns = ["Claim Date", "Claim", "Product", "SKU", "Serial / IMEI", "Customer", "Status", "Within Warranty", "Issue", "Resolved", "Replacement"]
    rows = []
    for claim in claims:
        replacement = claim.replacement_unit.display_identifier if claim.replacement_unit_id else "—"
        rows.append({
            "cells": [
                _cell(claim.claim_date, "date"), _cell(claim.claim_no), _cell(claim.unit.variant.product.name),
                _cell(claim.unit.variant.sku), _cell(claim.unit.display_identifier), _cell(claim.customer_name or "—"),
                _cell(claim.get_status_display()), _cell("Yes" if claim.within_unit_warranty else "No"),
                _cell(claim.issue), _date_cell(claim.resolved_at), _cell(replacement),
            ],
            "csv": [
                claim.claim_date.isoformat(), claim.claim_no, claim.unit.variant.product.name, claim.unit.variant.sku,
                claim.unit.display_identifier, claim.customer_name, claim.get_status_display(),
                "Yes" if claim.within_unit_warranty else "No", claim.issue,
                claim.resolved_at.isoformat() if claim.resolved_at else "", replacement if replacement != "—" else "",
            ],
        })

    active_statuses = {WarrantyClaim.Status.OPEN, WarrantyClaim.Status.IN_SERVICE}
    kpis = [
        {"label": "Claims", "value": len(claims), "kind": "number"},
        {"label": "Open / In Service", "value": sum(row.status in active_statuses for row in claims), "kind": "number"},
        {"label": "Resolved", "value": sum(row.status == WarrantyClaim.Status.RESOLVED for row in claims), "kind": "number"},
        {"label": "Replaced", "value": sum(row.status == WarrantyClaim.Status.REPLACED for row in claims), "kind": "number"},
        {"label": "Within Warranty", "value": sum(row.within_unit_warranty for row in claims), "kind": "number"},
    ]
    warehouse_choices = [("", "All"), *[(str(row.pk), row.name) for row in Warehouse.objects.order_by("name", "code")]]
    extra_filters = [
        _filter("warranty_status", "Status", filters["warranty_status"], _choices(WarrantyClaim.Status.choices)),
        _filter("warehouse", "Current Warehouse", filters["warehouse"], warehouse_choices),
    ]
    return columns, rows, kpis, extra_filters, "Claim Range", "No warranty claims found for this filter."


def _serial_report(filters):
    qs = SerializedUnit.objects.filter(
        created_at__date__range=(filters["date_from"], filters["date_to"])
    ).select_related("variant__product", "warehouse")
    if filters["serial_status"]:
        qs = qs.filter(status=filters["serial_status"])
    if filters["warehouse"]:
        qs = qs.filter(warehouse_id=filters["warehouse"])
    units = list(qs.order_by("-created_at", "-id"))

    columns = ["Registered", "Product", "SKU", "Serial", "IMEI 1", "IMEI 2", "Warehouse", "Status", "Purchase Ref", "Sales Ref", "Warranty End"]
    rows = []
    for unit in units:
        registered = timezone.localtime(unit.created_at).date()
        rows.append({
            "cells": [
                _cell(registered, "date"), _cell(unit.variant.product.name), _cell(unit.variant.sku),
                _cell(unit.serial_number or "—"), _cell(unit.imei1 or "—"), _cell(unit.imei2 or "—"),
                _cell(unit.warehouse.name), _cell(unit.get_status_display()), _cell(unit.purchase_reference or "—"),
                _cell(unit.sales_reference or "—"), _date_cell(unit.warranty_end_date),
            ],
            "csv": [
                registered.isoformat(), unit.variant.product.name, unit.variant.sku, unit.serial_number or "",
                unit.imei1 or "", unit.imei2 or "", unit.warehouse.name, unit.get_status_display(),
                unit.purchase_reference, unit.sales_reference,
                unit.warranty_end_date.isoformat() if unit.warranty_end_date else "",
            ],
        })

    kpis = [
        {"label": "Serialized Units", "value": len(units), "kind": "number"},
        {"label": "Available", "value": sum(row.status == SerializedUnit.Status.AVAILABLE for row in units), "kind": "number"},
        {"label": "Sold", "value": sum(row.status == SerializedUnit.Status.SOLD for row in units), "kind": "number"},
        {"label": "Warranty Service", "value": sum(row.status == SerializedUnit.Status.WARRANTY_SERVICE for row in units), "kind": "number"},
        {"label": "Active Warranty", "value": sum(row.warranty_is_active for row in units), "kind": "number"},
    ]
    warehouse_choices = [("", "All"), *[(str(row.pk), row.name) for row in Warehouse.objects.order_by("name", "code")]]
    extra_filters = [
        _filter("serial_status", "Status", filters["serial_status"], _choices(SerializedUnit.Status.choices)),
        _filter("warehouse", "Warehouse", filters["warehouse"], warehouse_choices),
    ]
    return columns, rows, kpis, extra_filters, "Registered Range", "No Serial/IMEI units found for this registration range."


def build_after_sales_report(params):
    filters = parse_after_sales_filters(params)
    report_key = filters["report"]

    if report_key == "payment":
        columns, rows, kpis, extra_filters, date_scope_label, empty_message = _payment_report(filters)
    elif report_key == "expense":
        columns, rows, kpis, extra_filters, date_scope_label, empty_message = _expense_report(filters)
    elif report_key == "returns":
        columns, rows, kpis, extra_filters, date_scope_label, empty_message = _returns_report(filters)
    elif report_key == "warranty":
        columns, rows, kpis, extra_filters, date_scope_label, empty_message = _warranty_report(filters)
    else:
        columns, rows, kpis, extra_filters, date_scope_label, empty_message = _serial_report(filters)

    title, description = AFTER_SALES_META[report_key]
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
        "extra_filters": extra_filters,
        "show_channel_filter": False,
        "show_warehouse_filter": False,
        "show_movement_filter": False,
        "date_scope_label": date_scope_label,
        "empty_message": empty_message,
    }
