from django.conf import settings
from django.db import models

from .permissions import ACCESS_PERMISSIONS


class StaffProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_profile")
    phone = models.CharField(max_length=32, blank=True)
    branch = models.CharField(max_length=120, blank=True, default="Main Branch")
    force_password_change = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        permissions = ACCESS_PERMISSIONS
        indexes = [models.Index(fields=("branch",), name="staff_profile_branch_idx")]

    def __str__(self):
        return self.user.get_full_name() or self.user.get_username()


class AuditLog(models.Model):
    class Action(models.TextChoices):
        LOGIN = "login", "Login"
        LOGIN_FAILED = "login_failed", "Login Failed"
        LOGOUT = "logout", "Logout"
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        DELETE = "delete", "Delete"
        MUTATE = "mutate", "Change"
        DENIED = "denied", "Permission Denied"
        PASSWORD = "password", "Password Change"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="staff_audit_logs")
    username_snapshot = models.CharField(max_length=150, blank=True)
    role_snapshot = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=24, choices=Action.choices)
    method = models.CharField(max_length=10, blank=True)
    path = models.CharField(max_length=500, blank=True)
    route_name = models.CharField(max_length=160, blank=True)
    status_code = models.PositiveSmallIntegerField(default=200)
    object_type = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=100, blank=True)
    summary = models.CharField(max_length=500, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=("created_at",), name="staff_audit_created_idx"),
            models.Index(fields=("action", "created_at"), name="staff_audit_action_idx"),
            models.Index(fields=("user", "created_at"), name="staff_audit_user_idx"),
        ]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.username_snapshot or 'anonymous'} {self.action}"
