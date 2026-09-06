"""Validate pages and assets without a database or Django's database test runner."""
import argparse
import ast
import json
import os
from pathlib import Path
import re
import sys
from html.parser import HTMLParser
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "techbari.settings")
import django
django.setup()

from django.conf import settings
from django.contrib.staticfiles import finders
from django.db import connections
from django.template.loader import get_template
from django.test import Client, RequestFactory, override_settings
from django.urls import reverse
from backoffice.page_registry import PAGES
from storefront.mock_data import PRODUCTS
from storefront.views import PAGE_TEMPLATES
from techbari.views import server_error


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ("src", "href", "data-list-url", "data-row-link", "data-edit-image") and value:
                self.urls.add(value)


def validate(export_dir=None):
    client = Client()
    paths = {reverse("storefront:" + name) for name in PAGE_TEMPLATES}
    paths.update(reverse("backoffice:" + name) for name in PAGES)
    paths.update(reverse("storefront:product_detail", kwargs={"slug": p["slug"]}) for p in PRODUCTS)
    paths.update(reverse("storefront:product_by_id", kwargs={"product_id": p["id"]}) for p in PRODUCTS)
    paths.update(("/dashboard/orders/detail/?id=2", "/dashboard/customers/detail/?id=2"))
    paths.update(("/dashboard/orders/detail/?id=999&local=1", "/dashboard/customers/detail/?id=999&local=1"))
    snapshots, links = {}, set()
    # Any accidental database connection is a test failure, including error views.
    with patch.object(connections["default"], "ensure_connection", side_effect=AssertionError("Database access attempted")):
        for path in sorted(paths):
            response = client.get(path)
            assert response.status_code == 200, (path, response.status_code)
            source = response.content.decode()
            assert "{%" not in source, path
            parser = Links(); parser.feed(source); links.update(parser.urls)
            snapshots[path] = source
        for link in links:
            parsed = urlsplit(link)
            if parsed.scheme or parsed.netloc or link.startswith("#"):
                continue
            if parsed.path.startswith(settings.STATIC_URL):
                asset = parsed.path.removeprefix(settings.STATIC_URL)
                assert finders.find(asset), ("Missing static asset", asset)
            elif parsed.path:
                assert ".html" not in parsed.path, ("Legacy navigation link", link)
                assert client.get(link).status_code == 200, ("Broken navigation", link)
        for legacy, target in [("/products.html?q=anker", "/products/?q=anker"),
                               ("/dashboard/product-edit.html?id=2", "/dashboard/products/edit/?id=2")]:
            response = client.get(legacy)
            assert response.status_code == 302 and response.url == target, legacy
        for info in PAGES.values():
            assert client.get("/dashboard/" + info["legacy"] + ".html", follow=True).status_code == 200
        with override_settings(DEBUG=False):
            for path in ("/missing-page/", "/product/no-such-product/", "/product/id/missing/",
                         "/dashboard/orders/detail/?id=9999", "/dashboard/customers/detail/?id=invalid"):
                response = client.get(path)
                assert response.status_code == 404 and b"TechBari" in response.content
            assert server_error(RequestFactory().get("/")).status_code == 500
    for template in (ROOT / "templates").rglob("*.html"):
        get_template(template.relative_to(ROOT / "templates").as_posix())
        for asset in re.findall(r"{%\s*static\s+['\"]([^'\"]+)['\"]\s*%}", template.read_text(encoding="utf8")):
            assert finders.find(asset), (template, asset)
    for path in ROOT.rglob("*.py"):
        if ".venv" not in path.parts:
            ast.parse(path.read_text(encoding="utf8"), filename=str(path))
    for path in list((ROOT / "static").rglob("*.css")) + list((ROOT / "templates").rglob("*.html")):
        for size in re.findall(r"font-size\s*:\s*([\d.]+)px", path.read_text(encoding="utf8")):
            assert float(size) >= 13, (path, size)
    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.dummy"
    assert not {"django.contrib.auth", "django.contrib.sessions", "django.contrib.admin"}.intersection(settings.INSTALLED_APPS)
    assert not (ROOT / "db.sqlite3").exists()
    assert not list((ROOT / "storefront").glob("migrations/*.py"))
    assert not list((ROOT / "backoffice").glob("migrations/*.py"))
    if export_dir:
        export_dir.mkdir(parents=True, exist_ok=True)
        (export_dir / "pages.json").write_text(json.dumps(snapshots, ensure_ascii=False), encoding="utf8")
    print(f"PASS: {len(paths)} page/detail URLs, {len(links)} link/asset targets, all templates and Python syntax.")
    print("PASS: legacy redirects, branded errors, minimum declared font size, no database access.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-dir", type=Path)
    validate(parser.parse_args().export_dir)
