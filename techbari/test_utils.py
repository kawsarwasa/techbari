from django.contrib.auth import get_user_model


def login_test_superuser(test_case):
    """Authenticate a real staff identity while leaving StaffAccessMiddleware enabled."""
    User = get_user_model()
    user, _ = User.objects.get_or_create(
        username="__techbari_test_superuser__",
        defaults={
            "email": "test-superuser@techbari.local",
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
        },
    )
    changed = []
    for field in ("is_staff", "is_superuser", "is_active"):
        if not getattr(user, field):
            setattr(user, field, True)
            changed.append(field)
    if changed:
        user.save(update_fields=changed)
    test_case.client.force_login(user)
    test_case.staff_user = user
    return user
