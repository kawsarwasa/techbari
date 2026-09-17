import shutil
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS, transaction

from accounting.models import Account
from staff_access.models import StaffProfile


CONFIRM_PHRASE = "RESET-TECHBARI-DATA"


class Command(BaseCommand):
    help = (
        "Reset TechBari business/demo data for a fresh manual setup while preserving "
        "auth users, groups/permissions, staff profiles, and mandatory system GL accounts."
    )

    def add_arguments(self, parser):
        parser.add_argument("--database", default=DEFAULT_DB_ALIAS)
        parser.add_argument(
            "--confirm",
            default="",
            help=f"Required destructive confirmation phrase: {CONFIRM_PHRASE}",
        )
        parser.add_argument(
            "--delete-media",
            action="store_true",
            help="Also delete uploaded files under MEDIA_ROOT (keeps only .gitkeep files).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be preserved/deleted without changing the database or media files.",
        )
        parser.add_argument(
            "--allow-production",
            action="store_true",
            help="Allow this destructive command when DEBUG=False. Use only with a verified backup.",
        )

    def handle(self, *args, **options):
        database = options["database"]
        dry_run = bool(options["dry_run"])
        delete_media = bool(options["delete_media"])

        if not settings.DEBUG and not options["allow_production"]:
            raise CommandError(
                "Refusing to reset data while DEBUG=False. This command is intended for local/dev cleanup. "
                "Use --allow-production only if you intentionally accept the risk and have a verified backup."
            )

        snapshot = self._snapshot_preserved_data(database)
        media_root = Path(settings.MEDIA_ROOT)
        media_file_count = self._media_file_count(media_root)

        self.stdout.write("TechBari manual-data reset preview")
        self.stdout.write(f"  users preserved: {len(snapshot['users'])}")
        self.stdout.write(f"  groups preserved: {len(snapshot['groups'])}")
        self.stdout.write(f"  staff profiles preserved: {len(snapshot['staff_profiles'])}")
        self.stdout.write(f"  system GL accounts preserved: {len(snapshot['system_accounts'])}")
        self.stdout.write(f"  uploaded media files found: {media_file_count}")
        self.stdout.write(
            "  business/demo data: WILL BE CLEARED (catalog, inventory, serials, purchases, customers, "
            "sales, payments, shipping, returns, accounting activity, expenses, promotions, CMS content, "
            "customer profiles, integrations, audit/security state, sessions, etc.)"
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run only. No data or files were deleted."))
            return

        if options["confirm"] != CONFIRM_PHRASE:
            raise CommandError(
                f"Destructive reset not confirmed. Re-run with --confirm {CONFIRM_PHRASE}."
            )

        # flush clears application rows without removing migration history, then Django
        # recreates content types/permissions via post_migrate. We restore the intentionally
        # preserved identities/configuration immediately afterward.
        call_command(
            "flush",
            verbosity=0,
            interactive=False,
            database=database,
        )

        self._restore_preserved_data(database, snapshot)

        deleted_media = 0
        if delete_media:
            deleted_media = self._clear_media(media_root)

        self.stdout.write(
            self.style.SUCCESS(
                "Reset complete: business/demo data cleared; "
                f"users={len(snapshot['users'])}, groups={len(snapshot['groups'])}, "
                f"staff_profiles={len(snapshot['staff_profiles'])}, "
                f"system_gl_accounts={len(snapshot['system_accounts'])} restored; "
                f"media_files_deleted={deleted_media}."
            )
        )
        self.stdout.write(
            self.style.WARNING(
                "Existing browser sessions were cleared by the reset, so sign in again if needed."
            )
        )

    def _snapshot_preserved_data(self, database):
        User = get_user_model()

        users = []
        for user in User._default_manager.using(database).all().order_by(User._meta.pk.name):
            concrete = {
                field.attname: getattr(user, field.attname)
                for field in User._meta.concrete_fields
            }
            users.append(
                {
                    "fields": concrete,
                    "groups": list(user.groups.using(database).values_list("name", flat=True)),
                    "permissions": list(
                        user.user_permissions.using(database).values_list(
                            "content_type__app_label", "codename"
                        )
                    ),
                }
            )

        groups = []
        for group in Group.objects.using(database).all().order_by("id"):
            groups.append(
                {
                    "name": group.name,
                    "permissions": list(
                        group.permissions.using(database).values_list(
                            "content_type__app_label", "codename"
                        )
                    ),
                }
            )

        staff_profiles = list(
            StaffProfile.objects.using(database).values(
                "user_id",
                "phone",
                "branch",
                "force_password_change",
            )
        )

        system_accounts = list(
            Account.objects.using(database)
            .filter(is_system=True)
            .values(
                "id",
                "code",
                "name",
                "account_type",
                "normal_balance",
                "description",
                "is_system",
                "allow_manual_entries",
                "is_active",
            )
        )

        if not users:
            raise CommandError("No auth users were found. Aborting so you do not accidentally lose login access.")

        if not system_accounts:
            raise CommandError(
                "No system GL accounts were found. Aborting because TechBari accounting automation depends on them."
            )

        return {
            "users": users,
            "groups": groups,
            "staff_profiles": staff_profiles,
            "system_accounts": system_accounts,
        }

    @transaction.atomic
    def _restore_preserved_data(self, database, snapshot):
        User = get_user_model()

        permission_map = {
            (permission.content_type.app_label, permission.codename): permission
            for permission in Permission.objects.using(database).select_related("content_type")
        }

        group_map = {}
        for row in snapshot["groups"]:
            group = Group.objects.using(database).create(name=row["name"])
            permissions = [
                permission_map[key]
                for key in row["permissions"]
                if key in permission_map
            ]
            if permissions:
                group.permissions.set(permissions)
            group_map[group.name] = group

        user_map = {}
        for row in snapshot["users"]:
            user = User(**row["fields"])
            user.save(using=database, force_insert=True)
            user_map[user.pk] = user

            groups = [group_map[name] for name in row["groups"] if name in group_map]
            if groups:
                user.groups.set(groups)

            permissions = [
                permission_map[key]
                for key in row["permissions"]
                if key in permission_map
            ]
            if permissions:
                user.user_permissions.set(permissions)

        for row in snapshot["staff_profiles"]:
            if row["user_id"] not in user_map:
                continue
            StaffProfile.objects.using(database).create(**row)

        for row in snapshot["system_accounts"]:
            Account.objects.using(database).create(**row)

    def _media_file_count(self, media_root):
        if not media_root.exists():
            return 0
        return sum(
            1
            for path in media_root.rglob("*")
            if path.is_file() and path.name != ".gitkeep"
        )

    def _clear_media(self, media_root):
        if not media_root.exists():
            return 0

        deleted = 0
        for path in sorted(media_root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
            if path.is_file():
                if path.name == ".gitkeep":
                    continue
                path.unlink()
                deleted += 1
            elif path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    # Non-empty directories may contain a preserved .gitkeep.
                    pass

        # Defensive cleanup for any top-level directories that may have survived because
        # they contained only empty nested directories.
        for child in media_root.iterdir():
            if child.is_dir() and not any(child.rglob(".gitkeep")):
                shutil.rmtree(child, ignore_errors=True)

        return deleted
