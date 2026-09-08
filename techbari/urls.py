from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

handler404 = "techbari.views.not_found"
handler500 = "techbari.views.server_error"

urlpatterns = [
    path("dashboard/", include("backoffice.urls")),
    path("account/", include("customer_accounts.urls")),
    path("", include("storefront.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
