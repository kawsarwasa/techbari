from django.urls import path

from . import views

app_name = "customer_accounts"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("orders/", views.orders, name="orders"),
    path("orders/<str:order_number>/", views.order_detail, name="order_detail"),
    path("profile/", views.profile, name="profile"),
    path("addresses/", views.addresses, name="addresses"),
    path("addresses/add/", views.address_add, name="address_add"),
    path("addresses/<int:pk>/edit/", views.address_edit, name="address_edit"),
    path("addresses/<int:pk>/delete/", views.address_delete, name="address_delete"),
    path("password/", views.password_change, name="password_change"),
    path("warranty/", views.warranty_lookup, name="warranty"),
]
