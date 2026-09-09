from django.conf import settings
from django.core.checks import Error, Tags, Warning, register


@register(Tags.security, deploy=True)
def production_security_checks(app_configs, **kwargs):
    issues = []
    if settings.DEBUG:
        issues.append(Error("DEBUG must be False in production.", id="techbari.E001"))
    if not getattr(settings, "STAFF_AUTH_ENABLED", True):
        issues.append(Error("STAFF_AUTH_ENABLED must remain enabled in production.", id="techbari.E002"))
    if not getattr(settings, "SECURE_SSL_REDIRECT", False):
        issues.append(Error("SECURE_SSL_REDIRECT should be enabled for the production site.", id="techbari.E003"))
    if not getattr(settings, "SESSION_COOKIE_SECURE", False):
        issues.append(Error("SESSION_COOKIE_SECURE must be enabled in production.", id="techbari.E004"))
    if not getattr(settings, "CSRF_COOKIE_SECURE", False):
        issues.append(Error("CSRF_COOKIE_SECURE must be enabled in production.", id="techbari.E005"))
    if not getattr(settings, "INTEGRATION_REQUIRE_HTTPS", False):
        issues.append(Error("INTEGRATION_REQUIRE_HTTPS must be enabled in production.", id="techbari.E006"))
    if not getattr(settings, "COURIER_WEBHOOK_REQUIRE_TIMESTAMP", False):
        issues.append(Error("Timestamped courier webhook signatures must be enabled in production.", id="techbari.E007"))
    if not getattr(settings, "SECURE_HSTS_SECONDS", 0):
        issues.append(Warning("HSTS is disabled. Start with a tested value before increasing or enabling preload.", id="techbari.W001"))
    backend = str(getattr(settings, "EMAIL_BACKEND", ""))
    if backend.endswith("console.EmailBackend"):
        issues.append(Warning("Console email backend is configured; real production email will not be delivered.", id="techbari.W002"))
    db = settings.DATABASES.get("default", {})
    if not db.get("PASSWORD"):
        issues.append(Warning("The default database connection has an empty password.", id="techbari.W003"))
    if any(host in {"127.0.0.1", "localhost"} for host in getattr(settings, "ALLOWED_HOSTS", [])):
        issues.append(Warning("ALLOWED_HOSTS still contains localhost entries.", id="techbari.W004"))
    return issues
