from django.urls import path
from . import views

app_name = "storefront"
urlpatterns = [
    path("", views.page, name="home"),
    path("products/", views.page, {"page_name": "products"}, name="products"),
    path("product/<slug:slug>/", views.product_detail, name="product_detail"),
    path("product/id/<slug:product_id>/", views.product_detail, name="product_by_id"),
    *[path(name.replace("_", "-") + "/", views.page, {"page_name": name}, name=name)
      for name in ("cart", "checkout", "wishlist", "track_order", "login", "register", "contact")],
    path("<slug:page>.html", views.legacy_page, name="legacy_page"),
]
