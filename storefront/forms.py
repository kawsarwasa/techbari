import json
import re

from django import forms
from django.core import signing

from .bd_locations import DIVISION_CHOICES, district_choices, upazila_choices

CHECKOUT_SIGNING_SALT = "storefront.checkout.v160"


def normalize_bd_phone(value):
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("880"):
        digits = "0" + digits[3:]
    elif digits.startswith("88") and len(digits) == 13:
        digits = digits[2:]
    return digits


class CheckoutForm(forms.Form):
    full_name = forms.CharField(max_length=180, widget=forms.TextInput(attrs={"placeholder": "Enter your full name", "autocomplete": "name"}))
    phone = forms.CharField(max_length=40, widget=forms.TextInput(attrs={"placeholder": "01XXXXXXXXX", "autocomplete": "tel", "inputmode": "tel"}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={"placeholder": "you@email.com", "autocomplete": "email"}))
    division = forms.ChoiceField(
        choices=DIVISION_CHOICES,
        widget=forms.Select(attrs={"autocomplete": "address-level1"}),
    )
    district = forms.ChoiceField(
        choices=(("", "Select District"),),
        error_messages={"invalid_choice": "Select a district that belongs to the selected division."},
        widget=forms.Select(attrs={"autocomplete": "address-level2"}),
    )
    upazila = forms.ChoiceField(
        choices=(("", "Select Upazila / Thana"),),
        error_messages={"invalid_choice": "Select an Upazila / Thana that belongs to the selected district."},
        widget=forms.Select(attrs={"autocomplete": "address-level3"}),
    )
    address = forms.CharField(max_length=500, widget=forms.TextInput(attrs={"placeholder": "House no, Road no, Area name", "autocomplete": "street-address"}))
    landmark = forms.CharField(max_length=180, required=False, widget=forms.TextInput(attrs={"placeholder": "e.g. Near school, mosque, shopping mall"}))
    delivery_option = forms.ChoiceField(choices=(("inside", "Inside Dhaka"), ("outside", "Outside Dhaka")), initial="inside")
    payment_method = forms.ChoiceField(choices=(("cod", "Cash on Delivery"),), initial="cod")
    order_note = forms.CharField(max_length=1000, required=False, widget=forms.Textarea(attrs={"placeholder": "Any special instructions for your order?", "rows": 3}))
    coupon_code = forms.CharField(max_length=40, required=False, widget=forms.TextInput(attrs={"id": "checkoutCouponInput", "placeholder": "Enter coupon code", "autocomplete": "off"}))
    cart_payload = forms.CharField(widget=forms.HiddenInput(attrs={"id": "checkoutCartPayload"}))
    checkout_token = forms.CharField(widget=forms.HiddenInput(attrs={"id": "checkoutToken"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        def current_value(name):
            if self.is_bound:
                return str(self.data.get(self.add_prefix(name)) or "").strip()
            initial = self.initial.get(name, self.fields[name].initial)
            return str(initial or "").strip()

        division = current_value("division")
        district = current_value("district")
        upazila = current_value("upazila")

        # On GET, retain an old saved-address value even if it predates the
        # current hierarchy. Bound submissions stay strict, so users cannot
        # submit a District/Upazila that does not belong to its parent.
        legacy_district = district if not self.is_bound else ""
        legacy_upazila = upazila if not self.is_bound else ""
        self.fields["district"].choices = district_choices(division, include=legacy_district)
        self.fields["upazila"].choices = upazila_choices(
            division,
            district,
            include=legacy_upazila,
        )

    def clean_full_name(self):
        value = " ".join((self.cleaned_data.get("full_name") or "").split())
        if len(value) < 2:
            raise forms.ValidationError("Enter your full name.")
        return value

    def clean_phone(self):
        phone = normalize_bd_phone(self.cleaned_data.get("phone"))
        if not re.fullmatch(r"01[3-9]\d{8}", phone):
            raise forms.ValidationError("Enter a valid Bangladesh mobile number, for example 017XXXXXXXX.")
        return phone

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip().lower()

    def clean_coupon_code(self):
        return (self.cleaned_data.get("coupon_code") or "").strip().upper()

    def clean_cart_payload(self):
        raw = self.cleaned_data.get("cart_payload") or ""
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise forms.ValidationError("Your cart could not be read. Please refresh and try again.") from exc
        if not isinstance(payload, list) or not payload:
            raise forms.ValidationError("Your cart is empty.")
        if len(payload) > 50:
            raise forms.ValidationError("Too many cart lines. Please reduce your cart and try again.")
        merged = {}
        for index, row in enumerate(payload, start=1):
            if not isinstance(row, dict):
                raise forms.ValidationError(f"Cart line {index} is invalid.")
            try:
                variant_id = int(row.get("variant_id")); quantity = int(row.get("qty"))
            except (TypeError, ValueError) as exc:
                raise forms.ValidationError(f"Cart line {index} is invalid.") from exc
            if variant_id <= 0 or quantity <= 0:
                raise forms.ValidationError(f"Cart line {index} is invalid.")
            if quantity > 99:
                raise forms.ValidationError("A single cart line cannot exceed 99 units.")
            merged[variant_id] = merged.get(variant_id, 0) + quantity
            if merged[variant_id] > 99:
                raise forms.ValidationError("A single SKU cannot exceed 99 units per checkout.")
        return [{"variant_id": variant_id, "qty": quantity} for variant_id, quantity in merged.items()]

    def clean_checkout_token(self):
        token = (self.cleaned_data.get("checkout_token") or "").strip()
        try:
            payload = signing.loads(token, salt=CHECKOUT_SIGNING_SALT, max_age=7200)
        except signing.BadSignature as exc:
            raise forms.ValidationError("Your checkout session expired. Refresh the page and try again.") from exc
        order_number = str(payload.get("order_number") or "").strip().upper() if isinstance(payload, dict) else ""
        if not order_number.startswith("TB-"):
            raise forms.ValidationError("Invalid checkout session. Refresh the page and try again.")
        return {"token": token, "order_number": order_number}
