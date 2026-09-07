from django.urls import path

from . import catalog_views, customer_views, inventory_views, pos_views, purchase_views, sales_views, views
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

purchase_patterns = [
    path("suppliers/<int:supplier_id>/delete/", purchase_views.supplier_delete, name="supplier_delete"),
    path("purchases/<int:purchase_id>/", purchase_views.purchase_detail, name="purchase_detail"),
    path("purchases/<int:purchase_id>/receive/", purchase_views.purchase_receive, name="purchase_receive"),
    path("purchases/<int:purchase_id>/payment/", purchase_views.purchase_payment, name="purchase_payment"),
    path("purchases/<int:purchase_id>/return/", purchase_views.purchase_return, name="purchase_return"),
    path("purchases/<int:purchase_id>/cancel/", purchase_views.purchase_cancel, name="purchase_cancel"),
    path("purchases/<int:purchase_id>/delete/", purchase_views.purchase_delete, name="purchase_delete"),
]

customer_patterns = [
    path("customers/groups/", customer_views.customer_groups, name="customer_groups"),
    path("customers/groups/<int:group_id>/delete/", customer_views.customer_group_delete, name="customer_group_delete"),
    path("customers/<int:customer_id>/", customer_views.customer_detail, name="customer_detail_id"),
    path("customers/<int:customer_id>/delete/", customer_views.customer_delete, name="customer_delete"),
]

sales_patterns = [
    path("orders/<int:order_id>/", sales_views.order_detail, name="order_detail_id"),
    path("orders/<int:order_id>/confirm/", sales_views.order_confirm, name="order_confirm"),
    path("orders/<int:order_id>/process/", sales_views.order_process, name="order_process"),
    path("orders/<int:order_id>/complete/", sales_views.order_complete, name="order_complete"),
    path("orders/<int:order_id>/cancel/", sales_views.order_cancel, name="order_cancel"),
    path("orders/<int:order_id>/payment/", sales_views.order_payment, name="order_payment"),
    path("orders/<int:order_id>/delete/", sales_views.order_delete, name="order_delete"),
]

pos_patterns = [
    path("pos/", pos_views.pos, name="pos"),
    path("pos/action/", pos_views.pos_action, name="pos_action"),
    path("pos/held/<int:order_id>/", pos_views.pos_hold_detail, name="pos_hold_detail"),
    path("pos/receipt/<int:order_id>/", pos_views.pos_receipt, name="pos_receipt"),
]

urlpatterns = catalog_patterns + inventory_patterns + purchase_patterns + customer_patterns + sales_patterns + pos_patterns + [
    path(info["path"], views.page, {"page_name": name}, name=name)
    for name, info in PAGES.items()
    if name != "pos"
]
urlpatterns += [path("<slug:page>.html", views.legacy_page, name="legacy_page")]
