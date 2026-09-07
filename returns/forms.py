from django import forms

from inventory.models import Warehouse
from sales.models import SalesOrder

from .models import SalesReturn


class SalesReturnForm(forms.Form):
    order = forms.ModelChoiceField(queryset=SalesOrder.objects.none(), empty_label="Select completed order")
    warehouse = forms.ModelChoiceField(queryset=Warehouse.objects.none(), empty_label="Select receiving warehouse")
    source = forms.ChoiceField(choices=SalesReturn.Source.choices)
    resolution = forms.ChoiceField(choices=SalesReturn.Resolution.choices)
    reason_category = forms.ChoiceField(choices=SalesReturn.Reason.choices)
    requested_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    source_reference = forms.CharField(required=False, max_length=160)
    refund_reference = forms.CharField(required=False, max_length=160)
    customer_note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    internal_note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["order"].queryset = (
            SalesOrder.objects.filter(status=SalesOrder.Status.COMPLETED, items__issued_quantity__gt=0)
            .select_related("customer")
            .distinct()
            .order_by("-order_date", "-id")
        )
        self.fields["warehouse"].queryset = Warehouse.objects.filter(is_active=True).order_by("name", "code")
        for field in self.fields.values():
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (css + " control").strip()

    def clean(self):
        cleaned = super().clean()
        order = cleaned.get("order")
        source = cleaned.get("source")
        if order and source == SalesReturn.Source.POS and order.channel != SalesOrder.Channel.POS:
            self.add_error("source", "POS / Counter Return requires a POS Sales Order.")
        return cleaned
