from django.shortcuts import render
from storefront.context import catalog_context


def not_found(request, exception):
    return render(request, "404.html", catalog_context(), status=404)


def server_error(request):
    # Keep error rendering independent of any catalog/context source.
    return render(request, "500.html", status=500)
