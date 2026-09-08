from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from .context import page_context
from .page_registry import PAGES

CATALOG_PAGE_NAMES = {"products", "product_add", "product_edit", "categories", "category_add", "brands", "brand_add"}
INVENTORY_PAGE_NAMES = {"inventory", "warehouses", "warehouse_add", "stock_adjustment", "stock_transfer"}
SERIAL_PAGE_NAMES = {"serials", "serial_add", "warranty", "warranty_add"}
PURCHASE_PAGE_NAMES = {"suppliers", "supplier_add", "purchases", "purchase_add"}
CUSTOMER_PAGE_NAMES = {"customers", "customer_add", "customer_detail"}
SALES_PAGE_NAMES = {"orders", "order_add", "order_detail"}
MARKETING_PAGE_NAMES = {"marketing", "coupons", "coupon_add"}


def page(request, page_name="dashboard"):
    if page_name not in PAGES: raise Http404("Dashboard page not found")
    if page_name == "dashboard":
        from . import dashboard_analytics; return dashboard_analytics.dashboard(request)
    if page_name == "notifications":
        from . import integration_views; return integration_views.notifications(request)
    if page_name in CATALOG_PAGE_NAMES:
        from . import catalog_views; return getattr(catalog_views, page_name)(request)
    if page_name in INVENTORY_PAGE_NAMES:
        from . import inventory_views; return getattr(inventory_views, page_name)(request)
    if page_name in SERIAL_PAGE_NAMES:
        from . import serial_views; return getattr(serial_views, page_name)(request)
    if page_name in PURCHASE_PAGE_NAMES:
        from . import purchase_views; return getattr(purchase_views, page_name)(request)
    if page_name in CUSTOMER_PAGE_NAMES:
        from . import customer_views; return getattr(customer_views, page_name)(request)
    if page_name in SALES_PAGE_NAMES:
        from . import sales_views; return getattr(sales_views, page_name)(request)
    if page_name in MARKETING_PAGE_NAMES:
        from . import marketing_views; return getattr(marketing_views, page_name)(request)
    return render(request, PAGES[page_name]["template"], page_context(page_name))


def legacy_page(request, page):
    name = "dashboard" if page == "index" else next((name for name, info in PAGES.items() if info["legacy"] == page), None)
    if name is None: raise Http404("Dashboard page not found")
    query = request.META.get("QUERY_STRING", ""); return redirect(reverse("backoffice:" + name) + ("?" + query if query else ""))
