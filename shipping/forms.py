from django import forms

from payments.models import PaymentMethodConfig
from sales.models import SalesOrder

from .models import CODSettlement, CourierProvider, Shipment


class ShipmentOrderSelect(forms.Select):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_meta = {}

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        raw_value = getattr(value, "value", value)
        meta = self.order_meta.get(str(raw_value))
        if meta:
            option["attrs"]["data-outstanding"] = str(meta["outstanding"])
            option["attrs"]["data-shipping-charge"] = str(meta["shipping_charge"])
            option["attrs"]["data-grand-total"] = str(meta["grand_total"])
        return option


class ShipmentCourierSelect(forms.Select):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.courier_meta = {}

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        raw_value = getattr(value, "value", value)
        meta = self.courier_meta.get(str(raw_value))
        if meta:
            option["attrs"]["data-default-fee"] = str(meta["default_fee"])
            option["attrs"]["data-supports-cod"] = "1" if meta["supports_cod"] else "0"
        return option


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
            "order": ShipmentOrderSelect(),
            "courier": ShipmentCourierSelect(),
            "shipment_date": forms.DateInput(attrs={"type": "date"}),
            "expected_delivery_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        order_queryset = (
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
        courier_queryset = CourierProvider.objects.filter(is_active=True).order_by("name")
        self.fields["order"].queryset = order_queryset
        self.fields["courier"].queryset = courier_queryset
        self.fields["courier_fee"].required = False
        self.fields["cod_expected"].required = False
        self.fields["cod_expected"].widget.attrs["readonly"] = "readonly"
        self.fields["cod_expected"].widget.attrs["aria-readonly"] = "true"

        orders = list(order_queryset)
        couriers = list(courier_queryset)
        if isinstance(self.fields["order"].widget, ShipmentOrderSelect):
            self.fields["order"].widget.order_meta = {
                str(order.pk): {
                    "outstanding": order.outstanding_amount,
                    "shipping_charge": order.shipping_charge or 0,
                    "grand_total": order.grand_total or 0,
                }
                for order in orders
            }
        if isinstance(self.fields["courier"].widget, ShipmentCourierSelect):
            self.fields["courier"].widget.courier_meta = {
                str(courier.pk): {
                    "default_fee": courier.default_courier_fee or 0,
                    "supports_cod": courier.supports_cod,
                }
                for courier in couriers
            }

        if not self.is_bound:
            # Avoid the model's numeric 0.00 defaults being mistaken for an intentional
            # zero. Blank courier fee falls back to the provider default in the service.
            self.initial["courier_fee"] = None
            self.initial["cod_expected"] = None
            selected_order_id = self.initial.get("order")
            if selected_order_id:
                selected_order = next((order for order in orders if str(order.pk) == str(selected_order_id)), None)
                if selected_order:
                    self.initial["cod_expected"] = selected_order.outstanding_amount

        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "control")

    def clean(self):
        cleaned = super().clean()
        order = cleaned.get("order")
        courier = cleaned.get("courier")
        if order:
            # Dashboard shipment COD is always the order's current unpaid balance.
            # This prevents a stale/default 0.00 field from creating a non-COD
            # shipment for an unpaid order.
            cleaned["cod_expected"] = order.outstanding_amount
        cod_expected = cleaned.get("cod_expected")
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
