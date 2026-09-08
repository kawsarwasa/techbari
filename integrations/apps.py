from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "integrations"
    verbose_name = "Notifications & Integrations"

    def ready(self):
        from . import signals  # noqa: F401
