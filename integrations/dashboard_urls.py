from django.urls import path

from backoffice import integration_views

app_name = "integration_admin"

urlpatterns = [
    path("", integration_views.integration_settings, name="integration_settings"),
    path("process/", integration_views.integration_process, name="integration_process"),
    path("deliveries/<int:message_id>/retry/", integration_views.integration_retry, name="integration_retry"),
    path("notifications/read-all/", integration_views.notifications_read_all, name="notifications_read_all"),
    path("notifications/<int:notification_id>/read/", integration_views.notification_read, name="notification_read"),
]
