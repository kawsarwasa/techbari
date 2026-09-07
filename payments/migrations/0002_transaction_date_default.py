from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [("payments", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="paymenttransaction",
            name="transaction_date",
            field=models.DateField(default=django.utils.timezone.localdate),
        ),
    ]
