from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from catalog.models import Product
from catalog.presentation import catalog_queryset, serialize_product
from customer_accounts.models import CustomerAccount
from promotions.services import campaign_attribution_for_request
from sales.models import SalesOrder
from store_settings.content import render_content_page_body
from store_settings.models import ContentPage

from .bd_locations import BD_LOCATIONS
from .checkout_services import CheckoutError, checkout_success_url, create_checkout_token, place_checkout_order, verify_success_token
from .collections import COLLECTION_LABELS, collection_label, collection_products, normalize_collection
from .context import catalog_context
from .forms import CheckoutForm
from .search import matching_product_ids, product_search_rank

PAGE_TEMPLATES = {"home": "home", "products": "products", "categories": "categories", "brands": "brands", "cart": "cart", "contact": "contact"}
PRODUCTS_PER_PAGE = 12
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


def _selected_filter_names(rows, request, key):
    values = []
    for raw_value in request.GET.getlist(key):
        values.extend(value.strip() for value in raw_value.split(",") if value.strip())
    if not values:
        return []

    by_name = {}
    by_slug = {}
    for row in rows:
        name = str(row.get("name") or "").strip()
        slug = str(row.get("slug") or "").strip()
        if name:
            by_name[name.casefold()] = name
        if slug:
            by_slug[slug.casefold()] = name

    selected = []
    for value in values:
        normalized = value.casefold()
        name = by_name.get(normalized) or by_slug.get(normalized)
        if name and name not in selected:
            selected.append(name)
    return selected


def _selected_category_names(context, request):
    return _selected_filter_names(context.get("categories", []), request, "category")


def _selected_brand_names(context, request):
    return _selected_filter_names(context.get("brands", []), request, "brand")


def _sync_listing_products(context):
    browser_by_pk = {product["pk"]: product for product in context["store_data"]["products"]}
    context["store_data"]["listing_products"] = [
        browser_by_pk[product["pk"]]
        for product in context["products"]
        if product["pk"] in browser_by_pk
    ]


def _apply_collection_filter(context, raw_collection):
    key = normalize_collection(raw_collection)
    context["selected_collection"] = key
    context["selected_collection_label"] = collection_label(key)
    if not key:
        return
    context["products"] = collection_products(context["products"], key)
    _sync_listing_products(context)


def _apply_home_collections(context):
    collections = {
        key: collection_products(context["catalog"], key)[:6]
        for key in COLLECTION_LABELS
    }
    context["home_featured_collections"] = collections
    context["home_featured_collection_ids"] = {
        key: [product["id"] for product in products]
        for key, products in collections.items()
    }
    context["featured_products"] = collections["best-selling"]


def _apply_category_filter(context, selected_names):
    context["selected_category_name"] = selected_names[0] if len(selected_names) == 1 else ""
    if not selected_names:
        return

    allowed = {name.casefold() for name in selected_names}
    context["products"] = [
        product
        for product in context["products"]
        if str(product.get("category") or "").casefold() in allowed
    ]
    _sync_listing_products(context)


def _apply_brand_filter(context, selected_names):
    context["selected_brand_name"] = selected_names[0] if len(selected_names) == 1 else ""
    if not selected_names:
        return

    allowed = {name.casefold() for name in selected_names}
    context["products"] = [
        product
        for product in context["products"]
        if str(product.get("brand") or "").casefold() in allowed
    ]
    _sync_listing_products(context)


def _apply_product_search(context, raw_query):
    query = " ".join(str(raw_query or "").split())
    context["search_query"] = query
    context["store_data"]["search_query"] = query
    if not query:
        context["search_result_count"] = len(context["products"])
        return

    matched_ids = set(matching_product_ids(query))
    products = [product for product in context["products"] if product["pk"] in matched_ids]
    products.sort(
        key=lambda product: (
            -product_search_rank(product, query),
            -int(bool(product.get("is_featured"))),
            str(product.get("name") or "").casefold(),
        )
    )
    context["products"] = products
    context["search_result_count"] = len(products)
    _sync_listing_products(context)


def _apply_product_pagination(context, request):
    paginator = Paginator(context["products"], PRODUCTS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))
    context["products"] = list(page_obj.object_list)
    context["page_obj"] = page_obj
    context["paginator"] = paginator
    context["pagination_total_count"] = paginator.count
    context["pagination_items"] = [
        {"number": value, "ellipsis": value == paginator.ELLIPSIS}
        for value in paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1)
    ]

    query = request.GET.copy()
    query.pop("page", None)
    context["pagination_query"] = query.urlencode()
    _sync_listing_products(context)


def page(request, page_name="home"):
    if page_name not in PAGE_TEMPLATES:
        raise Http404("Page not found")
    context = catalog_context()
    if page_name == "home":
        _apply_home_collections(context)
    elif page_name == "products":
        _apply_collection_filter(context, request.GET.get("collection", ""))
        _apply_category_filter(context, _selected_category_names(context, request))
        _apply_brand_filter(context, _selected_brand_names(context, request))
        _apply_product_search(context, request.GET.get("q", ""))
        _apply_product_pagination(context, request)
    return render(request, f"storefront/pages/{PAGE_TEMPLATES[page_name]}.html", context)


def content_page(request, slug):
    page_obj = get_object_or_404(ContentPage, slug=slug, is_published=True)
    context = catalog_context()
    context.update(
        content_page=page_obj,
        content_page_body_html=render_content_page_body(page_obj.body),
        seo_title=page_obj.seo_title or page_obj.title,
        page_seo_description=page_obj.seo_description or context["store_settings"].seo_description,
    )
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
    context.update(
        checkout_form=form,
        checkout_backend=True,
        checkout_customer_account=account,
        checkout_bd_locations=BD_LOCATIONS,
    )
    return render(request, "storefront/pages/checkout.html", context)


def _purchase_tracking_data(order):
    items = []
    contents = []
    for item in order.items.all():
        price = float(item.unit_price)
        quantity = int(item.quantity)
        items.append({
            "item_id": item.sku_snapshot,
            "item_name": item.product_snapshot,
            "item_variant": item.variant_snapshot,
            "price": price,
            "quantity": quantity,
        })
        contents.append({"id": item.sku_snapshot, "quantity": quantity, "item_price": price})
    return {
        "order_number": order.order_number,
        "event_id": f"tb-purchase-{order.order_number}",
        "value": float(order.grand_total),
        "shipping": float(order.shipping_charge),
        "items": items,
        "contents": contents,
    }


def checkout_success(request, order_number):
    try:
        verify_success_token(order_number, request.GET.get("token", ""))
    except CheckoutError as exc:
        raise Http404("Order confirmation not found") from exc
    order = get_object_or_404(SalesOrder.objects.select_related("customer", "warehouse").prefetch_related("items__variant__product"), order_number=order_number, channel=SalesOrder.Channel.ONLINE)
    context = catalog_context()
    context.update(order=order, checkout_complete=True, purchase_tracking_data=_purchase_tracking_data(order))
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
