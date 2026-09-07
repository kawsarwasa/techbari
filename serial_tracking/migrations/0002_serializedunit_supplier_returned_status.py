from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("serial_tracking", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="serializedunit",
            name="status",
            field=models.CharField(
                choices=[
                    ("available", "Available"),
                    ("reserved", "Reserved"),
                    ("sold", "Sold"),
                    ("returned", "Returned"),
                    ("damaged", "Damaged"),
                    ("warranty_service", "Warranty Service"),
                    ("scrapped", "Scrapped"),
                    ("supplier_returned", "Returned to Supplier"),
                ],
                default="available",
                max_length=32,
            ),
        ),
    ]
