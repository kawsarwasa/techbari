from functools import wraps
from urllib.parse import urlencode

from django.shortcuts import redirect

from .models import CustomerAccount


def customer_account_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/login/?{urlencode({'next': request.get_full_path()})}")
        account = CustomerAccount.objects.select_related("customer", "user").filter(
            user_id=request.user.pk,
            is_active=True,
            customer__is_active=True,
            user__is_active=True,
        ).first()
        if not account:
            return redirect(f"/login/?{urlencode({'next': request.get_full_path()})}")
        request.customer_account = account
        return view_func(request, *args, **kwargs)

    return wrapped
