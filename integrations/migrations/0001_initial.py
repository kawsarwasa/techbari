from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="IntegrationSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("singleton_key", models.PositiveSmallIntegerField(default=1, editable=False, unique=True)),
                ("email_enabled", models.BooleanField(default=True)),
                ("sms_enabled", models.BooleanField(default=False)),
                ("whatsapp_enabled", models.BooleanField(default=False)),
                ("notify_order_events", models.BooleanField(default=True)),
                ("notify_payment_events", models.BooleanField(default=True)),
                ("notify_low_stock", models.BooleanField(default=True)),
                ("notify_shipping_events", models.BooleanField(default=True)),
                ("admin_email", models.EmailField(blank=True, max_length=254)),
                ("admin_phone", models.CharField(blank=True, max_length=40)),
                ("sms_webhook_url", models.URLField(blank=True)),
                ("whatsapp_webhook_url", models.URLField(blank=True)),
                ("meta_pixel_enabled", models.BooleanField(default=False)),
                ("meta_pixel_id", models.CharField(blank=True, max_length=80)),
                ("meta_capi_enabled", models.BooleanField(default=False)),
                ("ga4_enabled", models.BooleanField(default=False)),
                ("ga4_measurement_id", models.CharField(blank=True, max_length=80)),
                ("ga4_server_enabled", models.BooleanField(default=False)),
                ("courier_api_enabled", models.BooleanField(default=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name_plural": "integration settings"},
        ),
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("order", "Order"), ("payment", "Payment"), ("stock", "Stock"), ("shipping", "Shipping"), ("integration", "Integration")], default="order", max_length=24)),
                ("severity", models.CharField(choices=[("info", "Info"), ("success", "Success"), ("warning", "Warning"), ("danger", "Danger")], default="info", max_length=16)),
                ("title", models.CharField(max_length=180)),
                ("message", models.CharField(max_length=500)),
                ("link", models.CharField(blank=True, max_length=500)),
                ("reference_type", models.CharField(blank=True, max_length=50)),
                ("reference_id", models.CharField(blank=True, max_length=100)),
                ("dedupe_key", models.CharField(blank=True, max_length=220, null=True, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ("-created_at", "-id"),
                "indexes": [models.Index(fields=["kind", "created_at"], name="int_notif_kind_time_idx"), models.Index(fields=["created_at"], name="int_notif_time_idx")],
            },
        ),
        migrations.CreateModel(
            name="OutboundMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("channel", models.CharField(choices=[("email", "Email"), ("sms", "SMS"), ("whatsapp", "WhatsApp"), ("meta_capi", "Meta CAPI"), ("ga4", "Google Analytics 4"), ("courier", "Courier API")], max_length=24)),
                ("event_type", models.CharField(max_length=80)),
                ("recipient", models.CharField(blank=True, max_length=500)),
                ("subject", models.CharField(blank=True, max_length=255)),
                ("body", models.TextField(blank=True)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("idempotency_key", models.CharField(max_length=220, unique=True)),
                ("reference_type", models.CharField(blank=True, max_length=50)),
                ("reference_id", models.CharField(blank=True, max_length=100)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("sent", "Sent"), ("failed", "Failed"), ("skipped", "Skipped")], default="pending", max_length=16)),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("available_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("last_attempt_at", models.DateTimeField(blank=True, null=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.CharField(blank=True, max_length=1000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("status", "available_at", "id"),
                "indexes": [models.Index(fields=["status", "available_at"], name="int_outbox_status_idx"), models.Index(fields=["channel", "created_at"], name="int_outbox_channel_idx"), models.Index(fields=["reference_type", "reference_id"], name="int_outbox_ref_idx")],
            },
        ),
        migrations.CreateModel(
            name="NotificationRead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("read_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("notification", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reads", to="integrations.notification")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notification_reads", to=settings.AUTH_USER_MODEL)),
            ],
            options={"indexes": [models.Index(fields=["user", "read_at"], name="int_notif_read_user_idx")]},
        ),
        migrations.AddConstraint(
            model_name="notificationread",
            constraint=models.UniqueConstraint(fields=("notification", "user"), name="uniq_int_notification_read"),
        ),
    ]
