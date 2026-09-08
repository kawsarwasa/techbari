from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("catalog", "0002_catalog_crud_expansion"),
        ("customers", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomerAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("is_active", models.BooleanField(default=True)),
                ("link_verified_at", models.DateTimeField(blank=True, null=True)),
                ("last_login_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("customer", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="account", to="customers.customer")),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="customer_account", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at", "-id")},
        ),
        migrations.CreateModel(
            name="SavedAddress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("label", models.CharField(default="Home", max_length=60)),
                ("recipient_name", models.CharField(max_length=180)),
                ("phone", models.CharField(max_length=40)),
                ("division", models.CharField(max_length=120)),
                ("district", models.CharField(max_length=120)),
                ("upazila", models.CharField(max_length=120)),
                ("address", models.CharField(max_length=500)),
                ("landmark", models.CharField(blank=True, max_length=180)),
                ("postal_code", models.CharField(blank=True, max_length=20)),
                ("is_default", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="addresses", to="customer_accounts.customeraccount")),
            ],
            options={"ordering": ("-is_default", "-updated_at", "-id")},
        ),
        migrations.CreateModel(
            name="WishlistItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="wishlist_items", to="customer_accounts.customeraccount")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="customer_wishlist_items", to="catalog.product")),
            ],
            options={"ordering": ("-created_at", "-id")},
        ),
        migrations.AddIndex(model_name="savedaddress", index=models.Index(fields=["account", "is_default"], name="custacct_addr_default_idx")),
        migrations.AddConstraint(model_name="wishlistitem", constraint=models.UniqueConstraint(fields=("account", "product"), name="uniq_customer_wishlist_product")),
        migrations.AddIndex(model_name="wishlistitem", index=models.Index(fields=["account", "created_at"], name="custacct_wish_created_idx")),
    ]
