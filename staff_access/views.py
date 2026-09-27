import time
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import Group, User
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from backoffice.context import page_context
from .forms import MFAChallengeForm, MFASetupConfirmForm, MFASetupStartForm, RoleCreateForm, RolePermissionForm, StaffPasswordResetForm, StaffUserForm
from .mfa import (
    decrypt_secret,
    enable_mfa,
    get_or_create_mfa_device,
    mfa_enabled,
    qr_svg_bytes,
    reset_mfa,
    verify_mfa_code,
)
from .models import AuditLog
from .permissions import SYSTEM_ROLE_NAMES, staff_permissions_queryset, staff_role_groups_queryset, sync_system_roles
from .security import clear_auth_throttle, register_auth_failure, throttle_seconds_remaining
from .services import ensure_profile, record_audit, user_role


def _staff_users():
    return User.objects.filter(Q(is_staff=True) | Q(is_superuser=True) | Q(groups__name__in=SYSTEM_ROLE_NAMES)).distinct()



class StaffPasswordResetView(auth_views.PasswordResetView):
    form_class = StaffPasswordResetForm

    def post(self, request, *args, **kwargs):
        identity = str(request.POST.get("email") or "").strip().lower()
        ip_limited = throttle_seconds_remaining("staff_password_reset_ip", request, "*")
        identity_limited = throttle_seconds_remaining("staff_password_reset", request, identity)
        if ip_limited or identity_limited:
            record_audit(
                request,
                AuditLog.Action.LOGIN_FAILED,
                summary="Staff password reset request rate limited",
                status_code=429,
            )
            return redirect(self.get_success_url())

        # Count reset requests regardless of whether an account exists so the
        # endpoint never becomes an account-enumeration side channel.
        register_auth_failure("staff_password_reset_ip", request, "*")
        register_auth_failure("staff_password_reset", request, identity)
        return super().post(request, *args, **kwargs)

MFA_PREAUTH_KEYS = (
    "staff_mfa_preauth_user_id",
    "staff_mfa_preauth_backend",
    "staff_mfa_preauth_next",
    "staff_mfa_preauth_at",
)


