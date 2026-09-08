from django.core.management.base import BaseCommand, CommandError

from integrations.delivery import process_outbound


class Command(BaseCommand):
    help = "Process pending TechBari notification/integration deliveries. Safe for shared-hosting cron."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        limit = options["limit"]
        if limit < 1 or limit > 500:
            raise CommandError("--limit must be between 1 and 500.")
        result = process_outbound(limit=limit)
        self.stdout.write(self.style.SUCCESS(f"Integrations processed: sent={result['sent']}; failed={result['failed']}; skipped={result['skipped']}"))
