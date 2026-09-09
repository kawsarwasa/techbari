from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from storefront.context import catalog_context


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
    return render(request, "404.html", catalog_context(), status=404)


def server_error(request):
    # Keep error rendering independent of any catalog/context source.
    return render(request, "500.html", status=500)
