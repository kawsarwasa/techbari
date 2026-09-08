from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Prefetch, Sum
from django.utils import timezone

from accounting.models import JournalEntry, JournalLine
from accounting.services import SYSTEM_ACCOUNTS, sales_order_cogs, variant_weighted_cost
from returns.models import SalesReturn, SalesReturnItem
from sales.models import SalesOrder, SalesOrderItem

ZERO = Decimal("0.00")
MONEY = Decimal("0.01")

REPORT_TABS = [
    ("sales", "Sales"),
    ("daily", "Daily"),
    ("monthly", "Monthly"),
    ("channel", "POS vs Online"),
    ("product", "Product"),
    ("category", "Category"),
    ("brand", "Brand"),
    ("profit", "Profit"),
    ("cogs", "COGS"),
]

REPORT_META = {
    "sales": ("Sales Report", "Completed sales with return-aware net sales, COGS and gross profit."),
    "daily": ("Daily Sales", "Completed sales grouped by original order date."),
    "monthly": ("Monthly Sales", "Completed sales grouped by month."),
    "channel": ("POS vs Online Sales", "Compare Online Store, POS and Manual sales channels."),
    "product": ("Product Sales", "Product-level sales, net units, allocated COGS and gross profit. Shipping revenue is excluded."),
    "category": ("Category Sales", "Category-level product sales and profitability using the product's current catalog classification."),
    "brand": ("Brand Sales", "Brand-level product sales and profitability using the product's current catalog classification."),
    "profit": ("Profit Report", "Order-level gross profit after completed return credits and restocked COGS reversals."),
    "cogs": ("COGS Report", "Original sale COGS, returned/restocked COGS and net COGS by completed order."),
}


def _money(value):
    return Decimal(value or ZERO).quantize(MONEY, rounding=ROUND_HALF_UP)


def _percent(numerator, denominator):
    numerator = Decimal(numerator or ZERO)
    denominator = Decimal(denominator or ZERO)
    if denominator <= ZERO:
        return Decimal("0.00")
    return ((numerator / denominator) * Decimal("100")).quantize(Decimal("0.01"))