def _safe_next_url(request, value):
    target = value or reverse("backoffice:dashboard")
    if not url_has_allowed_host_and_scheme(
        target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return reverse("backoffice:dashboard")
    return target


def _clear_mfa_preauth(request):
    for key in MFA_PREAUTH_KEYS:
        request.session.pop(key, None)


def _mfa_preauth_user(request):
    user_id = request.session.get("staff_mfa_preauth_user_id")
    started = request.session.get("staff_mfa_preauth_at")
    try:
        fresh = user_id and started and (
            int(time.time()) - int(started) <= int(getattr(settings, "STAFF_MFA_PREAUTH_TTL", 300))
        )
    except (TypeError, ValueError):
        fresh = False
    if not fresh:
        _clear_mfa_preauth(request)
        return None
    user = User.objects.filter(pk=user_id, is_active=True).first()
    if user is None or not (user.is_staff or user.is_superuser) or not mfa_enabled(user):
        _clear_mfa_preauth(request)
        return None
    return user


def login_view(request):
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        return redirect("backoffice:dashboard")
    error = ""
    if request.method == "POST":
        identity = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        wait_seconds = throttle_seconds_remaining("staff_login", request, identity)
        if wait_seconds:
            record_audit(request, AuditLog.Action.LOGIN_FAILED, summary="Staff login rate limited", status_code=429)
            error = "Too many sign-in attempts. Try again later."
        else:
            username = identity
            if "@" in identity:
                matches = _staff_users().filter(email__iexact=identity, is_active=True)[:2]
                if len(matches) == 1:
                    username = matches[0].username
            user = authenticate(request, username=username, password=password)
            if user is not None and user.is_active and (user.is_staff or user.is_superuser):
                clear_auth_throttle("staff_login", request, identity)
                ensure_profile(user)
                next_url = _safe_next_url(
                    request,
                    request.POST.get("next") or request.GET.get("next"),
                )
                if mfa_enabled(user):
                    request.session.cycle_key()
                    request.session["staff_mfa_preauth_user_id"] = user.pk
                    request.session["staff_mfa_preauth_backend"] = getattr(
                        user,
                        "backend",
                        "django.contrib.auth.backends.ModelBackend",
                    )
                    request.session["staff_mfa_preauth_next"] = next_url
                    request.session["staff_mfa_preauth_at"] = int(time.time())
                    return redirect("backoffice:mfa_challenge")

                login(request, user)
                request.session["staff_last_activity"] = int(time.time())
                record_audit(request, AuditLog.Action.LOGIN, user=user, summary="Staff login successful")
                return redirect(next_url)
            register_auth_failure("staff_login", request, identity)
            record_audit(request, AuditLog.Action.LOGIN_FAILED, summary=f"Failed staff login for {identity[:120]}", status_code=401)
            error = "Invalid username/email or password."
    return render(request, "backoffice/auth/login.html", {"error_message": error, "next": request.GET.get("next", "")})


def mfa_challenge(request):
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        return redirect("backoffice:dashboard")

    user = _mfa_preauth_user(request)
    if user is None:
        return redirect("backoffice:login")

    form = MFAChallengeForm(request.POST or None)
    wait_seconds = throttle_seconds_remaining("staff_mfa", request, str(user.pk))
    if request.method == "POST":
        if wait_seconds:
            form.add_error(None, "Too many verification attempts. Try again later.")
            record_audit(
                request,
                AuditLog.Action.LOGIN_FAILED,
                summary="Staff MFA challenge rate limited",
                status_code=429,
            )
        elif form.is_valid():
            verified, method = verify_mfa_code(user, form.cleaned_data["code"])
            if verified:
                clear_auth_throttle("staff_mfa", request, str(user.pk))
                next_url = _safe_next_url(
                    request,
                    request.session.get("staff_mfa_preauth_next"),
                )
                backend = request.session.get(
                    "staff_mfa_preauth_backend",
                    "django.contrib.auth.backends.ModelBackend",
                )
                _clear_mfa_preauth(request)
                login(request, user, backend=backend)
                request.session["staff_mfa_verified_user_id"] = user.pk
                request.session["staff_last_activity"] = int(time.time())
                record_audit(
                    request,
                    AuditLog.Action.LOGIN,
                    user=user,
                    summary=f"Staff login successful with MFA ({method})",
                )
                return redirect(next_url)

            register_auth_failure("staff_mfa", request, str(user.pk))
            record_audit(
                request,
                AuditLog.Action.LOGIN_FAILED,
                user=user,
                summary="Invalid staff MFA challenge",
                status_code=401,
            )
            form.add_error("code", "Invalid or already-used verification code.")

    return render(
        request,
        "backoffice/auth/mfa_challenge.html",
        {"form": form, "staff_user": user},
    )


MFA_SETUP_REAUTH_SESSION_KEY = "staff_mfa_setup_reauth_at"


def _mfa_setup_reauthenticated(request):
    started = request.session.get(MFA_SETUP_REAUTH_SESSION_KEY)
    try:
        return bool(started) and int(time.time()) - int(started) <= 300
    except (TypeError, ValueError):
        return False


def mfa_setup(request):
    existing = getattr(request.user, "staff_mfa", None)
    if existing and existing.is_enabled:
        return render(
            request,
            "backoffice/auth/mfa_setup.html",
            {
                "mfa_enabled": True,
                "recovery_codes_remaining": len(existing.recovery_code_hashes or []),
                "mfa_required": bool(getattr(settings, "STAFF_MFA_REQUIRED", False)),
            },
        )

    authorized = _mfa_setup_reauthenticated(request)
    start_form = MFASetupStartForm()
    confirm_form = MFASetupConfirmForm()

    if request.method == "POST" and request.POST.get("action") == "reauth":
        start_form = MFASetupStartForm(request.POST)
        if start_form.is_valid():
            if not request.user.check_password(start_form.cleaned_data["password"]):
                start_form.add_error("password", "Your current password is incorrect.")
            else:
                request.session[MFA_SETUP_REAUTH_SESSION_KEY] = int(time.time())
                get_or_create_mfa_device(request.user)
                return redirect("backoffice:mfa_setup")

    elif request.method == "POST" and request.POST.get("action") == "enable":
        if not authorized:
            messages.error(request, "Re-enter your password before configuring two-factor authentication.")
            return redirect("backoffice:mfa_setup")
        confirm_form = MFASetupConfirmForm(request.POST)
        if confirm_form.is_valid():
            recovery_codes = enable_mfa(request.user, confirm_form.cleaned_data["code"])
            if recovery_codes is None:
                confirm_form.add_error("code", "The authenticator code is invalid or expired.")
            else:
                request.session.pop(MFA_SETUP_REAUTH_SESSION_KEY, None)
                request.session["staff_mfa_verified_user_id"] = request.user.pk
                request.session["staff_mfa_new_recovery_codes"] = recovery_codes
                record_audit(
                    request,
                    AuditLog.Action.UPDATE,
                    object_type="StaffMFA",
                    object_id=request.user.pk,
                    summary="Staff MFA enabled",
                )
                messages.success(request, "Two-factor authentication is now enabled.")
                return redirect("backoffice:mfa_recovery_codes")

    context = {
        "mfa_enabled": False,
        "mfa_required": bool(getattr(settings, "STAFF_MFA_REQUIRED", False)),
        "mfa_setup_authorized": authorized,
        "start_form": start_form,
        "confirm_form": confirm_form,
    }
    if authorized:
        device = get_or_create_mfa_device(request.user)
        context["mfa_secret"] = decrypt_secret(device)
    return render(request, "backoffice/auth/mfa_setup.html", context)


def mfa_qr(request):
    if not _mfa_setup_reauthenticated(request):
        return HttpResponseForbidden("Re-enter your password before viewing the MFA setup QR code.")
    device = get_or_create_mfa_device(request.user)
    if device.is_enabled:
        raise Http404("MFA setup QR is no longer available.")
    response = HttpResponse(qr_svg_bytes(request.user, device), content_type="image/svg+xml")
    response["Cache-Control"] = "no-store, private"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def mfa_recovery_codes(request):
    codes = request.session.pop("staff_mfa_new_recovery_codes", None)
    if not codes:
        messages.info(request, "Recovery codes are only displayed once, immediately after MFA setup.")
        return redirect("backoffice:mfa_setup")
    response = render(
        request,
        "backoffice/auth/mfa_recovery_codes.html",
        {"recovery_codes": codes},
    )
    response["Cache-Control"] = "no-store, private"
    return response


@require_POST
def logout_view(request):
    if request.user.is_authenticated:
        record_audit(request, AuditLog.Action.LOGOUT, summary="Staff logout")
    logout(request)
    return redirect("backoffice:login")


def users(request):
    qs = _staff_users().prefetch_related("groups", "user_permissions").select_related("staff_profile", "staff_mfa").order_by("username")
    q = request.GET.get("q", "").strip()
    role = request.GET.get("role", "").strip()
    status = request.GET.get("status", "").strip()
    role_groups = staff_role_groups_queryset().order_by("name")
    role_names = list(role_groups.values_list("name", flat=True))
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q))
    if role and role in role_names:
        qs = qs.filter(groups__name=role)
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)
    qs = qs.distinct()
    page = Paginator(qs, 20).get_page(request.GET.get("page"))
    rows = []
    for user in page.object_list:
        profile = ensure_profile(user)
        rows.append({"user": user, "role": user_role(user), "branch": profile.branch, "extra_permissions": user.user_permissions.filter(content_type__app_label="staff_access").count(), "mfa_enabled": bool(getattr(user, "staff_mfa", None) and user.staff_mfa.is_enabled)})
    base_staff = _staff_users()
    context = page_context("users")
    context.update(
        user_rows=rows,
        user_page=page,
        role_choices=role_names,
        q=q,
        role_filter=role,
        status_filter=status,
        user_kpis={
            "total": base_staff.count(),
            "active": base_staff.filter(is_active=True).count(),
            "roles": role_groups.count(),
            "admins": base_staff.filter(Q(is_superuser=True) | Q(groups__name="Admin")).distinct().count(),
        },
    )
    return render(request, "backoffice/pages/users/users.html", context)


