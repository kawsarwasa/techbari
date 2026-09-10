from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.models import Group, Permission, User

from .permissions import SYSTEM_ROLE_NAMES, staff_permissions_queryset, staff_role_groups_queryset
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


def build_permission_groups(permissions, selected_ids=None):
    selected_ids = {str(value) for value in (selected_ids or set())}
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
        role_qs = staff_role_groups_queryset().order_by("name")
        self.fields["role"].queryset = role_qs
        self.fields["extra_permissions"].queryset = staff_permissions_queryset().order_by("codename")
        if self.instance and self.instance.pk:
            role = self.instance.groups.filter(pk__in=role_qs.values("pk")).order_by("name").first()
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
        return build_permission_groups(list(self.fields["extra_permissions"].queryset), self._selected_extra_permission_ids())

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


class RoleCreateForm(forms.Form):
    name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={"class": "control", "placeholder": "e.g. Store Manager", "autocomplete": "off"}),
        label="Role name",
    )
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.none(), required=False, widget=forms.CheckboxSelectMultiple
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["permissions"].queryset = staff_permissions_queryset().order_by("codename")
        selected_ids = set()
        if self.is_bound:
            selected_ids = {str(value) for value in self.data.getlist(self.add_prefix("permissions"))}
        self.permission_groups = build_permission_groups(list(self.fields["permissions"].queryset), selected_ids)
        self.permission_total = self.fields["permissions"].queryset.count()

    def clean_name(self):
        name = " ".join((self.cleaned_data.get("name") or "").split())
        if not name:
            raise forms.ValidationError("Role name is required.")
        if Group.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError("A role with this name already exists.")
        return name

    def clean_permissions(self):
        permissions = self.cleaned_data.get("permissions")
        if not permissions:
            raise forms.ValidationError("Select at least one permission for this role.")
        return permissions

    def save(self):
        group = Group.objects.create(name=self.cleaned_data["name"])
        group.permissions.set(self.cleaned_data["permissions"])
        return group


class RolePermissionForm(forms.Form):
    name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": "control", "autocomplete": "off"}),
        label="Role name",
    )
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.none(), required=False, widget=forms.CheckboxSelectMultiple
    )

    def __init__(self, *args, group=None, **kwargs):
        self.group = group
        super().__init__(*args, **kwargs)
        self.fields["permissions"].queryset = staff_permissions_queryset().order_by("codename")
        self.permission_total = self.fields["permissions"].queryset.count()
        selected_ids = set()
        if group:
            self.fields["name"].initial = group.name
            if group.name in SYSTEM_ROLE_NAMES:
                self.fields["name"].disabled = True
            initial_permissions = group.permissions.filter(
                content_type__app_label="staff_access", content_type__model="staffprofile"
            )
            self.fields["permissions"].initial = initial_permissions
            selected_ids = {str(value) for value in initial_permissions.values_list("pk", flat=True)}
        if self.is_bound:
            selected_ids = {str(value) for value in self.data.getlist(self.add_prefix("permissions"))}
        self.permission_groups = build_permission_groups(list(self.fields["permissions"].queryset), selected_ids)

    def clean_name(self):
        if not self.group:
            return ""
        if self.group.name in SYSTEM_ROLE_NAMES:
            return self.group.name
        name = " ".join((self.cleaned_data.get("name") or "").split())
        if not name:
            raise forms.ValidationError("Role name is required.")
        if Group.objects.filter(name__iexact=name).exclude(pk=self.group.pk).exists():
            raise forms.ValidationError("A role with this name already exists.")
        return name

    def clean_permissions(self):
        permissions = self.cleaned_data.get("permissions")
        if self.group and self.group.name not in SYSTEM_ROLE_NAMES and not permissions:
            raise forms.ValidationError("Custom roles must keep at least one permission.")
        return permissions

    def save(self):
        if self.group.name not in SYSTEM_ROLE_NAMES:
            new_name = self.cleaned_data.get("name")
            if new_name and new_name != self.group.name:
                self.group.name = new_name
                self.group.save(update_fields=["name"])
        self.group.permissions.set(self.cleaned_data["permissions"])
        return self.group
