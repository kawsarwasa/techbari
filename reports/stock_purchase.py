from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum
from django.utils import timezone

from accounting.services import variant_weighted_cost
from customers.models import Customer
from inventory.models import InventoryBalance, StockMovement, Warehouse
from payments.models import PaymentTransaction
from purchasing.models import PurchaseOrder, PurchasePayment, PurchaseReturn, Supplier
from returns.models import SalesReturnItem
from sales.models import SalesOrder

ZERO = Decimal("0.00")
MONEY = Decimal("0.01")

OPERATIONAL_REPORT_KEYS = {
    "stock",
    "stock_valuation",
    "low_stock",
    "stock_movement",
    "purchase",
    "supplier_due",
    "customer_due",
}

OPERATIONAL_TABS = [
    ("stock", "Stock"),
    ("stock_valuation", "Valuation"),
    ("low_stock", "Low Stock"),
    ("stock_movement", "Stock Movement"),
    ("purchase", "Purchase"),
    ("supplier_due", "Supplier Due"),
    ("customer_due", "Customer Due"),
]

OPERATIONAL_META = {
    "stock": ("Stock Report", "Warehouse/SKU stock position as of the selected To date."),
    "stock_valuation": ("Stock Valuation", "Warehouse stock value using weighted purchase cost as of the selected To date."),
    "low_stock": ("Low Stock Report", "SKUs whose available quantity is at or below the configured low-stock threshold."),
    "stock_movement": ("Stock Movement Report", "Immutable stock ledger activity for the selected date range."),
    "purchase": ("Purchase Report", "Non-draft purchase orders with receiving, payment, return and outstanding position."),
    "supplier_due": ("Supplier Due Report", "Supplier payable position as of the selected To date, including opening balances."),
    "customer_due": ("Customer Due Report", "Customer receivable position as of the selected To date, including opening dues."),
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


def parse_operational_filters(params):
    today = timezone.localdate()
    start_date = _parse_date(params.get("date_from")) or today.replace(day=1)
    end_date = _parse_date(params.get("date_to")) or today
    if end_date < start_date:
        start_date, end_date = end_date, start_date

    report_key = str(params.get("report") or "stock").strip().lower()
    if report_key not in OPERATIONAL_REPORT_KEYS:
        report_key = "stock"

    warehouse_id = _positive_int(params.get("warehouse"))
    if warehouse_id and not Warehouse.objects.filter(pk=warehouse_id).exists():
        warehouse_id = None

    movement_type = str(params.get("movement_type") or "").strip().lower()
    if movement_type not in set(StockMovement.Type.values):
        movement_type = ""

    return {
        "date_from": start_date,
        "date_to": end_date,
        "report": report_key,
        "warehouse": warehouse_id,
        "movement_type": movement_type,
        "channel": "",
    }


def _cell(value, kind="text"):
    return {"value": value, "kind": kind}


def _historical_stock_rows(filters):
    qs = StockMovement.objects.filter(created_at__date__lte=filters["date_to"]).select_related(
        "warehouse",
        "variant__product__category",
        "variant__product__brand",
    )
    if filters["warehouse"]:
        qs = qs.filter(warehouse_id=filters["warehouse"])
    qs = qs.order_by("warehouse_id", "variant_id", "-created_at", "-id")

    latest = {}
    for movement in qs:
        key = (movement.warehouse_id, movement.variant_id, movement.sku_snapshot)
        if key not in latest:
            latest[key] = movement

    balance_qs = InventoryBalance.objects.select_related("warehouse", "variant__product").all()
    if filters["warehouse"]:
        balance_qs = balance_qs.filter(warehouse_id=filters["warehouse"])
    balance_map = {(row.warehouse_id, row.variant_id): row for row in balance_qs}

    rows = []
    cost_cache = {}
    for movement in latest.values():
        variant = movement.variant
        balance = balance_map.get((movement.warehouse_id, movement.variant_id)) if movement.variant_id else None
        threshold = int(balance.low_stock_threshold) if balance else 0
        on_hand = int(movement.quantity_after or 0)
        reserved = min(int(movement.reserved_after or 0), on_hand)
        available = max(on_hand - reserved, 0)
        unit_cost = ZERO
        product_name = movement.product_snapshot
        sku = movement.sku_snapshot
        if variant:
            product_name = variant.product.name
            sku = variant.sku
            if variant.pk not in cost_cache:
                cost_cache[variant.pk] = variant_weighted_cost(variant.pk, as_of=filters["date_to"])
            unit_cost = _money(cost_cache[variant.pk])
        stock_value = _money(unit_cost * Decimal(on_hand))
        rows.append({
            "warehouse": movement.warehouse,
            "product": product_name,
            "sku": sku,
            "on_hand": on_hand,
            "reserved": reserved,
            "available": available,
            "threshold": threshold,
            "unit_cost": unit_cost,
            "stock_value": stock_value,
        })

    # A current balance should still appear when old/bootstrap data has no movement row.
    if filters["date_to"] >= timezone.localdate():
        represented = {(row["warehouse"].pk, row["sku"]) for row in rows}
        for balance in balance_qs:
            key = (balance.warehouse_id, balance.variant.sku)
            if key in represented:
                continue
            unit_cost = _money(variant_weighted_cost(balance.variant_id, as_of=filters["date_to"]))
            rows.append({
                "warehouse": balance.warehouse,
                "product": balance.variant.product.name,
                "sku": balance.variant.sku,
                "on_hand": int(balance.on_hand),
                "reserved": int(balance.reserved_quantity),
                "available": int(balance.available_quantity),
                "threshold": int(balance.low_stock_threshold),
                "unit_cost": unit_cost,
                "stock_value": _money(unit_cost * Decimal(balance.on_hand)),
            })

    rows.sort(key=lambda row: (row["warehouse"].name.lower(), row["product"].lower(), row["sku"]))
    return rows


def _stock_report(filters, *, low_only=False):
    data = _historical_stock_rows(filters)
    if low_only:
        data = [row for row in data if row["available"] <= row["threshold"]]
    columns = ["Warehouse", "Product", "SKU", "On Hand", "Reserved", "Available", "Low Threshold", "Unit Cost", "Stock Value"]
    rows = [{
        "cells": [
            _cell(row["warehouse"].name), _cell(row["product"]), _cell(row["sku"]),
            _cell(row["on_hand"], "number"), _cell(row["reserved"], "number"),
            _cell(row["available"], "number"), _cell(row["threshold"], "number"),
            _cell(row["unit_cost"], "money"), _cell(row["stock_value"], "money"),
        ],
        "csv": [row["warehouse"].name, row["product"], row["sku"], row["on_hand"], row["reserved"], row["available"], row["threshold"], row["unit_cost"], row["stock_value"]],
    } for row in data]
    total_value = _money(sum((row["stock_value"] for row in data), ZERO))
    return columns, rows, [
        {"label": "SKU Positions", "value": len(data), "kind": "number"},
        {"label": "On Hand", "value": sum(row["on_hand"] for row in data), "kind": "number"},
        {"label": "Reserved", "value": sum(row["reserved"] for row in data), "kind": "number"},
        {"label": "Available", "value": sum(row["available"] for row in data), "kind": "number"},
        {"label": "Stock Value", "value": total_value, "kind": "money"},
    ]


def _valuation_report(filters):
    data = _historical_stock_rows(filters)
    groups = {}
    for row in data:
        target = groups.setdefault(row["warehouse"].pk, {
            "warehouse": row["warehouse"], "skus": 0, "on_hand": 0, "available": 0, "value": ZERO,
        })
        target["skus"] += 1
        target["on_hand"] += row["on_hand"]
        target["available"] += row["available"]
        target["value"] += row["stock_value"]
    grouped = sorted(groups.values(), key=lambda row: row["warehouse"].name.lower())
    columns = ["Warehouse", "SKU Positions", "On Hand", "Available", "Stock Value"]
    rows = [{
        "cells": [_cell(row["warehouse"].name), _cell(row["skus"], "number"), _cell(row["on_hand"], "number"), _cell(row["available"], "number"), _cell(_money(row["value"]), "money")],
        "csv": [row["warehouse"].name, row["skus"], row["on_hand"], row["available"], _money(row["value"])],
    } for row in grouped]
    total_value = _money(sum((row["value"] for row in grouped), ZERO))
    return columns, rows, [
        {"label": "Warehouses", "value": len(grouped), "kind": "number"},
        {"label": "SKU Positions", "value": sum(row["skus"] for row in grouped), "kind": "number"},
        {"label": "On Hand", "value": sum(row["on_hand"] for row in grouped), "kind": "number"},
        {"label": "Available", "value": sum(row["available"] for row in grouped), "kind": "number"},
        {"label": "Inventory Value", "value": total_value, "kind": "money"},
    ]


def _movement_report(filters):
    qs = StockMovement.objects.filter(created_at__date__range=(filters["date_from"], filters["date_to"])).select_related("warehouse")
    if filters["warehouse"]:
        qs = qs.filter(warehouse_id=filters["warehouse"])
    if filters["movement_type"]:
        qs = qs.filter(movement_type=filters["movement_type"])
    qs = qs.order_by("-created_at", "-id")
    data = list(qs)
    columns = ["Date / Time", "Warehouse", "Type", "Product", "SKU", "Qty Δ", "Reserved Δ", "Qty After", "Reference"]
    rows = [{
        "cells": [
            _cell(timezone.localtime(row.created_at).strftime("%d %b %Y %H:%M")), _cell(row.warehouse.name),
            _cell(row.get_movement_type_display()), _cell(row.product_snapshot), _cell(row.sku_snapshot),
            _cell(row.quantity_delta, "number"), _cell(row.reserved_delta, "number"), _cell(row.quantity_after, "number"),
            _cell(row.reference_no or "—"),
        ],
        "csv": [timezone.localtime(row.created_at).isoformat(), row.warehouse.name, row.get_movement_type_display(), row.product_snapshot, row.sku_snapshot, row.quantity_delta, row.reserved_delta, row.quantity_after, row.reference_no],
    } for row in data]
    net_qty = sum(int(row.quantity_delta or 0) for row in data)
    return columns, rows, [
        {"label": "Movements", "value": len(data), "kind": "number"},
        {"label": "Stock In", "value": sum(max(int(row.quantity_delta or 0), 0) for row in data), "kind": "number"},
        {"label": "Stock Out", "value": sum(abs(min(int(row.quantity_delta or 0), 0)) for row in data), "kind": "number"},
        {"label": "Net Quantity", "value": net_qty, "kind": "number"},
        {"label": "Warehouses", "value": len({row.warehouse_id for row in data}), "kind": "number"},
    ]


def _purchase_amount_maps(purchase_ids, end_date):
    paid = defaultdict(lambda: ZERO)
    for row in PurchasePayment.objects.filter(purchase_id__in=purchase_ids, payment_date__lte=end_date):
        paid[row.purchase_id] += _money(row.amount)
    returned = defaultdict(lambda: ZERO)
    for purchase_return in PurchaseReturn.objects.filter(purchase_id__in=purchase_ids, return_date__lte=end_date).prefetch_related("items"):
        returned[purchase_return.purchase_id] += _money(purchase_return.total_amount)
    return paid, returned


def _purchase_report(filters):
    qs = PurchaseOrder.objects.exclude(status__in=[PurchaseOrder.Status.DRAFT, PurchaseOrder.Status.CANCELLED]).filter(
        purchase_date__range=(filters["date_from"], filters["date_to"])
    ).select_related("supplier", "warehouse").prefetch_related("items")
    if filters["warehouse"]:
        qs = qs.filter(warehouse_id=filters["warehouse"])
    purchases = list(qs.order_by("-purchase_date", "-id"))
    paid, returned = _purchase_amount_maps([row.pk for row in purchases], filters["date_to"])
    data = []
    for purchase in purchases:
        grand_total = _money(purchase.grand_total)
        return_total = _money(returned[purchase.pk])
        paid_total = _money(paid[purchase.pk])
        outstanding = max(_money(grand_total - return_total - paid_total), ZERO)
        data.append((purchase, grand_total, return_total, paid_total, outstanding))
    columns = ["PO", "Date", "Supplier", "Warehouse", "Status", "Ordered Qty", "Received Qty", "Grand Total", "Returns", "Paid", "Outstanding"]
    rows = [{
        "cells": [
            _cell(p.po_number), _cell(p.purchase_date, "date"), _cell(p.supplier.name), _cell(p.warehouse.name), _cell(p.get_status_display()),
            _cell(p.ordered_quantity, "number"), _cell(p.received_quantity, "number"), _cell(total, "money"), _cell(ret, "money"), _cell(paid_amt, "money"), _cell(due, "money"),
        ],
        "csv": [p.po_number, p.purchase_date.isoformat(), p.supplier.name, p.warehouse.name, p.get_status_display(), p.ordered_quantity, p.received_quantity, total, ret, paid_amt, due],
    } for p, total, ret, paid_amt, due in data]
    return columns, rows, [
        {"label": "Purchase Orders", "value": len(data), "kind": "number"},
        {"label": "Purchase Value", "value": _money(sum((row[1] for row in data), ZERO)), "kind": "money"},
        {"label": "Returns", "value": _money(sum((row[2] for row in data), ZERO)), "kind": "money"},
        {"label": "Paid", "value": _money(sum((row[3] for row in data), ZERO)), "kind": "money"},
        {"label": "Outstanding", "value": _money(sum((row[4] for row in data), ZERO)), "kind": "money"},
    ]


def _supplier_due_report(filters):
    suppliers = list(Supplier.objects.all().order_by("name", "code"))
    purchase_qs = PurchaseOrder.objects.exclude(status__in=[PurchaseOrder.Status.DRAFT, PurchaseOrder.Status.CANCELLED]).filter(purchase_date__lte=filters["date_to"]).prefetch_related("items")
    if filters["warehouse"]:
        purchase_qs = purchase_qs.filter(warehouse_id=filters["warehouse"])
    purchases = list(purchase_qs)
    purchase_ids = [row.pk for row in purchases]
    paid, returned = _purchase_amount_maps(purchase_ids, filters["date_to"])
    grouped = defaultdict(lambda: {"purchases": ZERO, "returns": ZERO, "paid": ZERO})
    for purchase in purchases:
        grouped[purchase.supplier_id]["purchases"] += _money(purchase.grand_total)
        grouped[purchase.supplier_id]["returns"] += _money(returned[purchase.pk])
        grouped[purchase.supplier_id]["paid"] += _money(paid[purchase.pk])
    data = []
    for supplier in suppliers:
        values = grouped[supplier.pk]
        opening = _money(supplier.opening_balance)
        due = max(_money(opening + values["purchases"] - values["returns"] - values["paid"]), ZERO)
        if due <= ZERO and opening <= ZERO and values["purchases"] <= ZERO:
            continue
        data.append((supplier, opening, _money(values["purchases"]), _money(values["returns"]), _money(values["paid"]), due))
    data.sort(key=lambda row: (-row[5], row[0].name.lower()))
    columns = ["Supplier", "Code", "Opening", "Purchases", "Returns", "Paid", "Due"]
    rows = [{
        "cells": [_cell(s.name), _cell(s.code), _cell(opening, "money"), _cell(total, "money"), _cell(ret, "money"), _cell(paid_amt, "money"), _cell(due, "money")],
        "csv": [s.name, s.code, opening, total, ret, paid_amt, due],
    } for s, opening, total, ret, paid_amt, due in data]
    return columns, rows, [
        {"label": "Suppliers", "value": len(data), "kind": "number"},
        {"label": "Opening Payable", "value": _money(sum((row[1] for row in data), ZERO)), "kind": "money"},
        {"label": "Purchases", "value": _money(sum((row[2] for row in data), ZERO)), "kind": "money"},
        {"label": "Paid / Returns", "value": _money(sum((row[3] + row[4] for row in data), ZERO)), "kind": "money"},
        {"label": "Supplier Due", "value": _money(sum((row[5] for row in data), ZERO)), "kind": "money"},
    ]


def _customer_due_report(filters):
    customers = list(Customer.objects.all().order_by("name", "customer_no"))
    orders = list(SalesOrder.objects.exclude(status__in=[SalesOrder.Status.DRAFT, SalesOrder.Status.CANCELLED]).filter(
        order_date__lte=filters["date_to"], customer__isnull=False
    ).select_related("customer"))
    order_ids = [row.pk for row in orders]

    credits = defaultdict(lambda: ZERO)
    credit_rows = SalesReturnItem.objects.filter(
        sales_return__status="completed",
        sales_return__completed_date__lte=filters["date_to"],
        sales_return__order_id__in=order_ids,
    ).values("sales_return__order_id").annotate(total=Sum("refund_amount"))
    for row in credit_rows:
        credits[row["sales_return__order_id"]] = _money(row["total"])

    net_cash = defaultdict(lambda: ZERO)
    transactions = PaymentTransaction.objects.filter(
        sales_order_id__in=order_ids,
        transaction_date__lte=filters["date_to"],
        status__in=[PaymentTransaction.Status.COMPLETED, PaymentTransaction.Status.REVERSED],
    )
    for transaction in transactions:
        if transaction.direction == PaymentTransaction.Direction.IN:
            net_cash[transaction.sales_order_id] += _money(transaction.amount)
        else:
            net_cash[transaction.sales_order_id] -= _money(transaction.amount)

    grouped = defaultdict(lambda: {"orders": 0, "sales": ZERO, "credits": ZERO, "paid": ZERO, "due": ZERO})
    for order in orders:
        target = grouped[order.customer_id]
        target["orders"] += 1
        target["sales"] += _money(order.grand_total)
        target["credits"] += _money(credits[order.pk])
        target["paid"] += _money(net_cash[order.pk])

    data = []
    for customer in customers:
        values = grouped[customer.pk]
        opening = _money(customer.opening_due)
        due = max(_money(opening + values["sales"] - values["credits"] - values["paid"]), ZERO)
        if due <= ZERO and opening <= ZERO and values["orders"] == 0:
            continue
        data.append((customer, opening, values["orders"], _money(values["sales"]), _money(values["credits"]), _money(values["paid"]), due))
    data.sort(key=lambda row: (-row[6], row[0].name.lower()))
    columns = ["Customer", "Phone", "Opening Due", "Orders", "Sales", "Return Credit", "Net Paid", "Due"]
    rows = [{
        "cells": [_cell(c.name), _cell(c.phone), _cell(opening, "money"), _cell(order_count, "number"), _cell(sales, "money"), _cell(credit, "money"), _cell(paid, "money"), _cell(due, "money")],
        "csv": [c.name, c.phone, opening, order_count, sales, credit, paid, due],
    } for c, opening, order_count, sales, credit, paid, due in data]
    return columns, rows, [
        {"label": "Customers", "value": len(data), "kind": "number"},
        {"label": "Opening Due", "value": _money(sum((row[1] for row in data), ZERO)), "kind": "money"},
        {"label": "Sales", "value": _money(sum((row[3] for row in data), ZERO)), "kind": "money"},
        {"label": "Net Paid / Credits", "value": _money(sum((row[4] + row[5] for row in data), ZERO)), "kind": "money"},
        {"label": "Customer Due", "value": _money(sum((row[6] for row in data), ZERO)), "kind": "money"},
    ]


def build_stock_purchase_report(params):
    filters = parse_operational_filters(params)
    report_key = filters["report"]
    if report_key == "stock":
        columns, rows, kpis = _stock_report(filters)
    elif report_key == "stock_valuation":
        columns, rows, kpis = _valuation_report(filters)
    elif report_key == "low_stock":
        columns, rows, kpis = _stock_report(filters, low_only=True)
    elif report_key == "stock_movement":
        columns, rows, kpis = _movement_report(filters)
    elif report_key == "purchase":
        columns, rows, kpis = _purchase_report(filters)
    elif report_key == "supplier_due":
        columns, rows, kpis = _supplier_due_report(filters)
    else:
        columns, rows, kpis = _customer_due_report(filters)

    title, description = OPERATIONAL_META[report_key]
    return {
        "filters": filters,
        "report_key": report_key,
        "report_title": title,
        "report_description": description,
        "kpis": kpis,
        "columns": columns,
        "rows": rows,
        "csv_headers": columns,
        "csv_rows": [row["csv"] for row in rows],
        "warehouse_choices": [("", "All Warehouses"), *[(str(row.pk), row.name) for row in Warehouse.objects.all().order_by("name")]],
        "movement_choices": [("", "All Movement Types"), *StockMovement.Type.choices],
        "show_channel_filter": False,
        "show_warehouse_filter": report_key in {"stock", "stock_valuation", "low_stock", "stock_movement", "purchase", "supplier_due"},
        "show_movement_filter": report_key == "stock_movement",
        "date_scope_label": "As of" if report_key in {"stock", "stock_valuation", "low_stock", "supplier_due", "customer_due"} else "Range",
        "empty_message": "No data found for this report and filter.",
    }
