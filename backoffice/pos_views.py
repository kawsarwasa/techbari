import json
from decimal import Decimal

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.templatetags.static import static
from django.views.decorators.http import require_GET, require_POST

from customers.models import Customer
from inventory.models import InventoryBalance, Warehouse
from inventory.services import get_default_warehouse
from sales.models import SalesOrder
from sales.pos_services import POSError, complete_pos_sale, discard_pos_hold, hold_pos_order

from .context import page_context


def _money_number(value):
    value = Decimal(value or 0)
    return int(value) if value == value.to_integral() else float(value)


def _product_image(product):
    image = product.images.order_by("sort_order", "id").first()
    if image:
        if image.image:
            try:
                return image.image.url
            except ValueError:
                pass
        if image.static_path:
            return static(image.static_path)
    return static("admin/images/baseus-e16.webp")


def _catalog_for_warehouse(warehouse):
    rows = InventoryBalance.objects.select_related(
        "variant",
        "variant__product",
        "variant__product__category",
        "variant__product__brand",
    ).filter(
        warehouse=warehouse,
        variant__is_active=True,
        variant__product__status="active",
        variant__product__category__is_active=True,
        variant__product__brand__is_active=True,
    ).order_by("variant__product__name", "variant__name")
    products = []
    categories = set()
    for balance in rows:
        variant = balance.variant
        product = variant.product
        categories.add(product.category.name)
        price = variant.price_override if variant.price_override is not None else product.current_price
        products.append(
            {
                "variant_id": variant.pk,
                "product_id": product.pk,
                "name": product.name,
                "variant": variant.name,
                "sku": variant.sku,
                "barcode": variant.barcode or "",
                "category": product.category.name,
                "brand": product.brand.name,
                "price": _money_number(price),
                "stock": balance.available_quantity,
                "image": _product_image(product),
            }
        )
    return products, sorted(categories)


def _serialize_held(order):
    return {
        "id": order.pk,
        "order_number": order.order_number,
        "customer_id": order.customer_id,
        "customer_name": order.customer_name,
        "warehouse_id": order.warehouse_id,
        "discount_amount": _money_number(order.discount_amount),
        "notes": order.notes,
        "total": _money_number(order.grand_total),
        "created_at": order.created_at.isoformat(),
        "items": [
            {
                "variant_id": item.variant_id,
                "name": item.product_snapshot,
                "variant": item.variant_snapshot,
                "sku": item.sku_snapshot,
                "qty": item.quantity,
                "price": _money_number(item.unit_price),
            }
            for item in order.items.all()
        ],
    }


@require_GET
def pos(request):
    warehouses = list(Warehouse.objects.filter(is_active=True).order_by("-is_default", "name"))
    if warehouses:
        selected = None
        raw = request.GET.get("warehouse", "")
        if raw.isdigit():
            selected = next((warehouse for warehouse in warehouses if warehouse.pk == int(raw)), None)
        selected = selected or next((warehouse for warehouse in warehouses if warehouse.is_default), warehouses[0])
    else:
        selected = get_default_warehouse()
        warehouses = [selected]

    products, categories = _catalog_for_warehouse(selected)
    customers = list(Customer.objects.filter(is_active=True).order_by("name"))
    held_orders = list(
        SalesOrder.objects.select_related("customer", "warehouse").prefetch_related("items").filter(
            channel=SalesOrder.Channel.POS,
            status=SalesOrder.Status.DRAFT,
            warehouse=selected,
        ).order_by("-created_at")[:25]
    )
    context = page_context("pos")
    context.update(
        {
            "warehouses_real": warehouses,
            "selected_warehouse": selected,
            "customers_real": customers,
            "held_orders_real": held_orders,
            "pos_data": {
                "products": products,
                "categories": categories,
                "held": [_serialize_held(order) for order in held_orders],
                "warehouse_id": selected.pk,
            },
        }
    )
    return render(request, "backoffice/pages/pos/pos.html", context)


def _payload(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise POSError("Invalid POS request payload.") from exc


@require_POST
def pos_action(request):
    try:
        data = _payload(request)
        action = str(data.get("action") or "").lower()
        common = {
            "warehouse_id": data.get("warehouse_id"),
            "customer_id": data.get("customer_id"),
            "items": data.get("items"),
            "discount_amount": data.get("discount_amount", 0),
            "note": data.get("note", ""),
            "order_id": data.get("order_id"),
            "actor": "POS Counter",
        }
        if action == "hold":
            order = hold_pos_order(**common)
            return JsonResponse({"ok": True, "action": "hold", "order": _serialize_held(order)})
        if action == "complete":
            order = complete_pos_sale(
                **common,
                payment_method=data.get("payment_method", "cash"),
                payment_reference=data.get("payment_reference", ""),
                tendered_amount=data.get("tendered_amount"),
            )
            return JsonResponse(
                {
                    "ok": True,
                    "action": "complete",
                    "order_id": order.pk,
                    "order_number": order.order_number,
                    "receipt_url": f"/dashboard/pos/receipt/{order.pk}/",
                    "change_amount": _money_number(order.change_amount),
                }
            )
        if action == "discard":
            discard_pos_hold(order_id=data.get("order_id"))
            return JsonResponse({"ok": True, "action": "discard"})
        raise POSError("Unsupported POS action.")
    except POSError as exc:
        message = exc.messages[0] if hasattr(exc, "messages") and exc.messages else str(exc)
        return JsonResponse({"ok": False, "error": message}, status=400)


@require_GET
def pos_hold_detail(request, order_id):
    order = get_object_or_404(
        SalesOrder.objects.select_related("customer", "warehouse").prefetch_related("items"),
        pk=order_id,
        channel=SalesOrder.Channel.POS,
        status=SalesOrder.Status.DRAFT,
    )
    return JsonResponse({"ok": True, "order": _serialize_held(order)})


@require_GET
def pos_receipt(request, order_id):
    order = get_object_or_404(
        SalesOrder.objects.select_related("customer", "warehouse").prefetch_related("items"),
        pk=order_id,
        channel=SalesOrder.Channel.POS,
        status=SalesOrder.Status.COMPLETED,
    )
    return render(request, "backoffice/pages/pos/receipt.html", {"order": order})
