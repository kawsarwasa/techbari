from datetime import timedelta
import ipaddress
import json
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import F, Q, Sum
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from django.urls import reverse
from django.utils import timezone

from catalog.models import Product
from catalog.presentation import catalog_queryset, serialize_product
from customer_accounts.models import CustomerAccount
from integrations.services import enqueue_contact_message_notification
from promotions.services import PromotionError, campaign_attribution_for_request, coupon_discount_for_rows
from sales.models import SalesOrder
from staff_access.security import register_rate_event, throttle_seconds_remaining
from store_settings.content import render_content_page_body
from store_settings.models import ContentPage

from .bd_locations import BD_LOCATIONS
from .checkout_services import CheckoutError, _resolve_order_lines, checkout_success_url, create_checkout_token, place_checkout_order, verify_success_token
from .collections import COLLECTION_LABELS, collection_label, collection_products, normalize_collection
from .context import attach_catalog, browser_product_rows, catalog_context, prepare_catalog_products
from .forms import CheckoutForm, ContactForm
from .models import ContactMessage
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
    context["featured_products"] = collections["featured"]


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


def _active_product_base_queryset():
    return Product.objects.filter(
        status=Product.Status.ACTIVE,
        category__is_active=True,
        brand__is_active=True,
    )


def _home_product_ids(limit=6):
    base = _active_product_base_queryset()
    ids = []

    def extend(rows):
        for pk in rows:
            if pk not in ids:
                ids.append(pk)

    featured_ids = list(base.filter(is_featured=True).values_list("pk", flat=True)[:limit])
    extend(featured_ids)

    sold_ids = list(
        base.annotate(
            sold_quantity=Sum(
                "variants__sales_order_items__quantity",
                filter=Q(variants__sales_order_items__order__status=SalesOrder.Status.COMPLETED),
            )
        )
        .filter(sold_quantity__gt=0)
        .order_by("-sold_quantity", "pk")
        .values_list("pk", flat=True)[:limit]
    )
    extend(sold_ids or featured_ids or list(base.values_list("pk", flat=True)[:limit]))

    extend(
        base.filter(is_new_arrival=True)
        .order_by("-created_at", "pk")
        .values_list("pk", flat=True)[:limit]
    )
    extend(
        base.filter(sale_price__isnull=False, sale_price__lt=F("regular_price"))
        .order_by("-created_at", "pk")
        .values_list("pk", flat=True)[:limit]
    )
    return ids


def _apply_listing_collection(queryset, raw_collection):
    key = normalize_collection(raw_collection)
    if key == "featured":
        return queryset.filter(is_featured=True), key
    if key == "new-arrivals":
        return queryset.filter(is_new_arrival=True).order_by("-created_at", "pk"), key
    if key == "special-offers":
        return queryset.filter(
            sale_price__isnull=False,
            sale_price__lt=F("regular_price"),
        ).order_by("-created_at", "pk"), key
    if key == "best-selling":
        ranked = queryset.annotate(
            sold_quantity=Sum(
                "variants__sales_order_items__quantity",
                filter=Q(variants__sales_order_items__order__status=SalesOrder.Status.COMPLETED),
            )
        ).filter(sold_quantity__gt=0).order_by("-sold_quantity", "pk")
        if ranked.exists():
            return ranked, key
        featured = queryset.filter(is_featured=True)
        return (featured if featured.exists() else queryset), key
    return queryset, ""


def _products_page_context(request):
    context = catalog_context(include_filter_counts=True)
    queryset = catalog_queryset()

    selected_categories = _selected_category_names(context, request)
    selected_brands = _selected_brand_names(context, request)
    if selected_categories:
        queryset = queryset.filter(category__name__in=selected_categories)
    if selected_brands:
        queryset = queryset.filter(brand__name__in=selected_brands)

    queryset, collection_key = _apply_listing_collection(
        queryset,
        request.GET.get("collection", ""),
    )

    query = " ".join(str(request.GET.get("q") or "").split())
    if query:
        matched_ids = matching_product_ids(query)
        queryset = queryset.filter(pk__in=matched_ids)

    queryset = queryset.distinct()
    paginator = Paginator(queryset, PRODUCTS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))
    attach_catalog(context, page_obj.object_list)

    query_params = request.GET.copy()
    query_params.pop("page", None)
    context.update(
        selected_collection=collection_key,
        selected_collection_label=collection_label(collection_key),
        selected_category_name=selected_categories[0] if len(selected_categories) == 1 else "",
        selected_brand_name=selected_brands[0] if len(selected_brands) == 1 else "",
        search_query=query,
        search_result_count=paginator.count if query else len(context["products"]),
        page_obj=page_obj,
        paginator=paginator,
        pagination_total_count=paginator.count,
        pagination_items=[
            {"number": value, "ellipsis": value == paginator.ELLIPSIS}
            for value in paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1)
        ],
        pagination_query=query_params.urlencode(),
    )
    context["store_data"]["search_query"] = query
    return context


