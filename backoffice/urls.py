from django.urls import path
from . import views
from .page_registry import PAGES

app_name = "backoffice"
urlpatterns = [path(info["path"], views.page, {"page_name": name}, name=name)
               for name, info in PAGES.items()]
urlpatterns += [path("<slug:page>.html", views.legacy_page, name="legacy_page")]
