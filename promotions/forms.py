from django import forms
from django.core.exceptions import ValidationError

from .models import Campaign, Coupon, FlashSale


class DateTimeLocalInput(forms.DateTimeInput):
    input_type = "datetime-local"

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("format", "%Y-%m-%dT%H:%M")
        super().__init__(*args, **kwargs)


def _style(form):
    for field in form.fields.values():
        current = field.widget.attrs.get("class", "")
        field.widget.attrs["class"] = (current + " control").strip()
    return form


class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ("code", "name", "source", "medium", "starts_at", "ends_at", "is_active")
        widgets = {"starts_at": DateTimeLocalInput(), "ends_at": DateTimeLocalInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)


class CouponForm(forms.ModelForm):
    class Meta:
        model = Coupon
        fields = ("code", "name", "discount_type", "value", "minimum_order_amount", "starts_at", "ends_at", "usage_limit", "scope", "products", "categories", "campaign", "is_active")
        widgets = {"starts_at": DateTimeLocalInput(), "ends_at": DateTimeLocalInput(), "products": forms.SelectMultiple(attrs={"size": 8}), "categories": forms.SelectMultiple(attrs={"size": 8})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)
        self.fields["usage_limit"].help_text = "Leave blank for unlimited usage."
        self.fields["products"].required = False
        self.fields["categories"].required = False

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("scope") == Coupon.Scope.PRODUCTS and not cleaned.get("products"):
            self.add_error("products", "Select at least one product for a product-specific coupon.")
        if cleaned.get("scope") == Coupon.Scope.CATEGORIES and not cleaned.get("categories"):
            self.add_error("categories", "Select at least one category for a category-specific coupon.")
        return cleaned


class FlashSaleForm(forms.ModelForm):
    class Meta:
        model = FlashSale
        fields = ("name", "discount_type", "value", "starts_at", "ends_at", "products", "is_active")
        widgets = {"starts_at": DateTimeLocalInput(), "ends_at": DateTimeLocalInput(), "products": forms.SelectMultiple(attrs={"size": 10})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self)

    def clean_products(self):
        products = self.cleaned_data.get("products")
        if not products:
            raise ValidationError("Select at least one product for the Flash Sale.")
        return products
