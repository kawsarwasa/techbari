from urllib.parse import urlencode

from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_GET

from catalog.models import Product
from customers.models import Customer
from sales.models import SalesOrder


def _can(user, *permissions):
    return user.is_superuser or any(user.has_perm(permission) for permission in permissions)


@require_GET
def global_search(request):
    if not request.user.is_authenticated or not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({"results": [], "error": "Staff authentication required."}, status=403)

    query = (request.GET.get("q") or "").strip()[:120]
    if len(query) < 2:
        return JsonResponse({"query": query, "results": []})

    results = []
    lowered = query.casefold()

    can_view_catalog = _can(request.user, "staff_access.view_catalog", "staff_access.manage_catalog")
    can_manage_catalog = _can(request.user, "staff_access.manage_catalog")
    if can_view_catalog:
        products = (
            Product.objects.select_related("category", "brand")
            .prefetch_related("variants")
            .filter(
                Q(name__icontains=query)
                | Q(public_id__icontains=query)
                | Q(slug__icontains=query)
                | Q(variants__sku__icontains=query)
                | Q(variants__barcode__icontains=query)
            )
            .distinct()
            .order_by("-created_at", "name")[:5]
        )
        for product in products:
            variants = list(product.variants.all())
            matched = next(
                (
                    variant
                    for variant in variants
                    if lowered in (variant.sku or "").casefold()
                    or lowered in (variant.barcode or "").casefold()
                ),
                None,
            )
            variant = matched or next((row for row in variants if row.is_default), variants[0] if variants else None)
            sku = variant.sku if variant else "No SKU"
            meta = f"{sku} · {product.brand.name} · {product.category.name}"
            if can_manage_catalog:
                url = reverse("backoffice:product_edit") + "?" + urlencode({"id": product.pk})
            else:
                url = reverse("backoffice:products") + "?" + urlencode({"q": product.name})
            results.append(
                {
                    "type": "Product",
                    "title": product.name,
                    "meta": meta,
                    "status": product.get_status_display(),
                    "url": url,
                }
            )

    if _can(request.user, "staff_access.view_sales", "staff_access.manage_sales"):
        orders = (
            SalesOrder.objects.select_related("customer")
            .filter(
                Q(order_number__icontains=query)
                | Q(customer__name__icontains=query)
                | Q(customer__phone__icontains=query)
                | Q(shipping_name__icontains=query)
                | Q(shipping_phone__icontains=query)
                | Q(items__sku_snapshot__icontains=query)
                | Q(items__product_snapshot__icontains=query)
            )
            .distinct()
            .order_by("-order_date", "-id")[:5]
        )
        for order in orders:
            results.append(
                {
                    "type": "Order",
                    "title": order.order_number,
                    "meta": f"{order.customer_name} · ৳ {order.grand_total:,.2f}",
                    "status": order.get_status_display(),
                    "url": reverse("backoffice:order_detail_id", args=[order.pk]),
                }
            )

    if _can(request.user, "staff_access.view_customers", "staff_access.manage_customers"):
        customers = (
            Customer.objects.filter(
                Q(customer_no__icontains=query)
                | Q(name__icontains=query)
                | Q(phone__icontains=query)
                | Q(email__icontains=query)
            )
            .order_by("name", "customer_no")[:5]
        )
        for customer in customers:
            contact = customer.phone or customer.email or "No contact"
            results.append(
                {
                    "type": "Customer",
                    "title": customer.name,
                    "meta": f"{customer.customer_no} · {contact}",
                    "status": "Active" if customer.is_active else "Inactive",
                    "url": reverse("backoffice:customer_detail_id", args=[customer.pk]),
                }
            )

    return JsonResponse({"query": query, "results": results})