@ensure_csrf_cookie
def page(request, page_name="home"):
    if page_name not in PAGE_TEMPLATES:
        raise Http404("Page not found")

    if page_name == "home":
        product_ids = _home_product_ids()
        context = catalog_context(
            catalog_queryset().filter(pk__in=product_ids),
            include_filter_counts=True,
        )
        _apply_home_collections(context)
    elif page_name == "products":
        context = _products_page_context(request)
    elif page_name in {"categories", "brands"}:
        context = catalog_context(include_filter_counts=True)
    elif page_name == "cart":
        context = catalog_context(catalog_queryset()[:6])
    else:
        context = catalog_context()

    return render(request, f"storefront/pages/{PAGE_TEMPLATES[page_name]}.html", context)


@require_GET
def product_bootstrap(request):
    raw_ids = []
    for raw_value in request.GET.getlist("ids"):
        raw_ids.extend(value.strip() for value in raw_value.split(",") if value.strip())

    product_ids = []
    for product_id in raw_ids:
        if product_id not in product_ids:
            product_ids.append(product_id)
        if len(product_ids) >= 50:
            break

    if not product_ids:
        return JsonResponse({"products": []})

    catalog = prepare_catalog_products(
        catalog_queryset().filter(public_id__in=product_ids)
    )
    by_id = {product["id"]: product for product in catalog}
    ordered = [by_id[product_id] for product_id in product_ids if product_id in by_id]
    return JsonResponse({"products": browser_product_rows(ordered)})



def _contact_source_ip(request):
    raw = str(request.META.get("REMOTE_ADDR") or "").strip()
    if not raw:
        return None
    try:
        return str(ipaddress.ip_address(raw))
    except ValueError:
        return None


@ensure_csrf_cookie
def contact(request):
    context = catalog_context()
    source_ip = _contact_source_ip(request)
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            recent = 0
            if source_ip:
                recent = ContactMessage.objects.filter(
                    source_ip=source_ip,
                    created_at__gte=timezone.now() - timedelta(minutes=10),
                ).count()
            if recent >= 5:
                form.add_error(None, "Too many messages were sent recently. Please wait a few minutes and try again.")
            else:
                contact_message = ContactMessage.objects.create(
                    name=form.cleaned_data["name"],
                    email=form.cleaned_data["email"],
                    phone=form.cleaned_data["phone"],
                    subject=form.cleaned_data["subject"],
                    message=form.cleaned_data["message"],
                    source_ip=source_ip,
                )
                enqueue_contact_message_notification(contact_message)
                return redirect(reverse("storefront:contact") + "?sent=1")
    else:
        form = ContactForm()

    context.update(
        contact_form=form,
        contact_sent=request.GET.get("sent") == "1",
    )
    return render(request, "storefront/pages/contact.html", context)

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



