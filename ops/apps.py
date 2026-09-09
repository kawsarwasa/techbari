from django.apps import AppConfig


class OpsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ops"
    verbose_name = "Production Operations"

    def ready(self):
        from . import checks  # noqa: F401
