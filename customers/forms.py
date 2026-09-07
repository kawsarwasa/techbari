from decimal import Decimal

from django import forms

from .models import Customer, CustomerGroup


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            "name",
            "phone",
            "email",
            "group",
            "source",
            "address",
            "district",
            "city",
            "postal_code",
            "credit_limit",
            "opening_due",
            "notes",
            "is_active",
        ]
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        if not phone:
            raise forms.ValidationError("Phone is required.")
        qs = Customer.objects.filter(phone__iexact=phone)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A customer with this phone already exists.")
        return phone

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            return ""
        qs = Customer.objects.filter(email__iexact=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A customer with this email already exists.")
        return email

    def clean_credit_limit(self):
        value = self.cleaned_data.get("credit_limit") or Decimal("0.00")
        if value < 0:
            raise forms.ValidationError("Credit limit cannot be negative.")
        return value

    def clean_opening_due(self):
        value = self.cleaned_data.get("opening_due") or Decimal("0.00")
        if value < 0:
            raise forms.ValidationError("Opening due cannot be negative.")
        return value


class CustomerGroupForm(forms.ModelForm):
    class Meta:
        model = CustomerGroup
        fields = ["name", "code", "discount_percent", "is_active", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip().upper()
        if not code:
            raise forms.ValidationError("Group code is required.")
        qs = CustomerGroup.objects.filter(code__iexact=code)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A customer group with this code already exists.")
        return code

    def clean_discount_percent(self):
        value = self.cleaned_data.get("discount_percent") or Decimal("0.00")
        if value < 0 or value > 100:
            raise forms.ValidationError("Discount must be between 0 and 100 percent.")
        return value
