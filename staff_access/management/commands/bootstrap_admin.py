from getpass import getpass

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand, CommandError

from staff_access.permissions import sync_system_roles
from staff_access.services import assign_system_role, ensure_profile


class Command(BaseCommand):
    help = "Create or update the first TechBari administrator safely."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="admin")
        parser.add_argument("--email", required=True)
        parser.add_argument("--password", default="")
        parser.add_argument("--branch", default="Main Branch")
        parser.add_argument("--no-superuser", action="store_true")

    def handle(self, *args, **options):
        password = options["password"]
        if not password:
            first = getpass("Password: ")
            second = getpass("Password (again): ")
            if first != second:
                raise CommandError("Passwords do not match.")
            password = first
        if not password:
            raise CommandError("Password cannot be empty.")
        sync_system_roles()
        role = Group.objects.filter(name="Admin").first()
        if role is None:
            raise CommandError("Admin role was not created. Run migrations first.")
        user, created = User.objects.get_or_create(username=options["username"], defaults={"email": options["email"]})
        user.email = options["email"].strip().lower()
        user.is_active = True
        user.is_staff = True
        user.is_superuser = not options["no_superuser"]
        user.set_password(password)
        user.save()
        assign_system_role(user, role)
        profile = ensure_profile(user)
        profile.branch = options["branch"]
        profile.save(update_fields=["branch", "updated_at"])
        self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Updated'} TechBari admin: {user.username}"))
