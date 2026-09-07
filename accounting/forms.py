from django import forms

from .models import Account, AccountingPeriod


class StyledModelForm(forms.ModelForm):
    def _style(self):
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (existing + " control").strip()


class AccountForm(StyledModelForm):
    class Meta:
        model = Account
        fields = ["code", "name", "account_type", "normal_balance", "description", "allow_manual_entries", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()

    def clean_code(self):
        return str(self.cleaned_data.get("code") or "").strip().upper()


class AccountingPeriodForm(StyledModelForm):
    class Meta:
        model = AccountingPeriod
        fields = ["name", "start_date", "end_date"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()


class ManualJournalHeaderForm(forms.Form):
    entry_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "control"}))
    source_reference = forms.CharField(required=False, max_length=160, widget=forms.TextInput(attrs={"class": "control"}))
    description = forms.CharField(widget=forms.Textarea(attrs={"rows": 3, "class": "control"}))
