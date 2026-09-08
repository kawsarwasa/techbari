from sales.models import SalesOrder

from .services import (
    _group_order_metrics,
    _order_metrics,
    _orders_for,
    _product_breakdown,
    _rollup_products,
    _summary,
)


def build_dashboard_sales_analytics(date_from, date_to):
    """Return one dashboard snapshot using the exact Sales/Profit report semantics."""
    filters = {"date_from": date_from, "date_to": date_to, "channel": "", "report": "sales"}
    metrics = _order_metrics(_orders_for(filters))
    product_rows = _product_breakdown(metrics)
    category_rows = _rollup_products(product_rows, "category_id", "category_name")
    channel_labels = dict(SalesOrder.Channel.choices)
    channel_rows = _group_order_metrics(
        metrics,
        lambda row: row["order"].channel,
        lambda row: channel_labels.get(row["order"].channel, row["order"].channel.title()),
        sort_key=lambda row: (-row["net_sales"], row["label"]),
    )
    daily_rows = _group_order_metrics(
        metrics,
        lambda row: row["order"].order_date,
        lambda row: row["order"].order_date,
    )
    return {
        "summary": _summary(metrics),
        "daily": daily_rows,
        "channels": channel_rows,
        "products": product_rows,
        "categories": category_rows,
    }
