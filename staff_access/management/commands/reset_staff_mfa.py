from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from staff_access.mfa import reset_mfa


class Command(BaseCommand):
    help = "Emergency-reset MFA for a TechBari staff user so they can enroll again."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Confirm the destructive MFA reset.",
        )

    def handle(self, *args, **options):
        if not options["yes"]:
            raise CommandError("Refusing to reset MFA without --yes.")
        User = get_user_model()
        try:
            user = User.objects.get(username=options["username"])
        except User.DoesNotExist as exc:
            raise CommandError("Staff user not found.") from exc
        if not (user.is_staff or user.is_superuser):
            raise CommandError("The selected account is not a staff account.")
        deleted = reset_mfa(user)
        if deleted:
            self.stdout.write(
                self.style.SUCCESS(
                    f"MFA reset for {user.username}. The user must enroll again on next dashboard sign-in when MFA is required."
                )
            )
        else:
            self.stdout.write(self.style.WARNING(f"{user.username} did not have an MFA device."))
