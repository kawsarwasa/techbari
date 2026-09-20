from decimal import Decimal

from django import forms

from accounting.models import Account

from .models import CashbookEntry, CashbookSettlement, Expense, ExpenseCategory


ALLOWED_ATTACHMENT_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}
MAX_ATTACHMENT_SIZE = 5 * 1024 * 1024


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
            "attachment",
            "notes",
        ]
        widgets = {
            "expense_date": forms.DateInput(attrs={"type": "date"}),
            "amount": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "description": forms.TextInput(attrs={"placeholder": "What was this expense for?"}),
            "attachment": forms.ClearableFileInput(attrs={"accept": ".pdf,.jpg,.jpeg,.png,.webp"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = ExpenseCategory.objects.filter(is_active=True, entry_type=ExpenseCategory.EntryType.EXPENSE).select_related("account")
        self.fields["preferred_payment_method"].required = False
        self.fields["attachment"].required = False
        self._style()

    def clean_attachment(self):
        attachment = self.cleaned_data.get("attachment")
        if not attachment:
            return attachment
        name = str(getattr(attachment, "name", "")).lower()
        if not any(name.endswith(ext) for ext in ALLOWED_ATTACHMENT_EXTENSIONS):
            raise forms.ValidationError("Attachment must be PDF, JPG, JPEG, PNG or WebP.")
        if getattr(attachment, "size", 0) > MAX_ATTACHMENT_SIZE:
            raise forms.ValidationError("Attachment must be 5 MB or smaller.")
        return attachment


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
    payment_account = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        widget=forms.Select(attrs={"class": "control"}),
        help_text="Choose the exact Cash / Bank / Card / MFS asset account used for this payment.",
    )
    payment_reference = forms.CharField(required=False, max_length=160, widget=forms.TextInput(attrs={"class": "control"}))
    payment_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "control"}))
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3, "class": "control"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["payment_account"].queryset = Account.objects.filter(
            account_type=Account.Type.ASSET,
            is_active=True,
            allow_manual_entries=True,
        ).order_by("code")

    def clean(self):
        cleaned = super().clean()
        method = cleaned.get("payment_method")
        account = cleaned.get("payment_account")
        reference = (cleaned.get("payment_reference") or "").strip()
        if method and method != Expense.Method.CASH and not reference:
            self.add_error("payment_reference", "Non-cash payments require a transaction/reference number.")
        if account and (account.account_type != Account.Type.ASSET or not account.is_active or not account.allow_manual_entries):
            self.add_error("payment_account", "Select an active cash/bank/payment Asset account.")
        cleaned["payment_reference"] = reference
        return cleaned


class ExpenseActionForm(forms.Form):
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2, "class": "control"}))


class CategorySelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        instance = getattr(value, "instance", None)
        if instance is not None:
            option["attrs"]["data-entry-type"] = instance.entry_type
        return option


class FriendlyAccountChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.name