def user_form(request, user_id=None):
    instance = get_object_or_404(_staff_users(), pk=user_id) if user_id else None
    if instance and instance.is_superuser and not request.user.is_superuser:
        record_audit(
            request,
            AuditLog.Action.DENIED,
            status_code=403,
            object_type="User",
            object_id=instance.pk,
            summary="Non-superuser denied editing a superuser account",
        )
        return HttpResponseForbidden("Only a superuser can edit another superuser account.")
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
    target = get_object_or_404(_staff_users(), pk=user_id)
    if target.is_superuser and not request.user.is_superuser:
        record_audit(
            request,
            AuditLog.Action.DENIED,
            status_code=403,
            object_type="User",
            object_id=target.pk,
            summary="Non-superuser denied toggling a superuser account",
        )
        return HttpResponseForbidden("Only a superuser can change another superuser account.")
    if target.pk == request.user.pk and target.is_active:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect("backoffice:users")
    target.is_active = not target.is_active
    target.save(update_fields=["is_active"])
    record_audit(request, AuditLog.Action.UPDATE, object_type="User", object_id=target.pk, summary=f"Set {target.username} active={target.is_active}")
    return redirect("backoffice:users")


@require_POST
def user_mfa_reset(request, user_id):
    if not request.user.is_superuser:
        record_audit(
            request,
            AuditLog.Action.DENIED,
            status_code=403,
            object_type="StaffMFA",
            object_id=user_id,
            summary="Non-superuser denied staff MFA reset",
        )
        return HttpResponseForbidden("Only a superuser can reset staff MFA.")
    target = get_object_or_404(_staff_users(), pk=user_id)
    if target.pk == request.user.pk:
        messages.error(
            request,
            "You cannot reset your own MFA from the dashboard. Use the emergency management command if recovery is required.",
        )
        return redirect("backoffice:users")
    reset_mfa(target)
    record_audit(
        request,
        AuditLog.Action.UPDATE,
        object_type="StaffMFA",
        object_id=target.pk,
        summary=f"MFA reset for staff user {target.username}",
    )
    messages.success(
        request,
        f"MFA reset for {target.username}. The user must enroll again before dashboard access when MFA is required.",
    )
    return redirect("backoffice:users")


