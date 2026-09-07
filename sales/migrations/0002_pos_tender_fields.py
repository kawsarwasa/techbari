from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("sales", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="salesorder",
            name="payment_method",
            field=models.CharField(
                blank=True,
                choices=[
                    ("cash", "Cash"),
                    ("card", "Card"),
                    ("bkash", "bKash"),
                    ("nagad", "Nagad"),
                    ("other", "Other"),
                ],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="salesorder",
            name="payment_reference",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="salesorder",
            name="tendered_amount",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
        migrations.AddField(
            model_name="salesorder",
            name="change_amount",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
    ]
