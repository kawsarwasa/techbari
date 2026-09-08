from django.apps import AppConfig
from django.db.models.signals import post_migrate


class StaffAccessConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "staff_access"
    verbose_name = "Staff Access Control"

    def ready(self):
        from .permissions import sync_system_roles
        post_migrate.connect(sync_system_roles, sender=self, dispatch_uid="staff_access.sync_system_roles")
