from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from catalog.models import Product
from catalog.presentation import catalog_queryset, serialize_product
from customer_accounts.models import CustomerAccount
from promotions.services import campaign_attribution_for_request
from sales.models import SalesOrder
from store_settings.models import ContentPage

from .checkout_services import CheckoutError, checkout_success_url, create_checkout_token, place_checkout_order, verify_success_token
from .context import catalog_context
from .forms import CheckoutForm

PAGE_TEMPLATES = {"home": "home", "products": "products", "cart": "cart", "contact": "contact"}
LEGACY_PAGES = {
    "index": "home",
    "track-order": "track_order",
    "checkout": "checkout",
    "wishlist": "wishlist",
    "login": "login",
    "register": "register",
    **{name: name for name in PAGE_TEMPLATES},
}


def _customer_account_for_request(request):
    if not request.user.is_authenticated:
        return None
    return CustomerAccount.objects.select_related("customer", "user").filter(
        user_id=request.user.pk,
        is_active=True,
        customer__is_active=True,
        user__is_active=True,
    ).first()


def page(request, page_name="home"):
    if page_name not in PAGE_TEMPLATES:
        raise Http404("Page not found")
    context = catalog_context()
    if page_name == "products":
        query = request.GET.get("q", "").casefold().strip()
        if query:
            context["products"] = [p for p in context["products"] if query in f'{p["name"]} {p["brand"]} {p["category"]} {p["sku"]}'.casefold()]
    return render(request, f"storefront/pages/{PAGE_TEMPLATES[page_name]}.html", context)


def content_page(request, slug):
    page_obj = get_object_or_404(ContentPage, slug=slug, is_published=True)
    context = catalog_context()
    context.update(content_page=page_obj, seo_title=page_obj.seo_title or page_obj.title, page_seo_description=page_obj.seo_description or context["store_settings"].seo_description)
    return render(request, "storefront/pages/content_page.html", context)


def checkout(request):
    context = catalog_context()
    account = _customer_account_for_request(request)
    store = context["store_settings"]
    if not store.guest_checkout_enabled and not account:
        return redirect(f"{reverse('storefront:login')}?next={reverse('storefront:checkout')}")

    campaign_attribution = campaign_attribution_for_request(request)
    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            try:
                order, _created = place_checkout_order(form.cleaned_data, campaign_attribution=campaign_attribution, customer_account=account)
                return redirect(checkout_success_url(order))
            except CheckoutError as exc:
                form.add_error(None, " ".join(str(value) for value in getattr(exc, "messages", [str(exc)])))
    else:
        initial = {"delivery_option": "inside", "payment_method": "cod", "checkout_token": create_checkout_token(), "cart_payload": "[]"}
        if account:
            customer = account.customer
            initial.update(full_name=customer.name, phone=customer.phone, email=customer.email)
            default_address = account.addresses.filter(is_default=True).first()
            if default_address:
                # Saved addresses supply the destination. Customer identity remains the
                # linked CRM name/phone so checkout cannot silently alter the profile.
                initial.update(
                    division=default_address.division,
                    district=default_address.district,
                    upazila=default_address.upazila,
                    address=default_address.address,
                    landmark=default_address.landmark,
                )
            else:
                initial.update(address=customer.address, district=customer.district, upazila=customer.city)
        form = CheckoutForm(initial=initial)
    context.update(checkout_form=form, checkout_backend=True, checkout_customer_account=account)
    return render(request, "storefront/pages/checkout.html", context)


def checkout_success(request, order_number):
    try:
        verify_success_token(order_number, request.GET.get("token", ""))
    except CheckoutError as exc:
        raise Http404("Order confirmation not found") from exc
    order = get_object_or_404(SalesOrder.objects.select_related("customer", "warehouse").prefetch_related("items__variant__product"), order_number=order_number, channel=SalesOrder.Channel.ONLINE)
    context = catalog_context()
    context.update(order=order, checkout_complete=True)
    return render(request, "storefront/pages/checkout_success.html", context)


def product_detail(request, slug=None, product_id=None):
    qs = catalog_queryset()
    if slug:
        product_obj = get_object_or_404(qs, slug=slug)
    elif product_id:
        product_obj = get_object_or_404(qs, public_id=product_id)
    else:
        raise Http404("Product not found")
    context = catalog_context()
    product = next((row for row in context["catalog"] if row["pk"] == product_obj.pk), serialize_product(product_obj))
    context.update(product=product, has_local_benefits=True)
    context["store_data"]["current_product"] = product["id"]
    context["related_products"] = [p for p in context["catalog"] if p["id"] != product["id"]][:4]
    return render(request, "storefront/pages/product_detail.html", context)


def legacy_page(request, page):
    if page == "product":
        first_product = Product.objects.filter(status=Product.Status.ACTIVE).order_by("id").first()
        if first_product is None:
            raise Http404("Product not found")
        target = reverse("storefront:product_detail", kwargs={"slug": first_product.slug})
    elif page == "checkout":
        target = reverse("storefront:checkout")
    elif page in LEGACY_PAGES:
        target = reverse("storefront:" + LEGACY_PAGES[page])
    else:
        raise Http404("Page not found")
    query = request.META.get("QUERY_STRING", "")
    return redirect(target + ("?" + query if query else ""))
