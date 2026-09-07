from datetime import date

from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse

from .context import page_context
from .page_data import CUSTOMER_HISTORY, RECENT_ORDERS
from .page_registry import PAGES

CATALOG_PAGE_NAMES = {"products", "product_add", "product_edit", "categories", "category_add", "brands", "brand_add"}
INVENTORY_PAGE_NAMES = {"inventory", "warehouses", "warehouse_add", "stock_adjustment", "stock_transfer"}
SERIAL_PAGE_NAMES = {"serials", "serial_add", "warranty", "warranty_add"}
PURCHASE_PAGE_NAMES = {"suppliers", "supplier_add", "purchases", "purchase_add"}


def page(request, page_name="dashboard"):
    if page_name not in PAGES:
        raise Http404("Dashboard page not found")
    if page_name in CATALOG_PAGE_NAMES:
        from . import catalog_views
        return getattr(catalog_views, page_name)(request)
    if page_name in INVENTORY_PAGE_NAMES:
        from . import inventory_views
        return getattr(inventory_views, page_name)(request)
    if page_name in SERIAL_PAGE_NAMES:
        from . import serial_views
        return getattr(serial_views, page_name)(request)
    if page_name in PURCHASE_PAGE_NAMES:
        from . import purchase_views
        return getattr(purchase_views, page_name)(request)
    context = page_context(page_name)
    entity = {"order_detail": "orders", "customer_detail": "customers"}.get(page_name)
    if entity:
        try:
            record_id = int(request.GET.get("id", 1))
        except ValueError:
            raise Http404("Record not found")
        records = context[entity]
        if entity == "orders":
            records = records + [row for row in RECENT_ORDERS if row["id"] not in {r["id"] for r in records}]
        record = next((row for row in records if row["id"] == record_id), None)
        if record is None:
            if request.GET.get("local") != "1":
                raise Http404("Record not found")
            record = dict(records[0])
        if request.GET.get("local") == "1":
            context["admin_data"]["detail"] = {"entity": entity, "id": record_id}
        context["order" if entity == "orders" else "customer"] = record
        if entity == "orders":
            person = next((c for c in context["customers"] if c["name"] == record["customer"]), {})
            record.update(email=person.get("email", ""), phone=person.get("phone", ""))
            if record.get("date"):
                record["date_label"] = date.fromisoformat(record["date"]).strftime("%b %d, %Y")
            record.setdefault("payment", "Cash on Delivery")
            product = next((p for p in context["admin_data"]["pos_products"] if p["name"] == record["items"]), {})
            record.update(
                category=product.get("category", "Electronics"),
                sku=product.get("sku", ""),
                image=product.get("image", context["admin_data"]["default_image"]).removeprefix("/static/"),
            )
            if record_id == 1:
                record.update(
                    email="tanvir.hasan@gmail.com",
                    phone="+880 1712 345678",
                    image="admin/images/airpods-pro2.webp",
                    sku="IPH15-128-BLK",
                )
        else:
            record["customer_no"] = f"CUST{record_id:03d}"
            record["initials"] = "".join(word[0] for word in record["name"].split())
            context["customer_history"] = CUSTOMER_HISTORY.get(
                record_id,
                [
                    {
                        **order,
                        "date_label": date.fromisoformat(order["date"]).strftime("%b %d, %Y"),
                        "linked": True,
                    }
                    for order in context["orders"]
                    if order["customer"] == record["name"]
                ],
            )
    return render(request, PAGES[page_name]["template"], context)


def legacy_page(request, page):
    name = "dashboard" if page == "index" else next(
        (name for name, info in PAGES.items() if info["legacy"] == page),
        None,
    )
    if name is None:
        raise Http404("Dashboard page not found")
    query = request.META.get("QUERY_STRING", "")
    return redirect(reverse("backoffice:" + name) + ("?" + query if query else ""))
