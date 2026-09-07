from django.db import transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from inventory.forms import (
    LowStockThresholdForm,
    StockAdjustmentForm,
    StockTransferForm,
    StockTransferItemFormSet,
    WarehouseForm,
)
from inventory.models import InventoryBalance, StockMovement, StockTransfer, Warehouse
from inventory.services import InventoryError, adjust_stock, low_stock_balances, transfer_stock
from .context import page_context


NOTICE_TEXT = {
    "warehouse-saved": "Warehouse saved successfully.",
    "warehouse-deleted": "Warehouse deleted successfully.",
    "adjusted": "Stock adjustment posted successfully.",
    "transferred": "Stock transfer completed successfully.",
    "threshold": "Low-stock threshold updated.",
}
ERROR_TEXT = {
    "warehouse-default": "The default warehouse cannot be deleted. Make another warehouse default first.",
    "warehouse-stock": "This warehouse still contains stock or reservations and cannot be deleted.",
    "warehouse-history": "This warehouse has inventory history and cannot be deleted. Deactivate it instead.",
}


def _actor(request):
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return str(user)
    return "Dashboard"


def _context(page_name, request):
    context = page_context(page_name)
    context["inventory_database"] = True
    context["inventory_notice"] = NOTICE_TEXT.get(request.GET.get("notice", ""), "")
    context["inventory_error"] = ERROR_TEXT.get(request.GET.get("error", ""), "")
    return context


def _balance_queryset():
    return InventoryBalance.objects.select_related(
        "warehouse", "variant", "variant__product", "variant__product__category", "variant__product__brand"
    ).order_by("warehouse__name", "variant__product__name", "variant__sku")


def inventory(request):
    if request.method == "POST" and request.POST.get("action") == "set_threshold":
        balance = get_object_or_404(InventoryBalance, pk=request.POST.get("balance_id"))
        form = LowStockThresholdForm(request.POST)
        if form.is_valid():
            balance.low_stock_threshold = form.cleaned_data["low_stock_threshold"]
            balance.save(update_fields=["low_stock_threshold", "updated_at"])
            return redirect(reverse("backoffice:inventory") + "?notice=threshold")

    balances = list(_balance_queryset())
    low_rows = [row for row in balances if row.is_low_stock]
    context = _context("inventory", request)
    context.update(
        balances=balances,
        low_rows=low_rows[:8],
        inventory_stats=[
            {"label": "On Hand", "value": str(sum(row.on_hand for row in balances)), "trend": "Live"},
            {"label": "Reserved", "value": str(sum(row.reserved_quantity for row in balances)), "trend": "Live"},
            {"label": "Available", "value": str(sum(row.available_quantity for row in balances)), "trend": "Live"},
            {"label": "Low / Out", "value": str(len(low_rows)), "trend": "Live"},
        ],
    )
    return render(request, "backoffice/pages/inventory/inventory.html", context)


def warehouses(request):
    if request.method == "POST" and request.POST.get("action") == "delete":
        warehouse = get_object_or_404(Warehouse, pk=request.POST.get("warehouse_id"))
        if warehouse.is_default:
            return redirect(reverse("backoffice:warehouses") + "?error=warehouse-default")
        if warehouse.balances.filter(Q(on_hand__gt=0) | Q(reserved_quantity__gt=0)).exists():
            return redirect(reverse("backoffice:warehouses") + "?error=warehouse-stock")
        warehouse.balances.all().delete()
        try:
            warehouse.delete()
        except ProtectedError:
            return redirect(reverse("backoffice:warehouses") + "?error=warehouse-history")
        return redirect(reverse("backoffice:warehouses") + "?notice=warehouse-deleted")

    rows = list(Warehouse.objects.all())
    context = _context("warehouses", request)
    context.update(
        warehouse_rows=rows,
        warehouse_stats=[
            {"label": "Warehouses", "value": str(len(rows)), "trend": "Live"},
            {"label": "Active", "value": str(sum(1 for row in rows if row.is_active)), "trend": "Live"},
            {"label": "Default", "value": str(sum(1 for row in rows if row.is_default)), "trend": "Live"},
            {"label": "Stock Units", "value": str(sum(b.on_hand for w in rows for b in w.balances.all())), "trend": "Live"},
        ],
    )
    return render(request, "backoffice/pages/warehouses/warehouses.html", context)


