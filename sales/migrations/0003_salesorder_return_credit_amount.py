from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0002_pos_tender_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="salesorder",
            name="return_credit_amount",
            field=models.DecimalField(decimal_places=2, default=Decimal("0.00"), max_digits=18),
        ),
    ]