def _parse_date(value):
    value = str(value or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def parse_filters(params):
    today = timezone.localdate()
    start_date = _parse_date(params.get("date_from")) or today.replace(day=1)
    end_date = _parse_date(params.get("date_to")) or today
    if end_date < start_date:
        start_date, end_date = end_date, start_date

    channel = str(params.get("channel") or "").strip().lower()
    if channel not in set(SalesOrder.Channel.values):
        channel = ""

    report_key = str(params.get("report") or "sales").strip().lower()
    if report_key not in REPORT_META:
        report_key = "sales"

    return {"date_from": start_date, "date_to": end_date, "channel": channel, "report": report_key}


def _orders_for(filters):
    item_qs = SalesOrderItem.objects.select_related(
        "variant__product__category",
        "variant__product__brand",
    )
    qs = (
        SalesOrder.objects.filter(
            status=SalesOrder.Status.COMPLETED,
            order_date__range=(filters["date_from"], filters["date_to"]),
        )
        .select_related("customer", "warehouse")
        .prefetch_related(Prefetch("items", queryset=item_qs))
        .order_by("order_date", "id")
    )
    if filters["channel"]:
        qs = qs.filter(channel=filters["channel"])
    return list(qs)


def _line_totals_by_reference(*, references, source_type):
    references = [value for value in references if value]
    if not references:
        return {}
    rows = (
        JournalLine.objects.filter(
            account__code=SYSTEM_ACCOUNTS["cogs"],
            entry__status=JournalEntry.Status.POSTED,
            entry__source_type=source_type,
            entry__source_reference__in=references,
        )
        .values("entry__source_reference")
        .annotate(debit_total=Sum("debit"), credit_total=Sum("credit"))
    )
    return {
        row["entry__source_reference"]: _money((row["debit_total"] or ZERO) - (row["credit_total"] or ZERO))
        for row in rows
    }


def _return_context(order_ids):
    if not order_ids:
        return {}, {}
    completed_returns = list(
        SalesReturn.objects.filter(status=SalesReturn.Status.COMPLETED, order_id__in=order_ids)
        .select_related("order")
        .order_by("completed_date", "id")
    )
    return_cogs = _line_totals_by_reference(
        references=[row.return_no for row in completed_returns],
        source_type=JournalEntry.SourceType.SALE_RETURN,
    )
    returned_cogs_by_order = defaultdict(lambda: ZERO)
    for row in completed_returns:
        returned_cogs_by_order[row.order_id] += abs(return_cogs.get(row.return_no, ZERO))

    item_rows = (
        SalesReturnItem.objects.filter(
            sales_return__status=SalesReturn.Status.COMPLETED,
            sales_return__order_id__in=order_ids,
        )
        .values("order_item_id")
        .annotate(
            refund_total=Sum("refund_amount"),
            return_qty=Sum("quantity"),
            restocked_qty=Sum("restocked_quantity"),
        )
    )
    by_item = {
        row["order_item_id"]: {
            "refund": _money(row["refund_total"] or ZERO),
            "return_qty": int(row["return_qty"] or 0),
            "restocked_qty": int(row["restocked_qty"] or 0),
        }
        for row in item_rows
    }
    return dict(returned_cogs_by_order), by_item


def _order_metrics(orders):
    if not orders:
        return []
    sale_cogs = _line_totals_by_reference(
        references=[order.order_number for order in orders],
        source_type=JournalEntry.SourceType.SALE,
    )
    returned_cogs_by_order, return_by_item = _return_context([order.pk for order in orders])

    result = []
    for order in orders:
        original_cogs = sale_cogs.get(order.order_number)
        if original_cogs is None:
            original_cogs = _money(sales_order_cogs(order))
        returned_cogs = _money(returned_cogs_by_order.get(order.pk, ZERO))
        net_cogs = max(_money(original_cogs - returned_cogs), ZERO)
        gross_sales = _money(order.grand_total)
        return_credit = _money(order.return_credit_amount)
        net_sales = max(_money(gross_sales - return_credit), ZERO)
        profit = _money(net_sales - net_cogs)
        issued_units = sum(int(item.issued_quantity or 0) for item in order.items.all())
        returned_units = sum(
            int(return_by_item.get(item.pk, {}).get("return_qty", 0)) for item in order.items.all()
        )
        result.append({
            "order": order,
            "gross_sales": gross_sales,
            "return_credit": return_credit,
            "net_sales": net_sales,
            "original_cogs": _money(original_cogs),
            "returned_cogs": returned_cogs,
            "cogs": net_cogs,
            "profit": profit,
            "margin": _percent(profit, net_sales),
            "units": max(issued_units - returned_units, 0),
            "return_by_item": return_by_item,
        })
    return result


def _summary(metrics):
    net_sales = _money(sum((row["net_sales"] for row in metrics), ZERO))
    cogs = _money(sum((row["cogs"] for row in metrics), ZERO))
    profit = _money(sum((row["profit"] for row in metrics), ZERO))
    return {
        "orders": len(metrics),
        "units": sum(row["units"] for row in metrics),
        "net_sales": net_sales,
        "cogs": cogs,
        "profit": profit,
        "margin": _percent(profit, net_sales),
    }


def _allocate(total, weighted_keys):
    total = _money(total)
    if not weighted_keys:
        return {}
    weights = [max(Decimal(weight or ZERO), ZERO) for _, weight in weighted_keys]
    weight_total = sum(weights, ZERO)
    if weight_total <= ZERO:
        weights = [Decimal("1") for _ in weighted_keys]
        weight_total = Decimal(len(weighted_keys))
    result = {}
    allocated = ZERO
    for index, ((key, _), weight) in enumerate(zip(weighted_keys, weights)):
        if index == len(weighted_keys) - 1:
            amount = _money(total - allocated)
        else:
            amount = _money(total * weight / weight_total)
            allocated += amount
        result[key] = amount
    return result


def _group_order_metrics(metrics, key_func, label_func, *, sort_key=None):
    groups = {}
    for row in metrics:
        key = key_func(row)
        if key not in groups:
            groups[key] = {"label": label_func(row), "orders": 0, "units": 0, "net_sales": ZERO, "cogs": ZERO, "profit": ZERO}
        target = groups[key]
        target["orders"] += 1
        target["units"] += row["units"]
        target["net_sales"] += row["net_sales"]
        target["cogs"] += row["cogs"]
        target["profit"] += row["profit"]
    result = []
    for key, row in groups.items():
        row["net_sales"] = _money(row["net_sales"])
        row["cogs"] = _money(row["cogs"])
        row["profit"] = _money(row["profit"])
        row["margin"] = _percent(row["profit"], row["net_sales"])
        row["_key"] = key
        result.append(row)
    result.sort(key=sort_key or (lambda row: row["_key"]))
    return result


def _product_breakdown(metrics):
    groups = {}
    cost_cache = {}
    for metric in metrics:
        order = metric["order"]
        items = list(order.items.all())
        if not items:
            continue
        line_weights = [(item.pk, _money(item.line_total)) for item in items]
        order_discount_alloc = _allocate(order.discount_amount, line_weights)
        known_refunds = {
            item.pk: _money(metric["return_by_item"].get(item.pk, {}).get("refund", ZERO)) for item in items
        }
        known_refund_total = _money(sum(known_refunds.values(), ZERO))
        return_remainder = max(_money(metric["return_credit"] - known_refund_total), ZERO)
        return_remainder_alloc = _allocate(return_remainder, line_weights)

        item_net_sales = {}
        estimated_cost_weights = []
        for item in items:
            item_net_sales[item.pk] = max(
                _money(
                    item.line_total
                    - order_discount_alloc.get(item.pk, ZERO)
                    - known_refunds.get(item.pk, ZERO)
                    - return_remainder_alloc.get(item.pk, ZERO)
                ),
                ZERO,
            )
            cache_key = (item.variant_id, order.order_date)
            if cache_key not in cost_cache:
                cost_cache[cache_key] = variant_weighted_cost(item.variant_id, as_of=order.order_date)
            return_info = metric["return_by_item"].get(item.pk, {})
            sold_qty = Decimal(item.issued_quantity or 0)
            restocked_qty = Decimal(return_info.get("restocked_qty", 0))
            estimated_cost = max(_money(cost_cache[cache_key] * max(sold_qty - restocked_qty, ZERO)), ZERO)
            estimated_cost_weights.append((item.pk, estimated_cost))

        if sum((weight for _, weight in estimated_cost_weights), ZERO) <= ZERO:
            estimated_cost_weights = [(item.pk, item_net_sales[item.pk]) for item in items]
        cogs_alloc = _allocate(metric["cogs"], estimated_cost_weights)

        for item in items:
            product = item.variant.product
            return_info = metric["return_by_item"].get(item.pk, {})
            net_units = max(int(item.issued_quantity or 0) - int(return_info.get("return_qty", 0)), 0)
            target = groups.setdefault(product.pk, {
                "product_id": product.pk,
                "product_name": item.product_snapshot or product.name,
                "category_id": product.category_id,
                "category_name": product.category.name,
                "brand_id": product.brand_id,
                "brand_name": product.brand.name,
                "units": 0,
                "net_sales": ZERO,
                "cogs": ZERO,
            })
            target["units"] += net_units
            target["net_sales"] += item_net_sales[item.pk]
            target["cogs"] += cogs_alloc.get(item.pk, ZERO)

    result = []
    for row in groups.values():
        row["net_sales"] = _money(row["net_sales"])
        row["cogs"] = _money(row["cogs"])
        row["profit"] = _money(row["net_sales"] - row["cogs"])
        row["margin"] = _percent(row["profit"], row["net_sales"])
        result.append(row)
    result.sort(key=lambda row: (-row["net_sales"], row["product_name"].lower()))
    return result


def _rollup_products(product_rows, group_key, group_label):
    groups = {}
    for row in product_rows:
        target = groups.setdefault(row[group_key], {"label": row[group_label], "units": 0, "net_sales": ZERO, "cogs": ZERO})
        target["units"] += row["units"]
        target["net_sales"] += row["net_sales"]
        target["cogs"] += row["cogs"]
    result = []
    for row in groups.values():
        row["net_sales"] = _money(row["net_sales"])
        row["cogs"] = _money(row["cogs"])
        row["profit"] = _money(row["net_sales"] - row["cogs"])
        row["margin"] = _percent(row["profit"], row["net_sales"])
        result.append(row)
    result.sort(key=lambda row: (-row["net_sales"], row["label"].lower()))
    return result


def _cell(value, kind="text"):
    return {"value": value, "kind": kind}


def _standard_group_rows(grouped):
    return [{
        "cells": [
            _cell(row["label"]), _cell(row.get("orders", 0), "number"), _cell(row["units"], "number"),
            _cell(row["net_sales"], "money"), _cell(row["cogs"], "money"), _cell(row["profit"], "money"), _cell(row["margin"], "percent"),
        ],
        "csv": [row["label"], row.get("orders", 0), row["units"], row["net_sales"], row["cogs"], row["profit"], row["margin"]],
    } for row in grouped]


def _table_for(report_key, metrics):
    if report_key in {"sales", "profit", "cogs"}:
        if report_key == "cogs":
            columns = ["Order", "Date", "Channel", "Original COGS", "Returned COGS", "Net COGS"]
            rows = [{
                "cells": [_cell(row["order"].order_number), _cell(row["order"].order_date, "date"), _cell(row["order"].get_channel_display()), _cell(row["original_cogs"], "money"), _cell(row["returned_cogs"], "money"), _cell(row["cogs"], "money")],
                "csv": [row["order"].order_number, row["order"].order_date.isoformat(), row["order"].get_channel_display(), row["original_cogs"], row["returned_cogs"], row["cogs"]],
            } for row in reversed(metrics)]
            return columns, rows

        columns = ["Order", "Date", "Channel", "Units", "Net Sales"]
        if report_key == "sales":
            columns.append("Return Credit")
        columns += ["COGS", "Gross Profit", "Margin"]
        rows = []
        for row in reversed(metrics):
            cells = [_cell(row["order"].order_number), _cell(row["order"].order_date, "date"), _cell(row["order"].get_channel_display()), _cell(row["units"], "number"), _cell(row["net_sales"], "money")]
            csv = [row["order"].order_number, row["order"].order_date.isoformat(), row["order"].get_channel_display(), row["units"], row["net_sales"]]
            if report_key == "sales":
                cells.append(_cell(row["return_credit"], "money"))
                csv.append(row["return_credit"])
            cells += [_cell(row["cogs"], "money"), _cell(row["profit"], "money"), _cell(row["margin"], "percent")]
            csv += [row["cogs"], row["profit"], row["margin"]]
            rows.append({"cells": cells, "csv": csv})
        return columns, rows

    if report_key == "daily":
        grouped = _group_order_metrics(metrics, lambda row: row["order"].order_date, lambda row: row["order"].order_date)
        columns = ["Date", "Orders", "Units", "Net Sales", "COGS", "Gross Profit", "Margin"]
        rows = []
        for row in grouped:
            rows.append({
                "cells": [_cell(row["label"], "date"), _cell(row["orders"], "number"), _cell(row["units"], "number"), _cell(row["net_sales"], "money"), _cell(row["cogs"], "money"), _cell(row["profit"], "money"), _cell(row["margin"], "percent")],
                "csv": [row["label"].isoformat(), row["orders"], row["units"], row["net_sales"], row["cogs"], row["profit"], row["margin"]],
            })
        return columns, rows

    if report_key == "monthly":
        grouped = _group_order_metrics(metrics, lambda row: row["order"].order_date.replace(day=1), lambda row: row["order"].order_date.replace(day=1))
        columns = ["Month", "Orders", "Units", "Net Sales", "COGS", "Gross Profit", "Margin"]
        rows = []
        for row in grouped:
            rows.append({
                "cells": [_cell(row["label"].strftime("%b %Y")), _cell(row["orders"], "number"), _cell(row["units"], "number"), _cell(row["net_sales"], "money"), _cell(row["cogs"], "money"), _cell(row["profit"], "money"), _cell(row["margin"], "percent")],
                "csv": [row["label"].strftime("%Y-%m"), row["orders"], row["units"], row["net_sales"], row["cogs"], row["profit"], row["margin"]],
            })
        return columns, rows

    if report_key == "channel":
        labels = dict(SalesOrder.Channel.choices)
        grouped = _group_order_metrics(metrics, lambda row: row["order"].channel, lambda row: labels.get(row["order"].channel, row["order"].channel.title()), sort_key=lambda row: (-row["net_sales"], row["label"]))
        columns = ["Channel", "Orders", "Units", "Net Sales", "COGS", "Gross Profit", "Margin"]
        return columns, _standard_group_rows(grouped)

    product_rows = _product_breakdown(metrics)
    if report_key == "product":
        columns = ["Product", "Units", "Net Product Sales", "COGS", "Gross Profit", "Margin"]
        rows = [{
            "cells": [_cell(row["product_name"]), _cell(row["units"], "number"), _cell(row["net_sales"], "money"), _cell(row["cogs"], "money"), _cell(row["profit"], "money"), _cell(row["margin"], "percent")],
            "csv": [row["product_name"], row["units"], row["net_sales"], row["cogs"], row["profit"], row["margin"]],
        } for row in product_rows]
        return columns, rows

    if report_key == "category":
        grouped = _rollup_products(product_rows, "category_id", "category_name")
        columns = ["Category", "Units", "Net Product Sales", "COGS", "Gross Profit", "Margin"]
    else:
        grouped = _rollup_products(product_rows, "brand_id", "brand_name")
        columns = ["Brand", "Units", "Net Product Sales", "COGS", "Gross Profit", "Margin"]
    rows = [{
        "cells": [_cell(row["label"]), _cell(row["units"], "number"), _cell(row["net_sales"], "money"), _cell(row["cogs"], "money"), _cell(row["profit"], "money"), _cell(row["margin"], "percent")],
        "csv": [row["label"], row["units"], row["net_sales"], row["cogs"], row["profit"], row["margin"]],
    } for row in grouped]
    return columns, rows


def build_sales_profit_report(params):
    filters = parse_filters(params)
    metrics = _order_metrics(_orders_for(filters))
    summary = _summary(metrics)
    columns, rows = _table_for(filters["report"], metrics)
    title, description = REPORT_META[filters["report"]]
    return {
        "filters": filters,
        "report_key": filters["report"],
        "report_title": title,
        "report_description": description,
        "tabs": [{"key": key, "label": label} for key, label in REPORT_TABS],
        "kpis": [
            {"label": "Completed Orders", "value": summary["orders"], "kind": "number"},
            {"label": "Net Sales", "value": summary["net_sales"], "kind": "money"},
            {"label": "COGS", "value": summary["cogs"], "kind": "money"},
            {"label": "Gross Profit", "value": summary["profit"], "kind": "money"},
            {"label": "Gross Margin", "value": summary["margin"], "kind": "percent"},
        ],
        "columns": columns,
        "rows": rows,
        "csv_headers": columns,
        "csv_rows": [row["csv"] for row in rows],
        "summary": summary,
        "channel_choices": [("", "All Channels"), *SalesOrder.Channel.choices],
    }
