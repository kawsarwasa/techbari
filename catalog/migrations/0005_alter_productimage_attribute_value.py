from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0004_global_variant_library"),
    ]

    operations = [
        migrations.AlterField(
            model_name="productimage",
            name="attribute_value",
            field=models.ForeignKey(
                blank=True,
                help_text="Optional variant value this image represents, usually a color/finish.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="product_images",
                to="catalog.variantattributevalue",
            ),
        ),
    ]
