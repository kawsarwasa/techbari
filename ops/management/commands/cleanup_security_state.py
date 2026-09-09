from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from integrations.models import CourierWebhookReceipt
from staff_access.models import AuthThrottle


class Command(BaseCommand):
    help = "Delete expired authentication throttles and courier replay receipts."

    def add_arguments(self, parser):
        parser.add_argument("--throttle-hours", type=int, default=24)

    def handle(self, *args, **options):
        now = timezone.now()
        throttle_hours = max(1, min(int(options["throttle_hours"]), 24 * 30))
        throttle_cutoff = now - timedelta(hours=throttle_hours)
        throttle_qs = AuthThrottle.objects.filter(updated_at__lt=throttle_cutoff).exclude(locked_until__gt=now)
        throttle_count, _ = throttle_qs.delete()

        receipt_days = int(getattr(settings, "COURIER_WEBHOOK_RECEIPT_DAYS", 7))
        receipt_cutoff = now - timedelta(days=max(1, receipt_days))
        receipt_count, _ = CourierWebhookReceipt.objects.filter(received_at__lt=receipt_cutoff).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Security state cleaned: auth_throttles={throttle_count}; webhook_receipts={receipt_count}"
            )
        )
