from django.urls import path
from . import views

app_name = "storefront"
urlpatterns = [
    path("", views.page, name="home"),
    path("products/", views.page, {"page_name": "products"}, name="products"),
    path("product/<slug:slug>/", views.product_detail, name="product_detail"),
    path("product/id/<slug:product_id>/", views.product_detail, name="product_by_id"),
    path("checkout/", views.checkout, name="checkout"),
    path("checkout/success/<str:order_number>/", views.checkout_success, name="checkout_success"),
    path("terms-and-conditions/", views.content_page, {"slug": "terms-and-conditions"}, name="terms"),
    path("privacy-policy/", views.content_page, {"slug": "privacy-policy"}, name="privacy_policy"),
    path("return-refund-policy/", views.content_page, {"slug": "return-refund-policy"}, name="return_policy"),
    path("shipping-policy/", views.content_page, {"slug": "shipping-policy"}, name="shipping_policy"),
    *[
        path(name.replace("_", "-") + "/", views.page, {"page_name": name}, name=name)
        for name in ("cart", "wishlist", "track_order", "login", "register", "contact")
    ],
    path("<slug:page>.html", views.legacy_page, name="legacy_page"),
]
