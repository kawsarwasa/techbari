from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "techbari-development-change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "staff_access.apps.StaffAccessConfig",
    "catalog", "inventory", "serial_tracking", "purchasing", "customers", "sales",
    "payments.apps.PaymentsConfig", "shipping.apps.ShippingConfig", "returns.apps.ReturnsConfig",
    "accounting.apps.AccountingConfig", "expenses.apps.ExpensesConfig", "reports.apps.ReportsConfig",
    "promotions.apps.PromotionsConfig", "store_settings.apps.StoreSettingsConfig", "storefront", "backoffice",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "promotions.middleware.CampaignTrackingMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "staff_access.middleware.StaffAccessMiddleware",
]

ROOT_URLCONF = "techbari.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "techbari.wsgi.application"
ASGI_APPLICATION = "techbari.asgi.application"

DATABASES = {"default": {"ENGINE": "django.db.backends.mysql", "NAME": os.getenv("DB_NAME", "techbari"), "USER": os.getenv("DB_USER", "root"), "PASSWORD": os.getenv("DB_PASSWORD", ""), "HOST": os.getenv("DB_HOST", "127.0.0.1"), "PORT": os.getenv("DB_PORT", "3306"), "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")), "OPTIONS": {"charset": "utf8mb4", "init_command": "SET sql_mode='STRICT_TRANS_TABLES'"}}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "backoffice:login"
LOGIN_REDIRECT_URL = "backoffice:dashboard"
STAFF_AUTH_ENABLED = env_bool("STAFF_AUTH_ENABLED", True)
STAFF_IDLE_TIMEOUT = int(os.getenv("STAFF_IDLE_TIMEOUT", "1800"))
SESSION_COOKIE_AGE = int(os.getenv("SESSION_COOKIE_AGE", "28800"))
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

EMAIL_BACKEND = os.getenv("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@techbari.local")

# Legacy module tests predate staff authentication. The custom runner keeps
# those tests focused on business logic, while staff_access tests explicitly
# re-enable authentication to validate the real security boundary.
TEST_RUNNER = "techbari.test_runner.TechBariTestRunner"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
