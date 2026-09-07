from django import forms
from django.forms import formset_factory

from catalog.models import ProductVariant
from .models import Warehouse


CONTROL = {"class": "control"}


class WarehouseForm(forms.ModelForm):
    class Meta:
        model = Warehouse
        fields = ("name", "code", "address", "is_active", "is_default")
        widgets = {
            "name": forms.TextInput(attrs=CONTROL),
            "code": forms.TextInput(attrs=CONTROL),
            "address": forms.Textarea(attrs={"class": "control textarea", "rows": 4}),
        }

    def clean_code(self):
        return (self.cleaned_data.get("code") or "").strip().upper()

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("is_default") and not cleaned.get("is_active"):
            self.add_error("is_active", "The default warehouse must stay active.")
        return cleaned


class StockAdjustmentForm(forms.Form):
    warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.none(),
        widget=forms.Select(attrs=CONTROL),
    )
    variant = forms.ModelChoiceField(
        queryset=ProductVariant.objects.none(),
        widget=forms.Select(attrs=CONTROL),
        label="Product / SKU",
    )
    actual_quantity = forms.IntegerField(min_value=0, widget=forms.NumberInput(attrs=CONTROL))
    reason = forms.CharField(max_length=255, widget=forms.TextInput(attrs=CONTROL))
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": "control textarea", "rows": 4}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["warehouse"].queryset = Warehouse.objects.filter(is_active=True).order_by("name")
        self.fields["variant"].queryset = ProductVariant.objects.filter(is_active=True).select_related(
            "product"
        ).order_by("product__name", "sku")
        self.fields["variant"].label_from_instance = lambda obj: f"{obj.product.name} — {obj.name} — {obj.sku}"


class StockTransferForm(forms.Form):
    from_warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.none(),
        widget=forms.Select(attrs=CONTROL),
        label="From Warehouse",
    )
    to_warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.none(),
        widget=forms.Select(attrs=CONTROL),
        label="To Warehouse",
    )
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": "control textarea", "rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = Warehouse.objects.filter(is_active=True).order_by("name")
        self.fields["from_warehouse"].queryset = queryset
        self.fields["to_warehouse"].queryset = queryset

    def clean(self):
        cleaned = super().clean()
        source = cleaned.get("from_warehouse")
        destination = cleaned.get("to_warehouse")
        if source and destination and source.pk == destination.pk:
            self.add_error("to_warehouse", "Destination warehouse must be different from source.")
        return cleaned


class StockTransferItemForm(forms.Form):
    variant = forms.ModelChoiceField(
        queryset=ProductVariant.objects.none(),
        required=False,
        widget=forms.Select(attrs=CONTROL),
        label="Product / SKU",
    )
    quantity = forms.IntegerField(
        min_value=1,
        required=False,
        widget=forms.NumberInput(attrs={"class": "control", "placeholder": "Qty"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["variant"].queryset = ProductVariant.objects.filter(is_active=True).select_related(
            "product"
        ).order_by("product__name", "sku")
        self.fields["variant"].label_from_instance = lambda obj: f"{obj.product.name} — {obj.name} — {obj.sku}"

    def clean(self):
        cleaned = super().clean()
        variant = cleaned.get("variant")
        quantity = cleaned.get("quantity")
        if variant and not quantity:
            self.add_error("quantity", "Enter a quantity for this item.")
        if quantity and not variant:
            self.add_error("variant", "Select a variant for this quantity.")
        return cleaned


StockTransferItemFormSet = formset_factory(
    StockTransferItemForm,
    extra=5,
    min_num=1,
    validate_min=True,
)


class LowStockThresholdForm(forms.Form):
    low_stock_threshold = forms.IntegerField(min_value=0, widget=forms.NumberInput(attrs=CONTROL))
