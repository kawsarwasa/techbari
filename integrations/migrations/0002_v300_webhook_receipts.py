from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("integrations", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="CourierWebhookReceipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("provider_code", models.CharField(max_length=64)),
                ("digest", models.CharField(max_length=64, unique=True)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ("-received_at", "-id"),
                "indexes": [models.Index(fields=["provider_code", "received_at"], name="int_hook_provider_time_idx")],
            },
        ),
    ]
