from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from inventory.models import Warehouse
from .models import PurchaseOrder, PurchasePayment, Supplier


def _style_fields(form):
    for field in form.fields.values():
        classes = field.widget.attrs.get("class", "")
        field.widget.attrs["class"] = (classes + " control").strip()


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = (
            "code",
            "name",
            "contact_person",
            "phone",
            "email",
            "address",
            "tax_id",
            "payment_terms_days",
            "credit_limit",
            "opening_balance",
            "is_active",
            "notes",
        )
        widgets = {
            "address": forms.Textarea(attrs={"rows": 4}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["contact_person"].required = False
        self.fields["phone"].required = False
        self.fields["email"].required = False
        self.fields["address"].required = False
        self.fields["tax_id"].required = False
        self.fields["notes"].required = False
        _style_fields(self)

    def clean_code(self):
        return (self.cleaned_data.get("code") or "").strip().upper()


class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = (
            "po_number",
            "supplier",
            "warehouse",
            "status",
            "purchase_date",
            "expected_date",
            "supplier_invoice_no",
            "invoice_date",
            "shipping_cost",
            "other_cost",
            "discount_amount",
            "notes",
        )
        widgets = {
            "purchase_date": forms.DateInput(attrs={"type": "date"}),
            "expected_date": forms.DateInput(attrs={"type": "date"}),
            "invoice_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier"].queryset = Supplier.objects.filter(is_active=True).order_by("name", "code")
        self.fields["warehouse"].queryset = Warehouse.objects.filter(is_active=True).order_by("-is_default", "name")
        self.fields["expected_date"].required = False
        self.fields["supplier_invoice_no"].required = False
        self.fields["invoice_date"].required = False
        self.fields["notes"].required = False
        if not self.is_bound and not (self.instance and self.instance.pk):
            self.fields["purchase_date"].initial = timezone.localdate()
            self.fields["status"].initial = PurchaseOrder.Status.DRAFT
        if self.instance and self.instance.pk and self.instance.status in {
            PurchaseOrder.Status.PARTIALLY_RECEIVED,
            PurchaseOrder.Status.RECEIVED,
            PurchaseOrder.Status.CANCELLED,
        }:
            self.fields["status"].disabled = True
        else:
            self.fields["status"].choices = [
                (PurchaseOrder.Status.DRAFT, PurchaseOrder.Status.DRAFT.label),
                (PurchaseOrder.Status.ORDERED, PurchaseOrder.Status.ORDERED.label),
            ]
        _style_fields(self)

    def clean_po_number(self):
        return (self.cleaned_data.get("po_number") or "").strip().upper()


class PurchaseReceiptHeaderForm(forms.Form):
    received_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    supplier_challan_no = forms.CharField(max_length=100, required=False)
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.fields["received_date"].initial = timezone.localdate()
        _style_fields(self)


class PurchasePaymentForm(forms.ModelForm):
    class Meta:
        model = PurchasePayment
        fields = ("amount", "method", "reference", "payment_date", "note")
        widgets = {
            "payment_date": forms.DateInput(attrs={"type": "date"}),
            "note": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, purchase=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.purchase = purchase
        self.fields["reference"].required = False
        self.fields["note"].required = False
        if not self.is_bound:
            self.fields["payment_date"].initial = timezone.localdate()
            if purchase:
                self.fields["amount"].initial = purchase.outstanding_amount
        _style_fields(self)

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount is not None and self.purchase and amount > self.purchase.outstanding_amount:
            raise ValidationError(f"Payment cannot exceed outstanding amount ({self.purchase.outstanding_amount}).")
        return amount


class PurchaseReturnHeaderForm(forms.Form):
    return_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    reason = forms.CharField(max_length=255)
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.fields["return_date"].initial = timezone.localdate()
        _style_fields(self)
