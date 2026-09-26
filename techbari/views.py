from django.db import connection
from django.http import HttpResponsePermanentRedirect, JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from storefront.context import catalog_context


@require_GET
def favicon(request):
    """Provide a stable root favicon target for browsers that request /favicon.ico directly."""
    return HttpResponsePermanentRedirect(static("store/images/techbari-favicon.svg"))


@never_cache
@require_GET
def health(request):
    """Minimal liveness/readiness endpoint; never returns configuration or secrets."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


def not_found(request, exception):
    if request.path.startswith("/dashboard/") and getattr(request.user, "is_authenticated", False):
        return render(request, "backoffice/errors/404.html", status=404)
    return render(request, "404.html", catalog_context(), status=404)


def server_error(request):
    # Keep error rendering independent of any catalog/context source.
    return render(request, "500.html", status=500)
