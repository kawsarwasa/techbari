from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.models import Group, Permission, User

from .permissions import SYSTEM_ROLE_NAMES, staff_permissions_queryset
from .services import assign_system_role, ensure_profile


CONTROL = {"class": "control"}

EXTRA_PERMISSION_GROUPS = (
    ("overview", "Dashboard & Notifications", ("view_dashboard", "view_notifications")),
    ("catalog", "Catalog & Products", ("view_catalog", "manage_catalog")),
    ("inventory", "Inventory & Serial / IMEI", ("view_inventory", "manage_inventory", "adjust_inventory", "view_serial", "manage_serial")),
    ("purchasing", "Purchasing", ("view_purchasing", "manage_purchasing")),
    ("customers", "Customers", ("view_customers", "manage_customers")),
    ("sales", "Sales & POS", ("view_sales", "manage_sales", "use_pos")),
    ("payments", "Payments", ("view_payments", "manage_payments")),
    ("shipping", "Shipping & COD", ("view_shipping", "manage_shipping")),
    ("returns", "Returns & Warranty", ("view_returns", "manage_returns")),
    ("accounting", "Accounting", ("view_accounting", "manage_accounting", "manage_accounting_settings")),
    ("expenses", "Expenses", ("view_expenses", "manage_expenses", "approve_expenses")),
    ("reports", "Reports", ("view_reports",)),
    ("marketing", "Marketing", ("view_marketing", "manage_marketing")),
    ("integrations", "Integrations & Notifications", ("manage_integrations",)),
    ("settings", "Store Settings", ("manage_store_settings",)),
    ("users", "Users & Security", ("view_users", "manage_users", "view_audit_log")),
)


class StaffUserForm(forms.ModelForm):
    role = forms.ModelChoiceField(queryset=Group.objects.none(), widget=forms.Select(attrs=CONTROL))
    branch = forms.CharField(max_length=120, required=False, widget=forms.TextInput(attrs=CONTROL))
    phone = forms.CharField(max_length=32, required=False, widget=forms.TextInput(attrs=CONTROL))
    password1 = forms.CharField(required=False, widget=forms.PasswordInput(attrs=CONTROL), label="New password")
    password2 = forms.CharField(required=False, widget=forms.PasswordInput(attrs=CONTROL), label="Confirm password")
    extra_permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.none(), required=False, widget=forms.CheckboxSelectMultiple, label="Extra user permissions"
    )

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "is_active")
        widgets = {
            "username": forms.TextInput(attrs=CONTROL),
            "first_name": forms.TextInput(attrs=CONTROL),
            "last_name": forms.TextInput(attrs=CONTROL),
            "email": forms.EmailInput(attrs=CONTROL),
            "is_active": forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].queryset = Group.objects.filter(name__in=SYSTEM_ROLE_NAMES).order_by("name")
        self.fields["extra_permissions"].queryset = staff_permissions_queryset().order_by("codename")
        if self.instance and self.instance.pk:
            role = self.instance.groups.filter(name__in=SYSTEM_ROLE_NAMES).first()
            if role:
                self.fields["role"].initial = role.pk
            profile = ensure_profile(self.instance)
            self.fields["branch"].initial = profile.branch
            self.fields["phone"].initial = profile.phone
            self.fields["extra_permissions"].initial = self.instance.user_permissions.filter(
                content_type__app_label="staff_access", content_type__model="staffprofile"
            )
        self.permission_groups = self._build_permission_groups()

    def _selected_extra_permission_ids(self):
        if self.is_bound:
            field_name = self.add_prefix("extra_permissions")
            return {str(value) for value in self.data.getlist(field_name)}

        initial = self.fields["extra_permissions"].initial
        if initial is None:
            return set()
        if hasattr(initial, "values_list"):
            return {str(value) for value in initial.values_list("pk", flat=True)}

        selected = set()
        for value in initial:
            selected.add(str(getattr(value, "pk", value)))
        return selected

    def _build_permission_groups(self):
        selected_ids = self._selected_extra_permission_ids()
        permissions = list(self.fields["extra_permissions"].queryset)
        by_codename = {permission.codename: permission for permission in permissions}
        used = set()
        groups = []

        for key, name, codenames in EXTRA_PERMISSION_GROUPS:
            items = []
            for codename in codenames:
                permission = by_codename.get(codename)
                if not permission:
                    continue
                used.add(permission.pk)
                items.append(
                    {
                        "id": permission.pk,
                        "codename": permission.codename,
                        "label": permission.name,
                        "checked": str(permission.pk) in selected_ids,
                    }
                )
            if items:
                groups.append({"key": key, "name": name, "permissions": items})

        other_items = [
            {
                "id": permission.pk,
                "codename": permission.codename,
                "label": permission.name,
                "checked": str(permission.pk) in selected_ids,
            }
            for permission in permissions
            if permission.pk not in used
        ]
        if other_items:
            groups.append({"key": "other", "name": "Other Access", "permissions": other_items})
        return groups

    def clean_email(self):
        email = self.cleaned_data.get("email", "").strip().lower()
        if not email:
            raise forms.ValidationError("Email is required.")
        qs = User.objects.filter(email__iexact=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A staff user with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if not self.instance.pk and not p1:
            self.add_error("password1", "Password is required for a new user.")
        if p1 or p2:
            if p1 != p2:
                self.add_error("password2", "Passwords do not match.")
            elif p1:
                password_validation.validate_password(p1, self.instance)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = True
        password = self.cleaned_data.get("password1")
        if password:
            user.set_password(password)
        if commit:
            user.save()
            assign_system_role(user, self.cleaned_data.get("role"))
            user.user_permissions.set(self.cleaned_data.get("extra_permissions"))
            profile = ensure_profile(user)
            profile.branch = self.cleaned_data.get("branch", "") or "Main Branch"
            profile.phone = self.cleaned_data.get("phone", "")
            profile.save(update_fields=["branch", "phone", "updated_at"])
        return user


class RolePermissionForm(forms.Form):
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.none(), required=False, widget=forms.CheckboxSelectMultiple
    )

    def __init__(self, *args, group=None, **kwargs):
        self.group = group
        super().__init__(*args, **kwargs)
        self.fields["permissions"].queryset = staff_permissions_queryset().order_by("codename")
        if group:
            self.fields["permissions"].initial = group.permissions.filter(
                content_type__app_label="staff_access", content_type__model="staffprofile"
            )

    def save(self):
        self.group.permissions.set(self.cleaned_data["permissions"])
        return self.group
