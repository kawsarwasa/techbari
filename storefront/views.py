from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from catalog.models import Product
from catalog.presentation import catalog_queryset, serialize_product
from .context import catalog_context

PAGE_TEMPLATES = {"home": "home", "products": "products", "cart": "cart", "checkout": "checkout", "wishlist": "wishlist", "track_order": "track_order", "login": "login", "register": "login", "contact": "contact"}
LEGACY_PAGES = {"index": "home", "track-order": "track_order", **{name: name for name in PAGE_TEMPLATES}}


def page(request, page_name="home"):
    if page_name not in PAGE_TEMPLATES:
        raise Http404("Page not found")
    context = catalog_context()
    context["auth_mode"] = "register" if page_name == "register" else "login"
    if page_name == "products":
        query = request.GET.get("q", "").casefold().strip()
        if query:
            context["products"] = [p for p in context["products"] if query in f'{p["name"]} {p["brand"]} {p["category"]} {p["sku"]}'.casefold()]
    return render(request, f"storefront/pages/{PAGE_TEMPLATES[page_name]}.html", context)


def product_detail(request, slug=None, product_id=None):
    qs = catalog_queryset()
    if slug:
        product_obj = get_object_or_404(qs, slug=slug)
    elif product_id:
        product_obj = get_object_or_404(qs, public_id=product_id)
    else:
        raise Http404("Product not found")
    context = catalog_context()
    product = serialize_product(product_obj)
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
    elif page in LEGACY_PAGES:
        target = reverse("storefront:" + LEGACY_PAGES[page])
    else:
        raise Http404("Page not found")
    query = request.META.get("QUERY_STRING", "")
    return redirect(target + ("?" + query if query else ""))
