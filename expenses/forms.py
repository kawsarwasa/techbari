from django import forms

from accounting.models import Account

from .models import Expense, ExpenseCategory


class StyledModelForm(forms.ModelForm):
    def _style(self):
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (existing + " control").strip()


class ExpenseForm(StyledModelForm):
    class Meta:
        model = Expense
        fields = [
            "expense_date",
            "category",
            "payee",
            "description",
            "amount",
            "preferred_payment_method",
            "receipt_no",
            "notes",
        ]
        widgets = {
            "expense_date": forms.DateInput(attrs={"type": "date"}),
            "amount": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "description": forms.TextInput(attrs={"placeholder": "What was this expense for?"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = ExpenseCategory.objects.filter(is_active=True).select_related("account")
        self.fields["preferred_payment_method"].required = False
        self._style()


class ExpenseCategoryForm(StyledModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ["code", "name", "account", "description", "sort_order", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = Account.objects.filter(account_type=Account.Type.EXPENSE, is_active=True).order_by("code")
        self._style()


class ExpensePaymentForm(forms.Form):
    payment_method = forms.ChoiceField(choices=Expense.Method.choices, widget=forms.Select(attrs={"class": "control"}))
    payment_reference = forms.CharField(required=False, max_length=160, widget=forms.TextInput(attrs={"class": "control"}))
    payment_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "control"}))
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3, "class": "control"}))

    def clean(self):
        cleaned = super().clean()
        method = cleaned.get("payment_method")
        reference = (cleaned.get("payment_reference") or "").strip()
        if method and method != Expense.Method.CASH and not reference:
            self.add_error("payment_reference", "Non-cash payments require a transaction/reference number.")
        cleaned["payment_reference"] = reference
        return cleaned


class ExpenseActionForm(forms.Form):
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2, "class": "control"}))