def roles(request):
    sync_system_roles()
    groups = staff_role_groups_queryset().prefetch_related("permissions").order_by("name")
    role_rows = [
        {
            "group": group,
            "staff_count": group.user_set.filter(is_staff=True).count(),
            "permission_count": group.permissions.filter(content_type__app_label="staff_access").count(),
            "is_system": group.name in SYSTEM_ROLE_NAMES,
        }
        for group in groups
    ]
    context = page_context("users")
    context.update(
        role_rows=role_rows,
        permission_total=staff_permissions_queryset().count(),
        system_role_count=sum(1 for row in role_rows if row["is_system"]),
        custom_role_count=sum(1 for row in role_rows if not row["is_system"]),
    )
    return render(request, "backoffice/pages/users/roles.html", context)


def role_add(request):
    form = RoleCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        group = form.save()
        record_audit(request, AuditLog.Action.CREATE, object_type="Role", object_id=group.pk, summary=f"Custom role {group.name} created")
        messages.success(request, f"Role {group.name} created successfully.")
        return redirect("backoffice:roles")
    context = page_context("users")
    context.update(form=form, permission_total=staff_permissions_queryset().count())
    return render(request, "backoffice/pages/users/role_add.html", context)


def role_edit(request, role_id):
    group = get_object_or_404(staff_role_groups_queryset(), pk=role_id)
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
        profile = ensure_profile(user)
        if profile.force_password_change:
            profile.force_password_change = False
            profile.save(update_fields=["force_password_change", "updated_at"])
        record_audit(request, AuditLog.Action.PASSWORD, object_type="User", object_id=user.pk, summary="Password changed by user")
        messages.success(request, "Password changed successfully.")
        return redirect("backoffice:password_change_done")
    return render(request, "backoffice/auth/password_change.html", {"form": form})


def password_change_done(request):
    return render(request, "backoffice/auth/password_change_done.html")