@require_POST
def coupon_preview(request):
    """Validate one customer-supplied coupon without exposing the coupon catalog."""
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"valid": False, "discount": 0, "reason": "Invalid coupon request."}, status=400)

    code = str(payload.get("code") or "").strip().upper()
    cart_payload = payload.get("cart") or []
    if not code:
        return JsonResponse({"valid": False, "discount": 0, "reason": "Enter a coupon code."})
    if not isinstance(cart_payload, list) or not cart_payload or len(cart_payload) > 100:
        return JsonResponse({"valid": False, "discount": 0, "reason": "Your cart is empty or invalid."}, status=400)

    normalized = []
    for row in cart_payload:
        if not isinstance(row, dict):
            return JsonResponse({"valid": False, "discount": 0, "reason": "Your cart is invalid."}, status=400)
        try:
            variant_id = int(row.get("variant_id"))
            quantity = int(row.get("qty"))
        except (TypeError, ValueError):
            return JsonResponse({"valid": False, "discount": 0, "reason": "Your cart is invalid."}, status=400)
        if variant_id <= 0 or quantity <= 0 or quantity > 999:
            return JsonResponse({"valid": False, "discount": 0, "reason": "Your cart is invalid."}, status=400)
        normalized.append({"variant_id": variant_id, "qty": quantity})

    try:
        rows = _resolve_order_lines(normalized)
        _coupon, discount = coupon_discount_for_rows(code, rows)
    except (CheckoutError, PromotionError) as exc:
        reason = " ".join(str(value) for value in getattr(exc, "messages", [str(exc)]))
        return JsonResponse({"valid": False, "discount": 0, "reason": reason})

    subtotal = sum((row["unit_price"] * int(row["quantity"]) for row in rows), 0)
    return JsonResponse({
        "valid": True,
        "code": code,
        "discount": float(discount),
        "subtotal": float(subtotal),
        "reason": "",
    })

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
            phone = form.cleaned_data["phone"]
            ip_wait = throttle_seconds_remaining("checkout_ip", request, "*")
            phone_wait = throttle_seconds_remaining("checkout_phone", request, phone)
            if ip_wait or phone_wait:
                form.add_error(
                    None,
                    "Too many orders were placed recently from this connection or phone number. Please wait a few minutes and try again.",
                )
            else:
                try:
                    order, created = place_checkout_order(
                        form.cleaned_data,
                        campaign_attribution=campaign_attribution,
                        customer_account=account,
                    )
                    if created:
                        register_rate_event(
                            "checkout_ip",
                            request,
                            "*",
                            failure_limit=settings.CHECKOUT_RATE_LIMIT_IP,
                            window_seconds=settings.CHECKOUT_RATE_WINDOW,
                            lockout_seconds=settings.CHECKOUT_RATE_LOCKOUT_SECONDS,
                        )
                        register_rate_event(
                            "checkout_phone",
                            request,
                            phone,
                            failure_limit=settings.CHECKOUT_RATE_LIMIT_PHONE,
                            window_seconds=settings.CHECKOUT_RATE_WINDOW,
                            lockout_seconds=settings.CHECKOUT_RATE_LOCKOUT_SECONDS,
                        )
                    _grant_checkout_success(request, order.order_number)
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


CHECKOUT_SUCCESS_SESSION_KEY = "storefront_checkout_success_orders"


def _grant_checkout_success(request, order_number):
    grants = [
        str(value)
        for value in request.session.get(CHECKOUT_SUCCESS_SESSION_KEY, [])
        if value
    ]
    if order_number not in grants:
        grants.append(order_number)
    request.session[CHECKOUT_SUCCESS_SESSION_KEY] = grants[-5:]


def _has_checkout_success_grant(request, order_number):
    return order_number in {
        str(value)
        for value in request.session.get(CHECKOUT_SUCCESS_SESSION_KEY, [])
        if value
    }


@never_cache
def checkout_success(request, order_number):
    legacy_token = str(request.GET.get("token") or "").strip()
    if legacy_token:
        try:
            verify_success_token(order_number, legacy_token)
        except CheckoutError as exc:
            raise Http404("Order confirmation not found") from exc
        _grant_checkout_success(request, order_number)
        response = redirect(
            reverse("storefront:checkout_success", kwargs={"order_number": order_number})
        )
        response["Referrer-Policy"] = "no-referrer"
        return response

    if not _has_checkout_success_grant(request, order_number):
        raise Http404("Order confirmation not found")

    order = get_object_or_404(
        SalesOrder.objects.select_related("customer", "warehouse").prefetch_related("items__variant__product"),
        order_number=order_number,
        channel=SalesOrder.Channel.ONLINE,
    )
    context = catalog_context()
    context.update(
        order=order,
        checkout_complete=True,
        purchase_tracking_data=_purchase_tracking_data(order),
    )
    response = render(request, "storefront/pages/checkout_success.html", context)
    response["Referrer-Policy"] = "no-referrer"
    response["Cache-Control"] = "no-store, private"
    return response


def product_detail(request, slug=None, product_id=None):
    qs = catalog_queryset()
    if slug:
        product_obj = get_object_or_404(qs, slug=slug)
    elif product_id:
        product_obj = get_object_or_404(qs, public_id=product_id)
    else:
        raise Http404("Product not found")

    related = list(
        catalog_queryset()
        .filter(category_id=product_obj.category_id)
        .exclude(pk=product_obj.pk)[:4]
    )
    if len(related) < 4:
        existing_ids = [product_obj.pk, *[row.pk for row in related]]
        related.extend(
            list(
                catalog_queryset()
                .exclude(pk__in=existing_ids)[: 4 - len(related)]
            )
        )

    context = catalog_context([product_obj, *related])
    product = next(row for row in context["catalog"] if row["pk"] == product_obj.pk)
    context.update(product=product, has_local_benefits=True)
    context["store_data"]["current_product"] = product["id"]
    context["related_products"] = [
        row for row in context["catalog"] if row["pk"] != product_obj.pk
    ][:4]
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
