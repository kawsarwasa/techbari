import os

from django.conf import settings
from django.core.management import BaseCommand, CommandError, call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.utils import OperationalError, ProgrammingError


class Command(BaseCommand):
    help = "Run TechBari production-readiness checks without exposing secrets."

    def handle(self, *args, **options):
        self.stdout.write("Running Django deployment checks...")
        call_command("check", deploy=True)

        errors = []
        warnings = []

        try:
            connection.ensure_connection()
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            executor = MigrationExecutor(connection)
            pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
            if pending:
                errors.append(f"{len(pending)} database migration(s) are pending.")
        except (OperationalError, ProgrammingError) as exc:
            errors.append(f"Database readiness check failed: {exc.__class__.__name__}.")

        if settings.DEBUG:
            errors.append("DJANGO_DEBUG must be 0.")
        if not getattr(settings, "STAFF_AUTH_ENABLED", True):
            errors.append("STAFF_AUTH_ENABLED must be enabled.")

        try:
            from integrations.models import IntegrationSettings
            config = IntegrationSettings.objects.first()
            if config:
                if config.meta_capi_enabled:
                    if not os.getenv("META_CAPI_ACCESS_TOKEN"):
                        errors.append("Meta CAPI is enabled but META_CAPI_ACCESS_TOKEN is missing.")
                    if not os.getenv("META_GRAPH_API_VERSION"):
                        errors.append("Meta CAPI is enabled but META_GRAPH_API_VERSION is missing.")
                if config.ga4_server_enabled and not os.getenv("GA4_API_SECRET"):
                    errors.append("GA4 server tracking is enabled but GA4_API_SECRET is missing.")
                if config.sms_enabled and not os.getenv("SMS_API_TOKEN"):
                    errors.append("SMS is enabled but SMS_API_TOKEN is missing.")
                if config.whatsapp_enabled and not os.getenv("WHATSAPP_API_TOKEN"):
                    errors.append("WhatsApp is enabled but WHATSAPP_API_TOKEN is missing.")
                if config.courier_api_enabled:
                    from shipping.models import CourierProvider
                    for provider in CourierProvider.objects.filter(is_active=True, api_enabled=True):
                        code = provider.code.upper().replace("-", "_")
                        if not os.getenv(f"COURIER_{code}_API_BASE_URL"):
                            errors.append(f"Courier {provider.code} API is enabled but COURIER_{code}_API_BASE_URL is missing.")
                        if not (os.getenv(f"COURIER_{code}_API_TOKEN") or os.getenv("COURIER_API_TOKEN")):
                            warnings.append(f"Courier {provider.code} has no API token configured; verify whether the provider requires one.")
        except (OperationalError, ProgrammingError):
            errors.append("Integration tables are unavailable; run migrations first.")

        try:
            from payments.models import PaymentMethodConfig
            test_methods = list(
                PaymentMethodConfig.objects.filter(is_active=True, allow_storefront=True, is_test_mode=True)
                .values_list("display_name", flat=True)
            )
            if test_methods:
                errors.append("Storefront payment method(s) still in test mode: " + ", ".join(test_methods))
        except (OperationalError, ProgrammingError):
            errors.append("Payment configuration tables are unavailable; run migrations first.")

        for warning in warnings:
            self.stdout.write(self.style.WARNING("WARNING: " + warning))
        if errors:
            for error in errors:
                self.stderr.write(self.style.ERROR("ERROR: " + error))
            raise CommandError(f"Production preflight failed with {len(errors)} error(s).")

        self.stdout.write(self.style.SUCCESS("Production preflight passed."))
