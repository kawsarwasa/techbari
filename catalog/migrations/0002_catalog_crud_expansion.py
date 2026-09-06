from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="product",
            name="slug",
            field=models.SlugField(max_length=255, unique=True),
        ),
        migrations.AddField(
            model_name="productvariant",
            name="barcode",
            field=models.CharField(blank=True, max_length=64, null=True, unique=True),
        ),
        migrations.AddIndex(
            model_name="productvariant",
            index=models.Index(fields=["product", "is_active"], name="cat_var_prod_active_idx"),
        ),
        migrations.AddIndex(
            model_name="productimage",
            index=models.Index(fields=["product", "role", "sort_order"], name="cat_img_prod_role_idx"),
        ),
    ]
