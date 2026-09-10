from django.conf import settings
from django.contrib.auth.models import Group

from .models import AuditLog, StaffProfile
from .permissions import staff_role_groups_queryset


def get_client_ip(request):
    remote = (request.META.get("REMOTE_ADDR", "") or "").strip()
    if getattr(settings, "TRUST_X_FORWARDED_FOR", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        value = forwarded.split(",")[0].strip() if forwarded else remote
        return value or None
    return remote or None


def user_role(user):
    if not getattr(user, "is_authenticated", False):
        return ""
    role_ids = staff_role_groups_queryset().values("pk")
    role = user.groups.filter(pk__in=role_ids).order_by("name").first()
    return role.name if role else ("Superuser" if user.is_superuser else "Unassigned")


def ensure_profile(user):
    profile, _ = StaffProfile.objects.get_or_create(user=user)
    return profile


def record_audit(request, action, *, user=None, status_code=200, object_type="", object_id="", summary="", route_name=""):
    actor = user if user is not None else getattr(request, "user", None)
    authenticated = actor is not None and getattr(actor, "is_authenticated", False)
    return AuditLog.objects.create(
        user=actor if authenticated else None,
        username_snapshot=actor.get_username() if authenticated else "",
        role_snapshot=user_role(actor) if authenticated else "",
        action=action,
        method=request.method,
        path=request.path[:500],
        route_name=(route_name or getattr(getattr(request, "resolver_match", None), "url_name", "") or "")[:160],
        status_code=status_code,
        object_type=object_type[:100],
        object_id=str(object_id)[:100],
        summary=summary[:500],
        ip_address=get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
    )


def assign_system_role(user, group):
    """Assign exactly one TechBari staff role, including custom roles."""
    current_roles = list(staff_role_groups_queryset().filter(user=user))
    if current_roles:
        user.groups.remove(*current_roles)
    if group:
        user.groups.add(group)