def warehouse_add(request):
    warehouse_id = request.GET.get("id")
    instance = get_object_or_404(Warehouse, pk=warehouse_id) if warehouse_id else None
    form = WarehouseForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            warehouse = form.save()
            if warehouse.is_default:
                Warehouse.objects.exclude(pk=warehouse.pk).update(is_default=False)
            elif not Warehouse.objects.filter(is_default=True).exists():
                warehouse.is_default = True
                warehouse.is_active = True
                warehouse.save(update_fields=["is_default", "is_active", "updated_at"])
        return redirect(reverse("backoffice:warehouses") + "?notice=warehouse-saved")
    context = _context("warehouse_add", request)
    context.update(form=form, warehouse_obj=instance, is_edit=bool(instance))
    return render(request, "backoffice/pages/warehouses/warehouse_add.html", context)


def stock_adjustment(request):
    form = StockAdjustmentForm(request.POST or None)
    inventory_error = ""
    if request.method == "POST" and form.is_valid():
        try:
            adjust_stock(
                warehouse=form.cleaned_data["warehouse"],
                variant=form.cleaned_data["variant"],
                actual_quantity=form.cleaned_data["actual_quantity"],
                reason=form.cleaned_data["reason"],
                note=form.cleaned_data["note"],
                actor=_actor(request),
            )
        except InventoryError as exc:
            inventory_error = "; ".join(exc.messages)
        else:
            return redirect(reverse("backoffice:inventory") + "?notice=adjusted")
    context = _context("stock_adjustment", request)
    context.update(form=form, inventory_form_error=inventory_error)
    return render(request, "backoffice/pages/inventory/stock_adjustment.html", context)


def stock_transfer(request):
    form = StockTransferForm(request.POST or None)
    formset = StockTransferItemFormSet(request.POST or None, prefix="items")
    inventory_error = ""
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        items = [
            (row["variant"], row["quantity"])
            for row in formset.cleaned_data
            if row and row.get("variant") and row.get("quantity")
        ]
        try:
            transfer_stock(
                from_warehouse=form.cleaned_data["from_warehouse"],
                to_warehouse=form.cleaned_data["to_warehouse"],
                items=items,
                note=form.cleaned_data["note"],
                actor=_actor(request),
            )
        except InventoryError as exc:
            inventory_error = "; ".join(exc.messages)
        else:
            return redirect(reverse("backoffice:inventory") + "?notice=transferred")
    recent_transfers = StockTransfer.objects.select_related("from_warehouse", "to_warehouse").prefetch_related("items")[:10]
    context = _context("stock_transfer", request)
    context.update(
        form=form,
        item_formset=formset,
        recent_transfers=recent_transfers,
        inventory_form_error=inventory_error,
    )
    return render(request, "backoffice/pages/inventory/stock_transfer.html", context)


def movements(request):
    rows = StockMovement.objects.select_related("warehouse", "variant").all()
    warehouse_id = request.GET.get("warehouse")
    movement_type = request.GET.get("type")
    query = (request.GET.get("q") or "").strip()
    if warehouse_id:
        rows = rows.filter(warehouse_id=warehouse_id)
    if movement_type:
        rows = rows.filter(movement_type=movement_type)
    if query:
        rows = rows.filter(
            Q(sku_snapshot__icontains=query)
            | Q(product_snapshot__icontains=query)
            | Q(reference_no__icontains=query)
        )
    context = _context("inventory", request)
    context.update(
        movements=rows[:250],
        warehouses_filter=Warehouse.objects.order_by("name"),
        movement_types=StockMovement.Type.choices,
        selected_warehouse=warehouse_id or "",
        selected_type=movement_type or "",
        search_query=query,
    )
    return render(request, "backoffice/pages/inventory/movements.html", context)


def low_stock(request):
    rows = low_stock_balances()
    context = _context("inventory", request)
    context.update(low_stock_rows=rows)
    return render(request, "backoffice/pages/inventory/low_stock.html", context)
