from .models import CustomerAccount


def customer_account(request):
    account = None
    wishlist_count = 0
    wishlist_product_ids = []
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        account = CustomerAccount.objects.select_related("customer").filter(user_id=user.pk, is_active=True, customer__is_active=True).first()
        if account:
            wishlist_qs = account.wishlist_items.all()
            wishlist_count = wishlist_qs.count()
            wishlist_product_ids = list(wishlist_qs.values_list("product_id", flat=True))
    return {
        "customer_account": account,
        "customer_wishlist_count": wishlist_count,
        "customer_wishlist_product_ids": wishlist_product_ids,
    }
