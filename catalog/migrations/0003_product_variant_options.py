from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0002_catalog_crud_expansion"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductOption",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="options", to="catalog.product")),
            ],
            options={"ordering": ("product_id", "sort_order", "id")},
        ),
        migrations.CreateModel(
            name="ProductOptionValue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("value", models.CharField(max_length=120)),
                ("symbol", models.CharField(blank=True, max_length=32)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("option", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="values", to="catalog.productoption")),
            ],
            options={"ordering": ("option_id", "sort_order", "id")},
        ),
        migrations.CreateModel(
            name="ProductVariantOptionValue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("option", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="variant_selections", to="catalog.productoption")),
                ("value", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="variant_selections", to="catalog.productoptionvalue")),
                ("variant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="option_selections", to="catalog.productvariant")),
            ],
            options={"ordering": ("option__sort_order", "option_id", "id")},
        ),
        migrations.AddConstraint(
            model_name="productoption",
            constraint=models.UniqueConstraint(fields=("product", "name"), name="uniq_product_option_name"),
        ),
        migrations.AddIndex(
            model_name="productoption",
            index=models.Index(fields=["product", "sort_order"], name="cat_option_product_sort_idx"),
        ),
        migrations.AddConstraint(
            model_name="productoptionvalue",
            constraint=models.UniqueConstraint(fields=("option", "value"), name="uniq_product_option_value"),
        ),
        migrations.AddIndex(
            model_name="productoptionvalue",
            index=models.Index(fields=["option", "sort_order"], name="cat_optval_option_sort_idx"),
        ),
        migrations.AddConstraint(
            model_name="productvariantoptionvalue",
            constraint=models.UniqueConstraint(fields=("variant", "option"), name="uniq_variant_option_selection"),
        ),
        migrations.AddIndex(
            model_name="productvariantoptionvalue",
            index=models.Index(fields=["variant", "option"], name="cat_varopt_variant_option_idx"),
        ),
    ]
