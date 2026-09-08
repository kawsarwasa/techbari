from django.urls import path

from . import views

app_name = "integrations"

urlpatterns = [
    path("courier/<str:code>/webhook/", views.courier_webhook, name="courier_webhook"),
]
