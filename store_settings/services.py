from decimal import Decimal

from django.db.models import Q
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from .models import ContentPage, HeroBanner, HomeSection, StoreSettings


def get_store_settings():
    return StoreSettings.get_solo()


def _safe_html_lines(value):
    return escape(value or "").replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")


def live_hero_banners():
    now = timezone.now()
    return HeroBanner.objects.filter(is_active=True).filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now)).filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now)).order_by("sort_order", "id")


def serialize_hero_banner(banner):
    image_url = banner.image.url if banner.image else static(banner.fallback_static or "store/images/hero-audio.webp")
    href = banner.cta_url or reverse("storefront:products")
    return {
        "id": banner.pk,
        "eyebrow": banner.eyebrow,
        "title": _safe_html_lines(banner.title),
        "text": _safe_html_lines(banner.description),
        "cta": banner.cta_label or "Shop Now →",
        "href": href,
        "img": image_url,
        "alt": banner.alt_text or banner.title,
    }


def homepage_sections():
    return list(HomeSection.objects.order_by("sort_order", "id"))


def published_pages():
    return {page.slug: page for page in ContentPage.objects.filter(is_published=True)}


def delivery_payload(store=None):
    store = store or get_store_settings()
    return {
        "inside_charge": float(store.delivery_inside_dhaka_charge),
        "outside_charge": float(store.delivery_outside_dhaka_charge),
        "free_threshold": float(store.free_delivery_threshold),
        "inside_days": f"{store.delivery_inside_days_min}-{store.delivery_inside_days_max} days",
        "outside_days": f"{store.delivery_outside_days_min}-{store.delivery_outside_days_max} days",
        "cod_enabled": store.cod_enabled,
    }


def shipping_charge_for_subtotal(subtotal, zone, store=None):
    store = store or get_store_settings()
    subtotal = Decimal(subtotal or 0)
    threshold = Decimal(store.free_delivery_threshold or 0)
    if threshold > 0 and subtotal >= threshold:
        return Decimal("0.00")
    if zone == "inside":
        return Decimal(store.delivery_inside_dhaka_charge)
    if zone == "outside":
        return Decimal(store.delivery_outside_dhaka_charge)
    return None


def storefront_cms_context():
    store = get_store_settings()
    slides = [serialize_hero_banner(banner) for banner in live_hero_banners()]
    return {
        "store_settings": store,
        "hero_slides": slides,
        "homepage_sections": homepage_sections(),
        "content_pages": published_pages(),
        "delivery": delivery_payload(store),
        "home_seo_title": store.homepage_seo_title or store.seo_title or store.store_name,
        "home_seo_description": store.homepage_seo_description or store.seo_description,
    }
