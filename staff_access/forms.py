from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.models import Group, Permission, User

from .permissions import SYSTEM_ROLE_NAMES, staff_permissions_queryset
from .services import assign_system_role, ensure_profile


CONTROL = {"class": "control"}


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
