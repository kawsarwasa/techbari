from django.apps import AppConfig


class SerialTrackingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "serial_tracking"
    verbose_name = "Serial / IMEI / Warranty Tracking"
