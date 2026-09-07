from decimal import Decimal

from django import forms

from customers.models import Customer
from inventory.models import Warehouse

from .models import SalesOrder


class SalesOrderForm(forms.ModelForm):
    class Meta:
        model = SalesOrder
        fields = [
            "order_number",
            "customer",
            "warehouse",
            "channel",
            "status",
            "order_date",
            "shipping_name",
            "shipping_phone",
            "shipping_email",
            "shipping_address",
            "shipping_city",
            "shipping_district",
            "shipping_postal_code",
            "discount_amount",
            "shipping_charge",
            "amount_paid",
            "notes",
        ]
        widgets = {
            "order_date": forms.DateInput(attrs={"type": "date"}),
            "shipping_address": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = Customer.objects.filter(is_active=True).order_by("name")
        self.fields["warehouse"].queryset = Warehouse.objects.filter(is_active=True).order_by("-is_default", "name")
        self.fields["status"].choices = [
            (SalesOrder.Status.DRAFT, SalesOrder.Status.DRAFT.label),
            (SalesOrder.Status.PENDING, SalesOrder.Status.PENDING.label),
        ]
        self.fields["order_number"].required = False

    def clean_order_number(self):
        number = (self.cleaned_data.get("order_number") or "").strip().upper()
        if not number:
            return self.instance.order_number if self.instance.pk else ""
        qs = SalesOrder.objects.filter(order_number__iexact=number)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("This order number already exists.")
        return number

    def clean(self):
        cleaned = super().clean()
        customer = cleaned.get("customer")
        shipping_name = (cleaned.get("shipping_name") or "").strip()
        shipping_phone = (cleaned.get("shipping_phone") or "").strip()
        if not customer and (not shipping_name or not shipping_phone):
            raise forms.ValidationError("Guest orders require a shipping name and phone.")
        for field in ("discount_amount", "shipping_charge", "amount_paid"):
            value = cleaned.get(field) or Decimal("0.00")
            if value < 0:
                self.add_error(field, "Amount cannot be negative.")
        return cleaned


class OrderPaymentUpdateForm(forms.Form):
    amount_paid = forms.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.00"))
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
