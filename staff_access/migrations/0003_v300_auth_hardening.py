from django.db import migrations, models
import django.utils.timezone


SYSTEM_ROLES = ("Admin", "Manager", "Cashier", "Inventory Manager", "Accountant", "Sales Staff")


def mark_role_users_as_staff(apps, schema_editor):
    User = apps.get_model("auth", "User")
    ids = list(User.objects.filter(groups__name__in=SYSTEM_ROLES).values_list("pk", flat=True).distinct())
    if ids:
        User.objects.filter(pk__in=ids).update(is_staff=True)


class Migration(migrations.Migration):
    dependencies = [("staff_access", "0002_v280_integration_permissions")]

    operations = [
        migrations.CreateModel(
            name="AuthThrottle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("scope", models.CharField(max_length=32)),
                ("key_hash", models.CharField(max_length=64)),
                ("failures", models.PositiveSmallIntegerField(default=0)),
                ("window_started_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("locked_until", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddConstraint(
            model_name="auththrottle",
            constraint=models.UniqueConstraint(fields=("scope", "key_hash"), name="uniq_auth_throttle_scope_key"),
        ),
        migrations.AddIndex(
            model_name="auththrottle",
            index=models.Index(fields=["locked_until"], name="staff_auth_locked_idx"),
        ),
        migrations.RunPython(mark_role_users_as_staff, migrations.RunPython.noop),
    ]
