from pathlib import Path
import os

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG", True)
_DEVELOPMENT_SECRET = "techbari-development-change-me"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", _DEVELOPMENT_SECRET).strip()
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# Fail closed when the application is explicitly placed in production mode.
if not DEBUG:
    if not SECRET_KEY or SECRET_KEY == _DEVELOPMENT_SECRET or len(SECRET_KEY) < 32:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be a strong, unique production secret (32+ characters).")
    if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
        raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must list explicit production hosts; wildcard '*' is not allowed.")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "ops.apps.OpsConfig",
    "staff_access.apps.StaffAccessConfig",
    "catalog", "inventory", "serial_tracking", "purchasing", "customers", "sales",
    "payments.apps.PaymentsConfig", "shipping.apps.ShippingConfig", "returns.apps.ReturnsConfig",
    "accounting.apps.AccountingConfig", "expenses.apps.ExpensesConfig", "reports.apps.ReportsConfig",
    "promotions.apps.PromotionsConfig", "store_settings.apps.StoreSettingsConfig",
    "customer_accounts.apps.CustomerAccountsConfig", "integrations.apps.IntegrationsConfig", "storefront", "backoffice",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "ops.middleware.ProductionSecurityHeadersMiddleware",
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
        "customer_accounts.context_processors.customer_account",
        "integrations.context_processors.staff_notifications",
    ]},
}]
WSGI_APPLICATION = "techbari.wsgi.application"
ASGI_APPLICATION = "techbari.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("DB_NAME", "techbari"),
        "USER": os.getenv("DB_USER", "root"),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "3306"),
        "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            "charset": "utf8mb4",
            "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "10")),
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PASSWORD_RESET_TIMEOUT = int(os.getenv("PASSWORD_RESET_TIMEOUT", "3600"))

LOGIN_URL = "backoffice:login"
LOGIN_REDIRECT_URL = "backoffice:dashboard"
STAFF_AUTH_ENABLED = env_bool("STAFF_AUTH_ENABLED", True)
STAFF_IDLE_TIMEOUT = int(os.getenv("STAFF_IDLE_TIMEOUT", "1800"))
AUTH_FAILURE_LIMIT = max(3, int(os.getenv("AUTH_FAILURE_LIMIT", "5")))
AUTH_FAILURE_WINDOW = max(60, int(os.getenv("AUTH_FAILURE_WINDOW", "900")))
AUTH_LOCKOUT_SECONDS = max(60, int(os.getenv("AUTH_LOCKOUT_SECONDS", "900")))

SESSION_COOKIE_AGE = int(os.getenv("SESSION_COOKIE_AGE", "28800"))
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "techbari_sessionid")
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SAMESITE = "Lax"

SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", not DEBUG)
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "3600" if not DEBUG else "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# Only trust forwarded headers when the deployment proxy is explicitly configured
# to overwrite/sanitize them. Do not enable these merely because a proxy exists.
TRUST_X_FORWARDED_FOR = env_bool("TRUST_X_FORWARDED_FOR", False)
if env_bool("TRUST_X_FORWARDED_PROTO", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("DATA_UPLOAD_MAX_MEMORY_SIZE", str(5 * 1024 * 1024)))
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("FILE_UPLOAD_MAX_MEMORY_SIZE", str(2 * 1024 * 1024)))
DATA_UPLOAD_MAX_NUMBER_FIELDS = int(os.getenv("DATA_UPLOAD_MAX_NUMBER_FIELDS", "2000"))
FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755

EMAIL_BACKEND = os.getenv("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@techbari.local")
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "15"))

# Outbound integration and webhook hardening.
INTEGRATION_REQUIRE_HTTPS = env_bool("INTEGRATION_REQUIRE_HTTPS", not DEBUG)
COURIER_WEBHOOK_REQUIRE_TIMESTAMP = env_bool("COURIER_WEBHOOK_REQUIRE_TIMESTAMP", not DEBUG)
COURIER_WEBHOOK_MAX_SKEW_SECONDS = max(30, int(os.getenv("COURIER_WEBHOOK_MAX_SKEW_SECONDS", "300")))
COURIER_WEBHOOK_MAX_BYTES = max(1024, int(os.getenv("COURIER_WEBHOOK_MAX_BYTES", str(64 * 1024))))
COURIER_WEBHOOK_RECEIPT_DAYS = max(1, int(os.getenv("COURIER_WEBHOOK_RECEIPT_DAYS", "7")))

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

LOG_LEVEL = os.getenv("DJANGO_LOG_LEVEL", "INFO").upper()
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": os.getenv("DJANGO_FRAMEWORK_LOG_LEVEL", "WARNING").upper(), "propagate": False},
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "techbari": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "integrations": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}
