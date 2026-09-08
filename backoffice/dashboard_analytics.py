from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Prefetch, Sum
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from customers.models import Customer
from expenses.models import Expense
from inventory.models import InventoryBalance
from payments.models import PaymentTransaction
from purchasing.models import PurchaseOrder, PurchasePayment, PurchaseReturn, Supplier
from reports.analytics import build_dashboard_sales_analytics
from returns.models import SalesReturn
from sales.models import SalesOrder

from .context import page_context

ZERO = Decimal("0.00")


def _money(value):
    return Decimal(value or ZERO).quantize(Decimal("0.01"))


def _parse_date(value):
    try:
        return date.fromisoformat(str(value or ""))
    except ValueError:
        return None


def parse_dashboard_period(params):
    today = timezone.localdate()
    period = str(params.get("period") or "30d").strip().lower()
    if period == "today":
        start = end = today
        label = "Today"
    elif period == "7d":
        start, end, label = today - timedelta(days=6), today, "Last 7 Days"
    elif period == "month":
        start, end, label = today.replace(day=1), today, "This Month"
    elif period == "custom":
        start = _parse_date(params.get("date_from")) or today - timedelta(days=29)
        end = _parse_date(params.get("date_to")) or today
        if end < start:
            start, end = end, start
        label = f"{start:%d %b %Y} – {end:%d %b %Y}"
    else:
        period = "30d"
        start, end, label = today - timedelta(days=29), today, "Last 30 Days"
    return {"key": period, "date_from": start, "date_to": end, "label": label}


def _customer_due():
    opening = Customer.objects.aggregate(total=Sum("opening_due"))["total"] or ZERO
    orders = SalesOrder.objects.exclude(status__in=[SalesOrder.Status.DRAFT, SalesOrder.Status.CANCELLED]).values(
        "grand_total", "return_credit_amount", "amount_paid"
    )
    due = _money(opening)
    for row in orders:
        outstanding = _money(row["grand_total"]) - _money(row["return_credit_amount"]) - _money(row["amount_paid"])
        due += max(outstanding, ZERO)
    return _money(due)


def _purchase_due():
    opening = Supplier.objects.aggregate(total=Sum("opening_balance"))["total"] or ZERO
    returns_qs = PurchaseReturn.objects.prefetch_related("items")
    purchases = (
        PurchaseOrder.objects.exclude(status__in=[PurchaseOrder.Status.DRAFT, PurchaseOrder.Status.CANCELLED])
        .prefetch_related("items", "payments", Prefetch("returns", queryset=returns_qs))
    )
    due = _money(opening)
    for purchase in purchases:
        due += _money(purchase.outstanding_amount)
    return _money(due)


def _stock_snapshot():
    balances = list(
        InventoryBalance.objects.select_related("warehouse", "variant__product").all()
    )
    alerts = []
    out_of_stock = 0
    for balance in balances:
        available = balance.available_quantity
        if available == 0:
            out_of_stock += 1
        if available <= balance.low_stock_threshold:
            alerts.append({
                "product": balance.variant.product.name,
                "sku": balance.variant.sku,
                "warehouse": balance.warehouse.name,
                "available": available,
                "threshold": balance.low_stock_threshold,
                "severity": "Out of stock" if available == 0 else "Low stock",
            })
    alerts.sort(key=lambda row: (row["available"], row["product"].lower(), row["sku"]))
    return {"count": len(alerts), "out_of_stock": out_of_stock, "rows": alerts[:8]}


def _with_bars(rows, value_key="net_sales"):
    rows = [dict(row) for row in rows]
    maximum = max((_money(row.get(value_key)) for row in rows), default=ZERO)
    for row in rows:
        value = _money(row.get(value_key))
        row["bar_percent"] = int((value / maximum) * 100) if maximum > ZERO else 0
    return rows


def _sales_trend(rows):
    rows = list(rows)[-31:]
    maximum = max((_money(row["net_sales"]) for row in rows), default=ZERO)
    result = []
    for row in rows:
        result.append({
            **row,
            "bar_percent": int((_money(row["net_sales"]) / maximum) * 100) if maximum > ZERO else 0,
        })
    return result


def _channel_rows(rows, total_sales):
    result = []
    for row in rows:
        value = _money(row["net_sales"])
        result.append({
            **row,
            "share": ((value / total_sales) * Decimal("100")).quantize(Decimal("0.1")) if total_sales > ZERO else Decimal("0.0"),
        })
    return result


def _order_status(period):
    qs = SalesOrder.objects.filter(order_date__range=(period["date_from"], period["date_to"])).exclude(status=SalesOrder.Status.DRAFT)
    counts = {value: 0 for value, _ in SalesOrder.Status.choices if value != SalesOrder.Status.DRAFT}
    for status in qs.values_list("status", flat=True):
        counts[status] = counts.get(status, 0) + 1
    labels = dict(SalesOrder.Status.choices)
    return [{"key": key, "label": labels.get(key, key.title()), "count": count} for key, count in counts.items()]


