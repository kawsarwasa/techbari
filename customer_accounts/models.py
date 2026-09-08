from django.conf import settings
from django.db import models

from catalog.models import Product
from customers.models import Customer


class CustomerAccount(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="customer_account")
    customer = models.OneToOneField(Customer, on_delete=models.PROTECT, related_name="account")
    is_active = models.BooleanField(default=True)
    link_verified_at = models.DateTimeField(null=True, blank=True)
    last_login_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self):
        return f"{self.customer.customer_no} / {self.user.username}"


class SavedAddress(models.Model):
    account = models.ForeignKey(CustomerAccount, on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField(max_length=60, default="Home")
    recipient_name = models.CharField(max_length=180)
    phone = models.CharField(max_length=40)
    division = models.CharField(max_length=120)
    district = models.CharField(max_length=120)
    upazila = models.CharField(max_length=120)
    address = models.CharField(max_length=500)
    landmark = models.CharField(max_length=180, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-is_default", "-updated_at", "-id")
        indexes = [models.Index(fields=("account", "is_default"), name="custacct_addr_default_idx")]

    @property
    def display_address(self):
        parts = [self.address, self.upazila, self.district, self.division, self.postal_code]
        return ", ".join(str(part).strip() for part in parts if str(part or "").strip())

    def __str__(self):
        return f"{self.account.customer.customer_no}: {self.label}"


class WishlistItem(models.Model):
    account = models.ForeignKey(CustomerAccount, on_delete=models.CASCADE, related_name="wishlist_items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="customer_wishlist_items")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [models.UniqueConstraint(fields=("account", "product"), name="uniq_customer_wishlist_product")]
        indexes = [models.Index(fields=("account", "created_at"), name="custacct_wish_created_idx")]

    def __str__(self):
        return f"{self.account.customer.customer_no}: {self.product.name}"
