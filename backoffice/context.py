"""Static view context and a safe JSON bridge for the localStorage demo."""
from copy import deepcopy
from django.templatetags.static import static
from django.urls import reverse
from .mock_data import POS_PRODUCTS, SEEDS, STATISTICS
from .page_registry import PAGES
from .table_config import COLUMNS
from .page_data import FORM_DEFAULTS, FORM_OPTIONS, ORDER_BREAKDOWN, RECENT_ORDERS, REPORTS, TOP_PRODUCTS
from .page_data import ACCOUNT_CHART, ACCOUNT_SUMMARY, CAMPAIGNS, NOTIFICATIONS, ORDER_TIMELINE, STOCK_ALERTS

EDIT_ROUTES = {
    "products": "product_edit", "orders": "order_add", "categories": "category_add",
    "brands": "brand_add", "serials": "serial_add", "customers": "customer_add",
    "purchases": "purchase_add", "suppliers": "supplier_add", "warehouses": "warehouse_add",
    "expenses": "expense_add", "payments": "payment_add", "coupons": "coupon_add",
    "shipping": "shipment_add", "returns": "return_add", "warranty": "warranty_add", "users": "user_add",
}


def page_context(page_name):
    seeds = deepcopy(SEEDS)
    browser_seeds = deepcopy(seeds)
    for records in browser_seeds.values():
        for record in records:
            if record.get("image"):
                record["image"] = static(record["image"])
    routes = {name: reverse("backoffice:" + name) for name in PAGES}
    return {
        **seeds, "statistics": STATISTICS[page_name],
        "form_data": deepcopy(FORM_DEFAULTS.get(page_name, {})),
        "form_options": FORM_OPTIONS.get(page_name, {}),
        "recent_orders": RECENT_ORDERS, "top_products": TOP_PRODUCTS,
        "order_breakdown": ORDER_BREAKDOWN, "reports": REPORTS,
        "account_chart": ACCOUNT_CHART, "account_summary": ACCOUNT_SUMMARY,
        "campaigns": CAMPAIGNS, "notifications": NOTIFICATIONS,
        "order_timeline": ORDER_TIMELINE, "stock_alerts": STOCK_ALERTS,
        "active_section": PAGES[page_name]["section"], "table_columns": COLUMNS,
        "edit_urls": {entity: routes[name] for entity, name in EDIT_ROUTES.items()},
        "money_fields": ("price", "amount", "spent", "total", "purchases", "outstanding", "value", "minimum", "refund", "cod"),
        "routes": routes,
        "admin_data": {
            "seeds": browser_seeds,
            "pos_products": [{**p, "image": static(p["image"])} for p in POS_PRODUCTS],
            "columns": COLUMNS,
            "edit_urls": {entity: routes[name] for entity, name in EDIT_ROUTES.items()},
            "default_image": static("admin/images/baseus-e16.webp"),
            "upload_image": static("admin/images/galaxy-buds.webp"),
        },
    }
