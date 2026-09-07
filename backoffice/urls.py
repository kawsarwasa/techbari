from django.urls import path

from . import catalog_views, inventory_views, views
from .page_registry import PAGES

app_name = "backoffice"

catalog_patterns = [
    path("variants/", catalog_views.variants, name="catalog_variants"),
    path("variants/form/", catalog_views.variant_form, name="catalog_variant_form"),
    path("product-media/", catalog_views.media, name="catalog_media"),
    path("product-media/form/", catalog_views.media_form, name="catalog_media_form"),
    path("specifications/", catalog_views.specifications, name="catalog_specifications"),
    path("specifications/form/", catalog_views.specification_form, name="catalog_specification_form"),
]

inventory_patterns = [
    path("inventory/movements/", inventory_views.movements, name="inventory_movements"),
    path("inventory/low-stock/", inventory_views.low_stock, name="inventory_low_stock"),
]

urlpatterns = catalog_patterns + inventory_patterns + [
    path(info["path"], views.page, {"page_name": name}, name=name)
    for name, info in PAGES.items()
]
urlpatterns += [path("<slug:page>.html", views.legacy_page, name="legacy_page")]
