from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from storefront.forms import DIVISION_CHOICES, normalize_bd_phone
from .models import SavedAddress


class CustomerLoginForm(forms.Form):
    identity = forms.CharField(max_length=254, widget=forms.TextInput(attrs={"id": "loginIdentity", "autocomplete": "username", "placeholder": "Email or phone number"}))
    password = forms.CharField(strip=False, widget=forms.PasswordInput(attrs={"id": "loginPassword", "autocomplete": "current-password", "placeholder": "Enter your password"}))
    remember = forms.BooleanField(required=False, initial=True)


class CustomerRegistrationForm(forms.Form):
    name = forms.CharField(max_length=180, widget=forms.TextInput(attrs={"id": "registerName", "autocomplete": "name", "placeholder": "Enter your full name"}))
    phone = forms.CharField(max_length=40, widget=forms.TextInput(attrs={"id": "registerPhone", "autocomplete": "tel", "inputmode": "tel", "placeholder": "01XXXXXXXXX"}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={"id": "registerEmail", "autocomplete": "email", "placeholder": "you@example.com"}))
    previous_order_number = forms.CharField(required=False, max_length=50, widget=forms.TextInput(attrs={"placeholder": "Required only if you bought from TechBari before", "autocomplete": "off"}))
    password1 = forms.CharField(strip=False, widget=forms.PasswordInput(attrs={"id": "registerPassword", "autocomplete": "new-password", "placeholder": "Create a strong password"}))
    password2 = forms.CharField(strip=False, widget=forms.PasswordInput(attrs={"id": "registerPasswordConfirm", "autocomplete": "new-password", "placeholder": "Re-enter your password"}))
    terms = forms.BooleanField(required=True)

    def clean_name(self):
        value = " ".join((self.cleaned_data.get("name") or "").split())
        if len(value) < 2:
            raise forms.ValidationError("Enter your full name.")
        return value

    def clean_phone(self):
        phone = normalize_bd_phone(self.cleaned_data.get("phone"))
        if len(phone) != 11 or not phone.startswith("01") or not phone.isdigit():
            raise forms.ValidationError("Enter a valid Bangladesh mobile number.")
        return phone

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip().lower()

    def clean_previous_order_number(self):
        return (self.cleaned_data.get("previous_order_number") or "").strip().upper()

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "The passwords do not match.")
        if password1:
            try:
                validate_password(password1)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned


class CustomerProfileForm(forms.Form):
    name = forms.CharField(max_length=180)
    email = forms.EmailField(required=False)
    address = forms.CharField(required=False, max_length=500, widget=forms.Textarea(attrs={"rows": 3}))
    city = forms.CharField(required=False, max_length=120)
    district = forms.CharField(required=False, max_length=120)
    postal_code = forms.CharField(required=False, max_length=20)

    def clean_name(self):
        return " ".join((self.cleaned_data.get("name") or "").split())

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip().lower()


class SavedAddressForm(forms.ModelForm):
    division = forms.ChoiceField(choices=DIVISION_CHOICES)

    class Meta:
        model = SavedAddress
        fields = ("label", "recipient_name", "phone", "division", "district", "upazila", "address", "landmark", "postal_code", "is_default")
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}

    def clean_phone(self):
        phone = normalize_bd_phone(self.cleaned_data.get("phone"))
        if len(phone) != 11 or not phone.startswith("01") or not phone.isdigit():
            raise forms.ValidationError("Enter a valid Bangladesh mobile number.")
        return phone


class TrackOrderForm(forms.Form):
    order_number = forms.CharField(max_length=50, widget=forms.TextInput(attrs={"placeholder": "e.g. TB-260908-ABC123"}))
    phone = forms.CharField(max_length=40, widget=forms.TextInput(attrs={"placeholder": "01XXXXXXXXX", "inputmode": "tel"}))

    def clean_order_number(self):
        return (self.cleaned_data.get("order_number") or "").strip().upper()

    def clean_phone(self):
        phone = normalize_bd_phone(self.cleaned_data.get("phone"))
        if len(phone) != 11 or not phone.startswith("01") or not phone.isdigit():
            raise forms.ValidationError("Enter a valid Bangladesh mobile number.")
        return phone


class WarrantyLookupForm(forms.Form):
    identifier = forms.CharField(max_length=120, widget=forms.TextInput(attrs={"placeholder": "Enter Serial Number or IMEI", "autocomplete": "off"}))

    def clean_identifier(self):
        return (self.cleaned_data.get("identifier") or "").strip()
