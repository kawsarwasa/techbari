import html
import re
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from PIL import Image, ImageOps, UnidentifiedImageError

from catalog.models import Product, ProductImage
from catalog.official_product_images import OFFICIAL_PRODUCT_IMAGE_SOURCES


OFFICIAL_PREFIX = "[Official gallery]"
DEMO_PREFIX = "[Demo gallery]"
MAX_DOWNLOAD_BYTES = 10 * 1024 * 1024
TARGET_SIZE = (1200, 1200)
MIN_DIMENSION = 300
DEFAULT_IMAGES_PER_PRODUCT = 4


def _host_allowed(hostname, allowed_hosts):
    host = (hostname or "").lower().strip(".")
    return any(host == allowed or host.endswith("." + allowed) for allowed in allowed_hosts)


def _srcset_urls(value):
    rows = []
    for part in (value or "").split(","):
        token = part.strip().split()
        if not token:
            continue
        weight = 0
        if len(token) > 1:
            suffix = token[-1].lower()
            try:
                if suffix.endswith("w"):
                    weight = int(float(suffix[:-1]))
                elif suffix.endswith("x"):
                    weight = int(float(suffix[:-1]) * 1000)
            except ValueError:
                weight = 0
        rows.append((weight, token[0]))
    return [url for _weight, url in sorted(rows, reverse=True)]


class _ImageHTMLParser(HTMLParser):
    URL_ATTRS = ("src", "data-src", "data-original", "data-lazy-src", "data-zoom-image")
    SRCSET_ATTRS = ("srcset", "data-srcset")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.candidates = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() not in {"img", "source"}:
            return
        values = {str(key).lower(): value or "" for key, value in attrs}
        context = " ".join(
            values.get(key, "")
            for key in ("alt", "title", "class", "id", "data-alt")
        )
        for key in self.URL_ATTRS:
            if values.get(key):
                self.candidates.append((values[key], context))
        for key in self.SRCSET_ATTRS:
            for url in _srcset_urls(values.get(key)):
                self.candidates.append((url, context))


def _normalize_url(value, source_page):
    raw = html.unescape(str(value or "").strip()).replace("\\/", "/")
    if not raw or raw.startswith(("data:", "blob:")):
        return ""
    if raw.startswith("//"):
        raw = "https:" + raw
    url = urljoin(source_page, raw)
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return ""
    return url


def _candidate_score(url, context, match_terms):
    haystack = f"{url} {context}".lower()
    score = 0
    for term in match_terms:
        clean = str(term).lower()
        if clean and clean in haystack:
            score += 3
    if any(marker in haystack for marker in ("product", "gallery", "hero", "front", "back", "side", "detail")):
        score += 1
    if any(marker in haystack for marker in ("logo", "icon", "flag", "payment", "avatar", "review")):
        score -= 5
    return score


def _discover_image_candidates(page_html, config):
    source_page = config["source_page"]
    allowed_hosts = tuple(value.lower() for value in config["allowed_hosts"])
    match_terms = tuple(config.get("match_terms", ()))

    parser = _ImageHTMLParser()
    parser.feed(page_html)

    # Some manufacturer pages keep lazy-loaded gallery URLs in JSON/script data rather
    # than <img> attributes. Capture those too, then score them with the same rules.
    raw_urls = re.findall(
        r"""(?P<url>https?:\\?/\\?/[^\"'<>\s]+?\.(?:jpe?g|png|webp)(?:\?[^\"'<>\s]*)?)""",
        page_html,
        flags=re.IGNORECASE,
    )
    parser.candidates.extend((value, "") for value in raw_urls)

    seen = set()
    ranked = []
    for raw_url, context in parser.candidates:
        url = _normalize_url(raw_url, source_page)
        if not url or url in seen:
            continue
        seen.add(url)
        if not _host_allowed(urlparse(url).hostname, allowed_hosts):
            continue
        score = _candidate_score(url, context, match_terms)
        if score <= 0 and not config.get("allow_unmatched", False):
            continue
        ranked.append((score, url))

    ranked.sort(key=lambda row: (-row[0], row[1]))
    return [url for _score, url in ranked]


def _fetch_html(url, timeout=20):
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; TechBariCatalog/1.0)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        data = response.read(MAX_DOWNLOAD_BYTES + 1)
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise CommandError(f"Official source page is unexpectedly large: {url}")
    return data.decode("utf-8", errors="replace")


def _download_bytes(url, source_page, timeout=25):
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; TechBariCatalog/1.0)",
            "Accept": "image/avif,image/webp,image/png,image/jpeg,*/*;q=0.5",
            "Referer": source_page,
        },
    )
    with urlopen(request, timeout=timeout) as response:
        length = response.headers.get("Content-Length")
        if length and int(length) > MAX_DOWNLOAD_BYTES:
            raise ValueError("image exceeds 10MB safety limit")
        data = response.read(MAX_DOWNLOAD_BYTES + 1)
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise ValueError("image exceeds 10MB safety limit")
    return data


