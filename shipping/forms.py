from django import forms

from payments.models import PaymentMethodConfig
from sales.models import SalesOrder

from .models import CODSettlement, CourierProvider, Shipment


class CourierProviderForm(forms.ModelForm):
    class Meta:
        model = CourierProvider
        fields = [
            "code",
            "name",
            "contact_person",
            "phone",
            "email",
            "website",
            "tracking_url_template",
            "supports_cod",
            "default_courier_fee",
            "is_active",
            "api_enabled",
            "is_test_mode",
            "notes",
        ]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                continue
            field.widget.attrs.setdefault("class", "control")


class ShipmentForm(forms.ModelForm):
    class Meta:
        model = Shipment
        fields = [
            "order",
            "courier",
            "shipment_date",
            "expected_delivery_date",
            "tracking_id",
            "courier_reference",
            "parcel_count",
            "weight_kg",
            "courier_fee",
            "cod_expected",
            "notes",
        ]
        widgets = {
            "shipment_date": forms.DateInput(attrs={"type": "date"}),
            "expected_delivery_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["order"].queryset = (
            SalesOrder.objects.filter(
                status__in=[
                    SalesOrder.Status.CONFIRMED,
                    SalesOrder.Status.PROCESSING,
                    SalesOrder.Status.COMPLETED,
                ]
            )
            .exclude(channel=SalesOrder.Channel.POS)
            .filter(shipment__isnull=True)
            .select_related("customer", "warehouse")
            .order_by("-order_date", "-id")
        )
        self.fields["courier"].queryset = CourierProvider.objects.filter(is_active=True).order_by("name")
        self.fields["courier_fee"].required = False
        self.fields["cod_expected"].required = False
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "control")

    def clean(self):
        cleaned = super().clean()
        order = cleaned.get("order")
        courier = cleaned.get("courier")
        cod_expected = cleaned.get("cod_expected")
        if order and cod_expected is not None and cod_expected > order.outstanding_amount:
            self.add_error("cod_expected", f"COD cannot exceed current order due ({order.outstanding_amount}).")
        if courier and cod_expected and not courier.supports_cod:
            self.add_error("courier", "Selected courier is not configured for COD shipments.")
        return cleaned


class ShipmentStatusForm(forms.Form):
    new_status = forms.ChoiceField(choices=Shipment.Status.choices)
    cod_collected = forms.DecimalField(max_digits=18, decimal_places=2, min_value=0, required=False)
    location = forms.CharField(max_length=180, required=False)
    failure_reason = forms.CharField(max_length=255, required=False)
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, allowed_statuses=None, **kwargs):
        super().__init__(*args, **kwargs)
        if allowed_statuses is not None:
            allowed = list(allowed_statuses)
            self.fields["new_status"].choices = [(value, Shipment.Status(value).label) for value in allowed]
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "control")


class TrackingUpdateForm(forms.Form):
    tracking_id = forms.CharField(max_length=160, required=False)
    courier_reference = forms.CharField(max_length=160, required=False)
    location = forms.CharField(max_length=180, required=False)
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "control")


class CODSettlementForm(forms.ModelForm):
    class Meta:
        model = CODSettlement
        fields = [
            "courier",
            "settlement_date",
            "payment_method",
            "reference",
            "courier_deduction",
            "note",
        ]
        widgets = {
            "settlement_date": forms.DateInput(attrs={"type": "date"}),
            "note": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["courier"].queryset = CourierProvider.objects.order_by("name")
        active_methods = PaymentMethodConfig.objects.filter(is_active=True, allow_dashboard=True).values_list("method", flat=True)
        allowed = set(active_methods)
        self.fields["payment_method"].choices = [
            (value, label) for value, label in PaymentMethodConfig.Method.choices if value in allowed
        ]
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "control")
