from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("sales", "0003_salesorder_return_credit_amount")]

    operations = [
        migrations.AddIndex(
            model_name="salesorder",
            index=models.Index(fields=["created_at"], name="sales_order_created_idx"),
        ),
    ]
