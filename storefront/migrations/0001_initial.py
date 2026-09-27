from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ContactMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=180)),
                ("email", models.EmailField(max_length=254)),
                ("phone", models.CharField(blank=True, max_length=40)),
                ("subject", models.CharField(max_length=120)),
                ("message", models.TextField(max_length=3000)),
                ("status", models.CharField(choices=[("new", "New"), ("read", "Read"), ("replied", "Replied")], default="new", max_length=16)),
                ("source_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("first_read_at", models.DateTimeField(blank=True, null=True)),
                ("replied_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("handled_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="handled_contact_messages", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("-created_at", "-id"),
                "indexes": [
                    models.Index(fields=["status", "created_at"], name="sf_contact_status_idx"),
                    models.Index(fields=["email", "created_at"], name="sf_contact_email_idx"),
                ],
            },
        ),
    ]
