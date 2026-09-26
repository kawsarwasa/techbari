from django.core.management.base import BaseCommand
from django.db import transaction

from store_settings.models import HeroBanner, HomeSection


DEFAULT_SECTIONS = (
    (HomeSection.Key.HERO, "Featured Offers", 10),
    (HomeSection.Key.CATEGORIES, "Shop by Category", 20),
    (HomeSection.Key.FEATURED, "Featured Products", 30),
    (HomeSection.Key.PROMOS, "Special Collections", 40),
)

DEFAULT_BANNERS = (
    {
        "eyebrow": "Sound that moves you",
        "title": "Premium Audio\nFor a Better You",
        "description": "TWS Earbuds | Headphones | Speakers\nDiscover authentic sound. Only at TechBari.",
        "cta_label": "Shop Audio Products →",
        "cta_url": "/products/",
        "fallback_static": "store/images/hero-audio.webp",
        "alt_text": "Premium audio products",
        "sort_order": 10,
    },
    {
        "eyebrow": "Power your day",
        "title": "Reliable Power\nAlways With You",
        "description": "Power Banks | Chargers | Cables\nFast, dependable charging for every device.",
        "cta_label": "Shop Power Solutions →",
        "cta_url": "/products/",
        "fallback_static": "store/images/promo-power.webp",
        "alt_text": "Power banks chargers and cables",
        "sort_order": 20,
    },
    {
        "eyebrow": "Style meets function",
        "title": "Smartwatches\nFor a Smarter You",
        "description": "Track. Stay Connected. Do More.\nSmart wearables for everyday life.",
        "cta_label": "Shop Smartwatches →",
        "cta_url": "/products/",
        "fallback_static": "store/images/promo-watch.webp",
        "alt_text": "Smartwatch collection",
        "sort_order": 30,
    },
)


class Command(BaseCommand):
    help = (
        "Restore missing default homepage sections and default hero banners "
        "without overwriting existing CMS configuration."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        created_sections = 0
        created_banners = 0

        for key, title, sort_order in DEFAULT_SECTIONS:
            _section, created = HomeSection.objects.get_or_create(
                key=key,
                defaults={
                    "title": title,
                    "sort_order": sort_order,
                    "is_enabled": True,
                },
            )
            created_sections += int(created)

        for row in DEFAULT_BANNERS:
            _banner, created = HeroBanner.objects.get_or_create(
                title=row["title"],
                defaults={**row, "is_active": True},
            )
            created_banners += int(created)

        self.stdout.write(
            self.style.SUCCESS(
                "Homepage defaults ready: "
                f"{created_sections} section(s) created, "
                f"{created_banners} hero banner(s) created. "
                "Existing CMS rows were preserved."
            )
        )
