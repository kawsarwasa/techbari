from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import Group, User
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from backoffice.context import page_context
from .forms import RolePermissionForm, StaffUserForm
from .models import AuditLog
from .permissions import SYSTEM_ROLE_NAMES, staff_permissions_queryset, sync_system_roles
from .services import ensure_profile, record_audit, user_role


def login_view(request):
    if request.user.is_authenticated:
        return redirect("backoffice:dashboard")
    error = ""
    if request.method == "POST":
        identity = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        username = identity
        if "@" in identity:
            matches = User.objects.filter(email__iexact=identity, is_active=True)[:2]
            if len(matches) == 1:
                username = matches[0].username
        user = authenticate(request, username=username, password=password)
        if user is not None and user.is_active:
            login(request, user)
            request.session["staff_last_activity"] = int(__import__("time").time())
            ensure_profile(user)
            record_audit(request, AuditLog.Action.LOGIN, user=user, summary="Staff login successful")
            next_url = request.POST.get("next") or request.GET.get("next") or reverse("backoffice:dashboard")
            if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
                next_url = reverse("backoffice:dashboard")
            return redirect(next_url)
        record_audit(request, AuditLog.Action.LOGIN_FAILED, summary=f"Failed login for {identity[:120]}", status_code=401)
        error = "Invalid username/email or password."
    return render(request, "backoffice/auth/login.html", {"error_message": error, "next": request.GET.get("next", "")})


@require_POST
def logout_view(request):
    if request.user.is_authenticated:
        record_audit(request, AuditLog.Action.LOGOUT, summary="Staff logout")
    logout(request)
    return redirect("backoffice:login")


def users(request):
    qs = User.objects.prefetch_related("groups", "user_permissions").select_related("staff_profile").order_by("username")
    q = request.GET.get("q", "").strip()
    role = request.GET.get("role", "").strip()
    status = request.GET.get("status", "").strip()
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q))
    if role in SYSTEM_ROLE_NAMES:
        qs = qs.filter(groups__name=role)
    if status == "active": qs = qs.filter(is_active=True)
    elif status == "inactive": qs = qs.filter(is_active=False)
    qs = qs.distinct()
    page = Paginator(qs, 20).get_page(request.GET.get("page"))
    rows = []
    for user in page.object_list:
        profile = ensure_profile(user)
        rows.append({"user": user, "role": user_role(user), "branch": profile.branch, "extra_permissions": user.user_permissions.filter(content_type__app_label="staff_access").count()})
    context = page_context("users")
    context.update(user_rows=rows, user_page=page, role_choices=SYSTEM_ROLE_NAMES, q=q, role_filter=role, status_filter=status,
                   user_kpis={"total": User.objects.count(), "active": User.objects.filter(is_active=True).count(), "roles": Group.objects.filter(name__in=SYSTEM_ROLE_NAMES).count(), "admins": User.objects.filter(Q(is_superuser=True) | Q(groups__name="Admin")).distinct().count()})
    return render(request, "backoffice/pages/users/users.html", context)


def user_form(request, user_id=None):
    instance = get_object_or_404(User, pk=user_id) if user_id else None
    form = StaffUserForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        record_audit(request, AuditLog.Action.UPDATE if instance else AuditLog.Action.CREATE, object_type="User", object_id=user.pk, summary=f"Staff user {user.username} saved")
        messages.success(request, f"User {user.username} saved successfully.")
        return redirect("backoffice:users")
    context = page_context("user_add")
    context.update(form=form, edited_user=instance, page_title="Edit User" if instance else "Add User")
    return render(request, "backoffice/pages/users/user_add.html", context)


@require_POST
def user_toggle(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    if target.pk == request.user.pk and target.is_active:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect("backoffice:users")
    target.is_active = not target.is_active
    target.save(update_fields=["is_active"])
    record_audit(request, AuditLog.Action.UPDATE, object_type="User", object_id=target.pk, summary=f"Set {target.username} active={target.is_active}")
    return redirect("backoffice:users")


def roles(request):
    sync_system_roles()
    groups = Group.objects.filter(name__in=SYSTEM_ROLE_NAMES).prefetch_related("permissions").order_by("name")
    role_rows = [{"group": group, "staff_count": group.user_set.count(), "permission_count": group.permissions.filter(content_type__app_label="staff_access").count()} for group in groups]
    context = page_context("users")
    context.update(role_rows=role_rows, permission_total=staff_permissions_queryset().count())
    return render(request, "backoffice/pages/users/roles.html", context)


def role_edit(request, role_id):
    group = get_object_or_404(Group, pk=role_id, name__in=SYSTEM_ROLE_NAMES)
    if group.name == "Admin":
        messages.info(request, "Admin is a protected system role and always keeps every TechBari permission.")
        return redirect("backoffice:roles")
    form = RolePermissionForm(request.POST or None, group=group)
    if request.method == "POST" and form.is_valid():
        form.save()
        record_audit(request, AuditLog.Action.UPDATE, object_type="Role", object_id=group.pk, summary=f"Permissions updated for {group.name}")
        messages.success(request, f"Permissions updated for {group.name}.")
        return redirect("backoffice:roles")
    context = page_context("users")
    context.update(role_group=group, form=form)
    return render(request, "backoffice/pages/users/role_edit.html", context)


def audit_log(request):
    qs = AuditLog.objects.select_related("user").all()
    q = request.GET.get("q", "").strip()
    action = request.GET.get("action", "").strip()
    if q:
        qs = qs.filter(Q(username_snapshot__icontains=q) | Q(summary__icontains=q) | Q(path__icontains=q) | Q(ip_address__icontains=q))
    if action in AuditLog.Action.values:
        qs = qs.filter(action=action)
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    context = page_context("audit_log")
    context.update(audit_page=page, action_choices=AuditLog.Action.choices, q=q, action_filter=action)
    return render(request, "backoffice/pages/audit/audit_log.html", context)


def password_change(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        record_audit(request, AuditLog.Action.PASSWORD, object_type="User", object_id=user.pk, summary="Password changed by user")
        messages.success(request, "Password changed successfully.")
        return redirect("backoffice:password_change_done")
    return render(request, "backoffice/auth/password_change.html", {"form": form})


def password_change_done(request):
    return render(request, "backoffice/auth/password_change_done.html")
