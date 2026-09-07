from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from catalog.models import ProductVariant
from inventory.models import Warehouse
from .models import SerializedUnit, WarrantyClaim


class SerializedUnitForm(forms.ModelForm):
    class Meta:
        model = SerializedUnit
        fields = (
            "variant",
            "warehouse",
            "serial_number",
            "imei1",
            "imei2",
            "status",
            "supplier_reference",
            "purchase_reference",
            "purchase_date",
            "purchase_cost",
            "received_date",
            "sales_reference",
            "customer_reference",
            "sold_at",
            "warranty_type",
            "warranty_start_date",
            "warranty_end_date",
            "supplier_warranty_reference",
            "notes",
        )
        widgets = {
            "purchase_date": forms.DateInput(attrs={"type": "date"}),
            "received_date": forms.DateInput(attrs={"type": "date"}),
            "sold_at": forms.DateInput(attrs={"type": "date"}),
            "warranty_start_date": forms.DateInput(attrs={"type": "date"}),
            "warranty_end_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["variant"].queryset = ProductVariant.objects.select_related("product").filter(is_active=True).order_by("product__name", "sku")
        self.fields["warehouse"].queryset = Warehouse.objects.filter(is_active=True).order_by("-is_default", "name")
        for name in (
            "serial_number",
            "imei1",
            "imei2",
            "supplier_reference",
            "purchase_reference",
            "purchase_date",
            "purchase_cost",
            "received_date",
            "sales_reference",
            "customer_reference",
            "sold_at",
            "warranty_type",
            "warranty_start_date",
            "warranty_end_date",
            "supplier_warranty_reference",
            "notes",
        ):
            self.fields[name].required = False
        if self.instance and self.instance.pk:
            self.fields["variant"].disabled = True

    def clean_serial_number(self):
        return (self.cleaned_data.get("serial_number") or "").strip() or None

    def clean_imei1(self):
        return (self.cleaned_data.get("imei1") or "").strip() or None

    def clean_imei2(self):
        return (self.cleaned_data.get("imei2") or "").strip() or None

    def clean(self):
        cleaned = super().clean()
        if not any((cleaned.get("serial_number"), cleaned.get("imei1"), cleaned.get("imei2"))):
            raise ValidationError("Enter at least one Serial Number, IMEI 1 or IMEI 2.")
        if cleaned.get("sold_at") and cleaned.get("status") not in {
            SerializedUnit.Status.SOLD,
            SerializedUnit.Status.WARRANTY_SERVICE,
            SerializedUnit.Status.SCRAPPED,
        }:
            self.add_error("sold_at", "Sold date should only be set for a sold/service/scrapped unit.")
        return cleaned


class WarrantyClaimForm(forms.ModelForm):
    class Meta:
        model = WarrantyClaim
        fields = (
            "claim_no",
            "unit",
            "customer_name",
            "customer_phone",
            "order_reference",
            "claim_date",
            "issue",
            "status",
            "resolution",
            "service_reference",
            "replacement_unit",
            "resolved_at",
            "notes",
        )
        widgets = {
            "claim_date": forms.DateInput(attrs={"type": "date"}),
            "resolved_at": forms.DateInput(attrs={"type": "date"}),
            "issue": forms.Textarea(attrs={"rows": 4}),
            "resolution": forms.Textarea(attrs={"rows": 4}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["unit"].queryset = SerializedUnit.objects.select_related("variant", "variant__product").order_by("variant__product__name", "id")
        self.fields["replacement_unit"].queryset = SerializedUnit.objects.select_related("variant", "variant__product").filter(
            status__in=[SerializedUnit.Status.AVAILABLE, SerializedUnit.Status.RETURNED]
        ).order_by("variant__product__name", "id")
        self.fields["replacement_unit"].required = False
        self.fields["resolved_at"].required = False
        for name in ("customer_name", "customer_phone", "order_reference", "resolution", "service_reference", "notes"):
            self.fields[name].required = False
        if not self.is_bound and not (self.instance and self.instance.pk):
            self.fields["claim_date"].initial = timezone.localdate()
        if self.instance and self.instance.pk:
            self.fields["unit"].disabled = True
        else:
            self.fields["status"].choices = [
                (WarrantyClaim.Status.OPEN, WarrantyClaim.Status.OPEN.label),
                (WarrantyClaim.Status.IN_SERVICE, WarrantyClaim.Status.IN_SERVICE.label),
            ]

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("status")
        replacement = cleaned.get("replacement_unit")
        unit = cleaned.get("unit") or (self.instance.unit if self.instance and self.instance.pk else None)
        if status == WarrantyClaim.Status.REPLACED and not replacement:
            self.add_error("replacement_unit", "Choose the replacement unit.")
        if replacement and unit and replacement.variant_id != unit.variant_id:
            self.add_error("replacement_unit", "Replacement must use the same product variant/SKU.")
        resolved_at = cleaned.get("resolved_at")
        claim_date = cleaned.get("claim_date")
        if resolved_at and claim_date and resolved_at < claim_date:
            self.add_error("resolved_at", "Resolved date cannot be before the claim date.")
        return cleaned
