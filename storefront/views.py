from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from .context import catalog_context

PAGE_TEMPLATES = {
    "home": "home", "products": "products", "cart": "cart", "checkout": "checkout",
    "wishlist": "wishlist", "track_order": "track_order", "login": "login",
    "register": "login", "contact": "contact",
}
LEGACY_PAGES = {"index": "home", "track-order": "track_order",
                **{name: name for name in PAGE_TEMPLATES}}


def page(request, page_name="home"):
    if page_name not in PAGE_TEMPLATES:
        raise Http404("Page not found")
    context = catalog_context()
    context["auth_mode"] = "register" if page_name == "register" else "login"
    if page_name == "products":
        query = request.GET.get("q", "").casefold()
        context["products"] = [p for p in context["products"]
                               if query in f'{p["name"]} {p["brand"]} {p["category"]}'.casefold()]
    return render(request, f"storefront/pages/{PAGE_TEMPLATES[page_name]}.html", context)


def product_detail(request, slug=None, product_id=None):
    context = catalog_context()
    product = next((p for p in context["catalog"]
                    if p["slug"] == slug or (product_id is not None and p["id"] == product_id)), None)
    if product is None:
        raise Http404("Product not found")
    context.update(product=product, has_local_benefits=True)
    context["store_data"]["current_product"] = product["id"]
    return render(request, "storefront/pages/product_detail.html", context)


def legacy_page(request, page):
    if page == "product":
        target = reverse("storefront:product_detail", kwargs={"slug": "baseus-bowie-e16-tws-earbuds"})
    elif page in LEGACY_PAGES:
        target = reverse("storefront:" + LEGACY_PAGES[page])
    else:
        raise Http404("Page not found")
    query = request.META.get("QUERY_STRING", "")
    return redirect(target + ("?" + query if query else ""))
