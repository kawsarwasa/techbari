from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from inventory.models import Warehouse
from serial_tracking.forms import SerializedUnitForm, WarrantyClaimForm
from serial_tracking.models import SerializedUnit, WarrantyClaim
from serial_tracking.services import (
    SerialTrackingError,
    open_warranty_claim,
    register_serial_unit,
    update_serial_unit,
    update_warranty_claim,
    unit_inventory_gap,
)
from .context import page_context


NOTICE_TEXT = {
    "serial-saved": "Serialized unit saved successfully.",
    "claim-saved": "Warranty claim saved successfully.",
}


def _base_context(page_name, request):
    context = page_context(page_name)
    context["serial_database"] = True
    context["serial_notice"] = NOTICE_TEXT.get(request.GET.get("notice", ""), "")
    return context


def _error_message(exc):
    if hasattr(exc, "messages"):
        return " ".join(str(message) for message in exc.messages)
    return str(exc)


def serials(request):
    context = _base_context("serials", request)
    qs = SerializedUnit.objects.select_related(
        "variant", "variant__product", "warehouse"
    ).order_by("-created_at", "-id")

    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    warehouse_id = (request.GET.get("warehouse") or "").strip()

    if query:
        qs = qs.filter(
            Q(serial_number__icontains=query)
            | Q(imei1__icontains=query)
            | Q(imei2__icontains=query)
            | Q(variant__sku__icontains=query)
            | Q(variant__product__name__icontains=query)
            | Q(customer_reference__icontains=query)
            | Q(sales_reference__icontains=query)
        )
    if status in {value for value, _ in SerializedUnit.Status.choices}:
        qs = qs.filter(status=status)
    if warehouse_id.isdigit():
        qs = qs.filter(warehouse_id=int(warehouse_id))

    all_units = SerializedUnit.objects.all()
    context.update(
        serial_units=qs,
        serial_query=query,
        serial_status=status,
        serial_warehouse=warehouse_id,
        serial_status_choices=SerializedUnit.Status.choices,
        serial_warehouses=Warehouse.objects.filter(is_active=True).order_by("-is_default", "name"),
        serial_stats=[
            {"label": "Tracked Units", "value": str(all_units.count()), "trend": "Live", "trend_class": "up", "icon": "backoffice/components/icons/icon_5.html", "color": "blue"},
            {"label": "Available", "value": str(all_units.filter(status=SerializedUnit.Status.AVAILABLE).count()), "trend": "Live", "trend_class": "up", "icon": "backoffice/components/icons/icon_5.html", "color": "green"},
            {"label": "Sold", "value": str(all_units.filter(status=SerializedUnit.Status.SOLD).count()), "trend": "Live", "trend_class": "up", "icon": "backoffice/components/icons/icon_13.html", "color": "purple"},
            {"label": "Warranty Service", "value": str(all_units.filter(status=SerializedUnit.Status.WARRANTY_SERVICE).count()), "trend": "Live", "trend_class": "up", "icon": "backoffice/components/icons/icon_20.html", "color": "orange"},
        ],
    )
    return render(request, "backoffice/pages/serials/serials.html", context)


def serial_add(request):
    unit_id = request.GET.get("id") or request.POST.get("unit_id")
    instance = get_object_or_404(
        SerializedUnit.objects.select_related("variant", "variant__product", "warehouse"),
        pk=unit_id,
    ) if unit_id else None

    form = SerializedUnitForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        try:
            data = dict(form.cleaned_data)
            if instance:
                unit = update_serial_unit(unit=instance, data=data, actor="Dashboard")
            else:
                unit = register_serial_unit(data=data, actor="Dashboard")
            return redirect(reverse("backoffice:serial_add") + f"?id={unit.pk}&notice=serial-saved")
        except (SerialTrackingError, ValidationError) as exc:
            form.add_error(None, _error_message(exc))

    context = _base_context("serial_add", request)
    context.update(
        form=form,
        unit_obj=instance,
        is_edit=bool(instance),
        unit_events=instance.events.select_related("from_warehouse", "to_warehouse").all()[:30] if instance else [],
        unit_claims=instance.warranty_claims.all()[:20] if instance else [],
        inventory_gap=unit_inventory_gap(instance) if instance else None,
    )
    return render(request, "backoffice/pages/serials/serial_add.html", context)


def warranty(request):
    context = _base_context("warranty", request)
    qs = WarrantyClaim.objects.select_related(
        "unit", "unit__variant", "unit__variant__product", "replacement_unit"
    ).order_by("-claim_date", "-id")

    query = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    if query:
        qs = qs.filter(
            Q(claim_no__icontains=query)
            | Q(customer_name__icontains=query)
            | Q(customer_phone__icontains=query)
            | Q(unit__serial_number__icontains=query)
            | Q(unit__imei1__icontains=query)
            | Q(unit__imei2__icontains=query)
            | Q(unit__variant__sku__icontains=query)
            | Q(unit__variant__product__name__icontains=query)
        )
    if status in {value for value, _ in WarrantyClaim.Status.choices}:
        qs = qs.filter(status=status)

    all_claims = WarrantyClaim.objects.all()
    context.update(
        warranty_claims=qs,
        warranty_query=query,
        warranty_status=status,
        warranty_status_choices=WarrantyClaim.Status.choices,
        warranty_stats=[
            {"label": "Total Claims", "value": str(all_claims.count()), "trend": "Live", "trend_class": "up", "icon": "backoffice/components/icons/icon_20.html", "color": "blue"},
            {"label": "Open", "value": str(all_claims.filter(status=WarrantyClaim.Status.OPEN).count()), "trend": "Live", "trend_class": "up", "icon": "backoffice/components/icons/icon_14.html", "color": "orange"},
            {"label": "In Service", "value": str(all_claims.filter(status=WarrantyClaim.Status.IN_SERVICE).count()), "trend": "Live", "trend_class": "up", "icon": "backoffice/components/icons/icon_20.html", "color": "purple"},
            {"label": "Resolved / Replaced", "value": str(all_claims.filter(status__in=[WarrantyClaim.Status.RESOLVED, WarrantyClaim.Status.REPLACED]).count()), "trend": "Live", "trend_class": "up", "icon": "backoffice/components/icons/icon_7.html", "color": "green"},
        ],
    )
    return render(request, "backoffice/pages/warranty/warranty.html", context)


def warranty_add(request):
    claim_id = request.GET.get("id") or request.POST.get("claim_id")
    instance = get_object_or_404(
        WarrantyClaim.objects.select_related("unit", "unit__variant", "unit__variant__product", "unit__warehouse"),
        pk=claim_id,
    ) if claim_id else None

    initial = {}
    if not instance and request.method == "GET":
        unit_id = request.GET.get("unit")
        if unit_id and SerializedUnit.objects.filter(pk=unit_id).exists():
            initial["unit"] = unit_id
    form = WarrantyClaimForm(request.POST or None, instance=instance, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            data = dict(form.cleaned_data)
            if instance:
                claim = update_warranty_claim(claim=instance, data=data, actor="Dashboard")
            else:
                claim = open_warranty_claim(data=data, actor="Dashboard")
            return redirect(reverse("backoffice:warranty_add") + f"?id={claim.pk}&notice=claim-saved")
        except (SerialTrackingError, ValidationError) as exc:
            form.add_error(None, _error_message(exc))

    context = _base_context("warranty_add", request)
    context.update(form=form, claim_obj=instance, is_edit=bool(instance))
    return render(request, "backoffice/pages/warranty/warranty_add.html", context)
