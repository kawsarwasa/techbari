from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "catalog"

    def ready(self):
        # Keep the runtime image-count limit aligned with the existing catalog
        # regression contract. Individual image files are still capped at 2 MB
        # by catalog.forms.validate_catalog_image().
        from . import forms, signals  # noqa: F401

        forms.MAX_PRODUCT_IMAGES = 8