class CashbookEntryForm(forms.ModelForm):
    entry_type = forms.ChoiceField(
        choices=CashbookEntry.EntryType.choices,
        initial=CashbookEntry.EntryType.EXPENSE,
        widget=forms.RadioSelect,
    )

    class SettlementStatus:
        PAID = "paid"
        DUE = "due"
        PARTIAL = "partial"
        choices = (
            (PAID, "Paid / Received"),
            (DUE, "Due"),
            (PARTIAL, "Partial"),
        )

    settlement_status = forms.ChoiceField(
        choices=SettlementStatus.choices,
        initial=SettlementStatus.PAID,
        widget=forms.RadioSelect,
    )
    initial_amount = forms.DecimalField(
        required=False,
        min_value=Decimal("0.01"),
        max_digits=18,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "control", "min": "0.01", "step": "0.01"}),
    )
    payment_account = FriendlyAccountChoiceField(
        required=False,
        queryset=Account.objects.none(),
        widget=forms.Select(attrs={"class": "control"}),
    )
    reference = forms.CharField(
        required=False,
        max_length=160,
        widget=forms.TextInput(attrs={"class": "control", "placeholder": "Optional reference / transaction ID"}),
    )

    class Meta:
        model = CashbookEntry
        fields = [
            "entry_type",
            "entry_date",
            "category",
            "amount",
            "counterparty",
            "description",
            "due_date",
            "attachment",
        ]
        widgets = {
            "entry_type": forms.RadioSelect,
            "entry_date": forms.DateInput(attrs={"type": "date"}),
            "category": CategorySelect(),
            "amount": forms.NumberInput(attrs={"min": "0.01", "step": "0.01", "placeholder": "0.00"}),
            "counterparty": forms.TextInput(attrs={"placeholder": "Person, shop or source (optional)"}),
            "description": forms.TextInput(attrs={"placeholder": "Short note (optional)"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "attachment": forms.ClearableFileInput(attrs={"accept": ".pdf,.jpg,.jpeg,.png,.webp"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = ExpenseCategory.objects.filter(is_active=True).select_related("account").order_by("entry_type", "sort_order", "name")
        self.fields["payment_account"].queryset = Account.objects.filter(
            account_type=Account.Type.ASSET,
            is_active=True,
            allow_manual_entries=True,
        ).order_by("code")
        self.fields["attachment"].required = False
        for field in self.fields.values():
            if not isinstance(field.widget, forms.RadioSelect):
                existing = field.widget.attrs.get("class", "")
                field.widget.attrs["class"] = (existing + " control").strip()

    def clean_attachment(self):
        attachment = self.cleaned_data.get("attachment")
        if not attachment:
            return attachment
        name = str(getattr(attachment, "name", "")).lower()
        if not any(name.endswith(ext) for ext in ALLOWED_ATTACHMENT_EXTENSIONS):
            raise forms.ValidationError("Attachment must be PDF, JPG, JPEG, PNG or WebP.")
        if getattr(attachment, "size", 0) > MAX_ATTACHMENT_SIZE:
            raise forms.ValidationError("Attachment must be 5 MB or smaller.")
        return attachment

    def clean(self):
        cleaned = super().clean()
        entry_type = cleaned.get("entry_type")
        category = cleaned.get("category")
        amount = cleaned.get("amount")
        status = cleaned.get("settlement_status")
        initial_amount = cleaned.get("initial_amount") or Decimal("0.00")
        payment_account = cleaned.get("payment_account")

        if category and entry_type and category.entry_type != entry_type:
            self.add_error("category", "Choose a category that matches Income or Expense.")

        if status == self.SettlementStatus.DUE:
            cleaned["initial_amount"] = Decimal("0.00")
            cleaned["payment_account"] = None
            cleaned["reference"] = ""
        elif amount:
            if status == self.SettlementStatus.PAID:
                cleaned["initial_amount"] = amount
            elif status == self.SettlementStatus.PARTIAL:
                if initial_amount <= Decimal("0.00") or initial_amount >= amount:
                    self.add_error("initial_amount", "Partial amount must be greater than zero and less than the total.")
            if not payment_account:
                self.add_error("payment_account", "Choose where the money was paid from or received into.")

        return cleaned


class CashbookSettlementForm(forms.Form):
    amount = forms.DecimalField(
        min_value=Decimal("0.01"),
        max_digits=18,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "control", "min": "0.01", "step": "0.01"}),
    )
    payment_account = FriendlyAccountChoiceField(
        queryset=Account.objects.none(),
        widget=forms.Select(attrs={"class": "control"}),
    )
    settlement_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "class": "control"}))
    reference = forms.CharField(required=False, max_length=160, widget=forms.TextInput(attrs={"class": "control"}))
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3, "class": "control"}))

    def __init__(self, *args, entry=None, **kwargs):
        self.entry = entry
        super().__init__(*args, **kwargs)
        self.fields["payment_account"].queryset = Account.objects.filter(
            account_type=Account.Type.ASSET,
            is_active=True,
            allow_manual_entries=True,
        ).order_by("code")
        if entry and not self.is_bound:
            self.fields["amount"].initial = entry.due_amount

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if self.entry and amount > self.entry.due_amount:
            raise forms.ValidationError("Amount cannot be greater than the remaining due.")
        return amount


class SimpleCategoryForm(forms.Form):
    entry_type = forms.ChoiceField(
        choices=ExpenseCategory.EntryType.choices,
        widget=forms.RadioSelect,
    )
    name = forms.CharField(max_length=120, widget=forms.TextInput(attrs={"class": "control", "placeholder": "Example: Salary or Service Income"}))
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": "control", "rows": 3, "placeholder": "Optional"}))
