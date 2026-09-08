def staff_notifications(request):
    if not request.path.startswith("/dashboard/") or not getattr(request.user, "is_authenticated", False):
        return {}
    try:
        from .services import unread_notifications_for
        return {"staff_unread_notification_count": unread_notifications_for(request.user).count()}
    except Exception:
        return {"staff_unread_notification_count": 0}