def _recent_orders():
    rows = SalesOrder.objects.select_related("customer").prefetch_related("items").exclude(status=SalesOrder.Status.DRAFT).order_by("-created_at", "-id")[:8]
    return [{
        "id": order.pk,
        "order_no": order.order_number,
        "customer": order.customer_name,
        "items": order.item_count,
        "amount": order.payable_total,
        "status": order.get_status_display(),
        "channel": order.get_channel_display(),
        "date": order.order_date,
    } for order in rows]


def _recent_activity():
    activity = []
    for order in SalesOrder.objects.exclude(status=SalesOrder.Status.DRAFT).order_by("-created_at")[:8]:
        activity.append({"at": order.created_at, "type": "Order", "title": f"{order.order_number} · {order.get_status_display()}", "detail": f"{order.customer_name} · ৳ {order.payable_total:,.2f}", "url": reverse("backoffice:order_detail") + f"?id={order.pk}"})
    for payment in PaymentTransaction.objects.select_related("sales_order", "purchase_payment__supplier").order_by("-created_at")[:8]:
        activity.append({"at": payment.created_at, "type": "Payment", "title": f"{payment.transaction_no} · {payment.get_kind_display()}", "detail": f"{payment.get_direction_display()} · ৳ {payment.amount:,.2f}", "url": reverse("backoffice:payments")})
    for purchase in PurchaseOrder.objects.select_related("supplier").order_by("-created_at")[:6]:
        activity.append({"at": purchase.created_at, "type": "Purchase", "title": f"{purchase.po_number} · {purchase.get_status_display()}", "detail": purchase.supplier.name, "url": reverse("backoffice:purchases")})
    for expense in Expense.objects.select_related("category").order_by("-created_at")[:6]:
        activity.append({"at": expense.created_at, "type": "Expense", "title": f"{expense.expense_no} · {expense.get_status_display()}", "detail": f"{expense.category.name} · ৳ {expense.amount:,.2f}", "url": reverse("backoffice:expenses")})
    for sale_return in SalesReturn.objects.select_related("order").order_by("-created_at")[:6]:
        activity.append({"at": sale_return.created_at, "type": "Return", "title": f"{sale_return.return_no} · {sale_return.get_status_display()}", "detail": sale_return.order.order_number, "url": reverse("backoffice:returns")})
    activity.sort(key=lambda row: row["at"], reverse=True)
    return activity[:14]


def build_dashboard_context(request):
    period = parse_dashboard_period(request.GET)
    today = timezone.localdate()
    today_sales = build_dashboard_sales_analytics(today, today)
    selected = build_dashboard_sales_analytics(period["date_from"], period["date_to"])
    stock = _stock_snapshot()
    purchase_due = _purchase_due()
    customer_due = _customer_due()
    today_orders = SalesOrder.objects.filter(order_date=today).exclude(status=SalesOrder.Status.DRAFT).count()

    selected_sales = _money(selected["summary"]["net_sales"])
    statistics = [
        {"label": "Today Sales", "value": f"৳ {today_sales['summary']['net_sales']:,.2f}", "trend": f"{today_sales['summary']['orders']} completed", "trend_class": "up", "note": "return-aware net sales", "icon": "backoffice/components/icons/icon_1.html", "color": "blue"},
        {"label": "Today Orders", "value": str(today_orders), "trend": "Live", "trend_class": "up", "note": "all placed orders", "icon": "backoffice/components/icons/icon_2.html", "color": "green"},
        {"label": "Today Profit", "value": f"৳ {today_sales['summary']['profit']:,.2f}", "trend": f"{today_sales['summary']['margin']}%", "trend_class": "up", "note": "Reports gross-profit logic", "icon": "backoffice/components/icons/icon_3.html", "color": "purple"},
        {"label": "Stock Alerts", "value": str(stock["count"]), "trend": f"{stock['out_of_stock']} out", "trend_class": "down" if stock["count"] else "up", "note": "low/out of stock SKUs", "icon": "backoffice/components/icons/icon_4.html", "color": "red"},
        {"label": "Purchase Due", "value": f"৳ {purchase_due:,.2f}", "trend": "Supplier payable", "trend_class": "down" if purchase_due else "up", "note": "including opening balances", "icon": "backoffice/components/icons/icon_5.html", "color": "orange"},
        {"label": "Customer Due", "value": f"৳ {customer_due:,.2f}", "trend": "Receivable", "trend_class": "up", "note": "CRM outstanding rule", "icon": "backoffice/components/icons/icon_6.html", "color": "blue"},
    ]

    context = page_context("dashboard")
    context.update(
        analytics_database=True,
        statistics=statistics,
        dashboard_period=period,
        dashboard_summary=selected["summary"],
        sales_trend=_sales_trend(selected["daily"]),
        channel_rows=_channel_rows(selected["channels"], selected_sales),
        top_products=_with_bars(selected["products"][:8]),
        top_categories=_with_bars(selected["categories"][:8]),
        stock_alert_rows=stock["rows"],
        order_status_rows=_order_status(period),
        recent_orders=_recent_orders(),
        recent_activity=_recent_activity(),
        purchase_due=purchase_due,
        customer_due=customer_due,
        today=today,
    )
    return context


def dashboard(request):
    return render(request, "backoffice/pages/dashboard.html", build_dashboard_context(request))
