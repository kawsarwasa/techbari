from decimal import Decimal

from django import forms

from sales.models import SalesOrder

from .models import PaymentMethodConfig, PaymentTransaction


class PaymentCaptureForm(forms.Form):
    sales_order = forms.ModelChoiceField(
        queryset=SalesOrder.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "control"}),
    )
    amount = forms.DecimalField(
        max_digits=18,
        decimal_places=2,
        min_value=Decimal("0.01"),
        widget=forms.NumberInput(attrs={"class": "control", "step": "0.01", "min": "0.01"}),
    )
    method = forms.ChoiceField(
        choices=PaymentMethodConfig.Method.choices,
        widget=forms.Select(attrs={"class": "control"}),
    )
    reference = forms.CharField(
        required=False,
        max_length=160,
        widget=forms.TextInput(attrs={"class": "control", "placeholder": "Transaction / bank / card reference"}),
    )
    transaction_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "control", "type": "date"}),
    )
    note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "control", "rows": 3}),
    )

    def __init__(self, *args, order=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = SalesOrder.objects.exclude(status__in=[SalesOrder.Status.DRAFT, SalesOrder.Status.CANCELLED]).order_by("-order_date", "-id")
        self.fields["sales_order"].queryset = qs
        if order is not None:
            self.fields["sales_order"].initial = order
            self.fields["sales_order"].required = False
            self.order = order
        else:
            self.fields["sales_order"].required = True
            self.order = None

    def clean_sales_order(self):
        return self.order or self.cleaned_data.get("sales_order")


class PaymentRefundForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=18,
        decimal_places=2,
        min_value=Decimal("0.01"),
        widget=forms.NumberInput(attrs={"class": "control", "step": "0.01", "min": "0.01"}),
    )
    reference = forms.CharField(required=False, max_length=160, widget=forms.TextInput(attrs={"class": "control"}))
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": "control", "rows": 2}))


class PaymentMethodConfigForm(forms.ModelForm):
    class Meta:
        model = PaymentMethodConfig
        fields = [
            "display_name",
            "provider_code",
            "merchant_label",
            "is_active",
            "allow_dashboard",
            "allow_pos",
            "allow_storefront",
            "is_test_mode",
            "instructions",
        ]
        widgets = {
            "display_name": forms.TextInput(attrs={"class": "control"}),
            "provider_code": forms.TextInput(attrs={"class": "control", "placeholder": "manual / bank / gateway code"}),
            "merchant_label": forms.TextInput(attrs={"class": "control"}),
            "instructions": forms.Textarea(attrs={"class": "control", "rows": 3}),
        }


class ReconciliationForm(forms.Form):
    reconciliation_status = forms.ChoiceField(
        choices=PaymentTransaction.ReconciliationStatus.choices,
        widget=forms.Select(attrs={"class": "control"}),
    )
    note = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "control"}))