def _prepare_webp(image_bytes):
    try:
        with Image.open(BytesIO(image_bytes)) as source:
            source.load()
            if min(source.width, source.height) < MIN_DIMENSION:
                raise ValueError(
                    f"image is too small ({source.width}x{source.height}); expected product photography"
                )
            has_alpha = "A" in source.getbands() or "transparency" in source.info
            mode = "RGBA" if has_alpha else "RGB"
            image = source.convert(mode)
            image = ImageOps.contain(image, TARGET_SIZE, method=Image.Resampling.LANCZOS)
            output = BytesIO()
            image.save(output, format="WEBP", quality=90, method=6)
            return output.getvalue()
    except UnidentifiedImageError as exc:
        raise ValueError("download is not a valid image") from exc


def _official_filename(public_id, index):
    safe_id = re.sub(r"[^a-z0-9-]+", "-", str(public_id).lower()).strip("-") or "product"
    return f"official-{safe_id}-{index:02d}.webp"


class Command(BaseCommand):
    help = (
        "Download product-specific images from curated official manufacturer pages "
        "and attach them to the 10 TechBari demo products."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--product",
            action="append",
            default=[],
            help="Limit to a demo public_id (repeatable), e.g. --product q20i.",
        )
        parser.add_argument(
            "--refresh",
            action="store_true",
            help="Replace only previously downloaded [Official gallery] rows.",
        )
        parser.add_argument(
            "--keep-generated",
            action="store_true",
            help="Keep synthetic [Demo gallery] image-file variants after official images are added.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=DEFAULT_IMAGES_PER_PRODUCT,
            help=f"Maximum official images per product (default {DEFAULT_IMAGES_PER_PRODUCT}).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        requested = list(dict.fromkeys(options["product"]))
        unknown = [value for value in requested if value not in OFFICIAL_PRODUCT_IMAGE_SOURCES]
        if unknown:
            raise CommandError("Unknown official demo product id(s): " + ", ".join(unknown))

        product_ids = requested or list(OFFICIAL_PRODUCT_IMAGE_SOURCES)
        per_product_limit = max(1, min(int(options["limit"] or DEFAULT_IMAGES_PER_PRODUCT), 8))
        total_saved = 0
        failures = []

        for public_id in product_ids:
            config = OFFICIAL_PRODUCT_IMAGE_SOURCES[public_id]
            product = Product.objects.filter(public_id=public_id).first()
            if product is None:
                self.stdout.write(self.style.WARNING(
                    f"{public_id}: product not found; run seed_real_demo_products first."
                ))
                failures.append(public_id)
                continue

            if options["refresh"]:
                product.images.filter(alt_text__startswith=OFFICIAL_PREFIX).delete()
            elif product.images.filter(alt_text__startswith=OFFICIAL_PREFIX).exists():
                self.stdout.write(f"{public_id}: official gallery already exists; use --refresh to replace it.")
                continue

            candidates = []
            for value in config.get("direct_images", ()):
                normalized = _normalize_url(value, config["source_page"])
                if normalized and normalized not in candidates:
                    candidates.append(normalized)

            try:
                page_html = _fetch_html(config["source_page"])
                for value in _discover_image_candidates(page_html, config):
                    if value not in candidates:
                        candidates.append(value)
            except Exception as exc:
                self.stdout.write(self.style.WARNING(
                    f"{public_id}: source page discovery warning: {exc}"
                ))

            saved = 0
            for image_url in candidates:
                if saved >= per_product_limit:
                    break
                if not _host_allowed(
                    urlparse(image_url).hostname,
                    tuple(value.lower() for value in config["allowed_hosts"]),
                ):
                    continue
                try:
                    prepared = _prepare_webp(
                        _download_bytes(image_url, config["source_page"])
                    )
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(
                        f"{public_id}: skipped {image_url} ({exc})"
                    ))
                    continue

                role = ProductImage.Role.DETAIL if saved == per_product_limit - 1 else ProductImage.Role.GALLERY
                row = ProductImage(
                    product=product,
                    alt_text=f"{OFFICIAL_PREFIX} {product.name} #{saved + 1}",
                    role=role,
                    sort_order=20 + saved,
                )
                row.image.save(
                    _official_filename(public_id, saved + 1),
                    ContentFile(prepared),
                    save=False,
                )
                row.save()
                saved += 1
                total_saved += 1

            if saved:
                if not options["keep_generated"]:
                    # Remove only the Pillow-generated demo variants. Static/manual source
                    # images and the original product primary image remain untouched.
                    product.images.filter(
                        alt_text__startswith=DEMO_PREFIX,
                        static_path="",
                    ).exclude(image="").delete()
                self.stdout.write(self.style.SUCCESS(
                    f"{public_id}: added {saved} official product image(s) "
                    f"from {config['source_page']}"
                ))
            else:
                failures.append(public_id)
                self.stdout.write(self.style.WARNING(
                    f"{public_id}: no suitable official image could be downloaded."
                ))

        self.stdout.write(self.style.SUCCESS(
            f"Official demo gallery sync complete: {total_saved} image(s) saved "
            f"across {len(product_ids) - len(failures)} product(s)."
        ))
        if failures:
            self.stdout.write(self.style.WARNING(
                "No official images saved for: " + ", ".join(failures)
            ))
