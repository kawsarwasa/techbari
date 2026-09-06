from django.urls import include, path

handler404 = "techbari.views.not_found"
handler500 = "techbari.views.server_error"

urlpatterns = [
    path("dashboard/", include("backoffice.urls")),
    path("", include("storefront.urls")),
]
