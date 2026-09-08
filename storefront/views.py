from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from catalog.models import Product
from catalog.presentation import catalog_queryset, serialize_product
from promotions.services import campaign_attribution_for_request
from sales.models import SalesOrder
from .checkout_services import CheckoutError, checkout_success_url, create_checkout_token, place_checkout_order, verify_success_token
from .context import catalog_context
from .forms import CheckoutForm

PAGE_TEMPLATES = {"home": "home", "products": "products", "cart": "cart", "wishlist": "wishlist", "track_order": "track_order", "login": "login", "register": "login", "contact": "contact"}
LEGACY_PAGES = {"index": "home", "track-order": "track_order", "checkout": "checkout", **{name: name for name in PAGE_TEMPLATES}}


def page(request, page_name="home"):
    if page_name not in PAGE_TEMPLATES: raise Http404("Page not found")
    context = catalog_context(); context["auth_mode"] = "register" if page_name == "register" else "login"
    if page_name == "products":
        query = request.GET.get("q", "").casefold().strip()
        if query: context["products"] = [p for p in context["products"] if query in f'{p["name"]} {p["brand"]} {p["category"]} {p["sku"]}'.casefold()]
    return render(request, f"storefront/pages/{PAGE_TEMPLATES[page_name]}.html", context)


def checkout(request):
    context = catalog_context()
    campaign_attribution = campaign_attribution_for_request(request)
    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            try:
                order, _created = place_checkout_order(form.cleaned_data, campaign_attribution=campaign_attribution); return redirect(checkout_success_url(order))
            except CheckoutError as exc:
                form.add_error(None, " ".join(str(value) for value in getattr(exc, "messages", [str(exc)])))
    else:
        form = CheckoutForm(initial={"delivery_option": "inside", "payment_method": "cod", "checkout_token": create_checkout_token(), "cart_payload": "[]"})
    context.update(checkout_form=form, checkout_backend=True)
    return render(request, "storefront/pages/checkout.html", context)


def checkout_success(request, order_number):
    try: verify_success_token(order_number, request.GET.get("token", ""))
    except CheckoutError as exc: raise Http404("Order confirmation not found") from exc
    order = get_object_or_404(SalesOrder.objects.select_related("customer", "warehouse").prefetch_related("items__variant__product"), order_number=order_number, channel=SalesOrder.Channel.ONLINE)
    context = catalog_context(); context.update(order=order, checkout_complete=True)
    return render(request, "storefront/pages/checkout_success.html", context)


def product_detail(request, slug=None, product_id=None):
    qs = catalog_queryset()
    if slug: product_obj = get_object_or_404(qs, slug=slug)
    elif product_id: product_obj = get_object_or_404(qs, public_id=product_id)
    else: raise Http404("Product not found")
    context = catalog_context(); product = next((row for row in context["catalog"] if row["pk"] == product_obj.pk), serialize_product(product_obj))
    context.update(product=product, has_local_benefits=True); context["store_data"]["current_product"] = product["id"]; context["related_products"] = [p for p in context["catalog"] if p["id"] != product["id"]][:4]
    return render(request, "storefront/pages/product_detail.html", context)


def legacy_page(request, page):
    if page == "product":
        first_product = Product.objects.filter(status=Product.Status.ACTIVE).order_by("id").first()
        if first_product is None: raise Http404("Product not found")
        target = reverse("storefront:product_detail", kwargs={"slug": first_product.slug})
    elif page == "checkout": target = reverse("storefront:checkout")
    elif page in LEGACY_PAGES: target = reverse("storefront:" + LEGACY_PAGES[page])
    else: raise Http404("Page not found")
    query = request.META.get("QUERY_STRING", ""); return redirect(target + ("?" + query if query else ""))
