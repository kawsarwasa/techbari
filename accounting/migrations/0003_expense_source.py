from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("accounting", "0002_backfill_existing_business_history")]

    operations = [
        migrations.AlterField(
            model_name="journalentry",
            name="source_type",
            field=models.CharField(
                choices=[
                    ("sale", "Sales Order"),
                    ("sale_return", "Sales Return"),
                    ("sale_payment", "Sale Payment"),
                    ("supplier_payment", "Supplier Payment"),
                    ("purchase_receipt", "Purchase Receipt"),
                    ("purchase_overhead", "Purchase Overhead"),
                    ("purchase_return", "Purchase Return"),
                    ("courier_fee", "Courier / Collection Fee"),
                    ("expense", "Business Expense"),
                    ("opening_balance", "Opening Balance"),
                    ("manual", "Manual Journal"),
                    ("reversal", "Journal Reversal"),
                ],
                default="manual",
                max_length=24,
            ),
        )
    ]
