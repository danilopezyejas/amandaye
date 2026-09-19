"""Secure defaults; DJANGO_ENV=development explicitly enables local development."""
import os
from datetime import timedelta
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
if os.environ.get("AMANDAYE_SKIP_DOTENV") != "1":
    load_dotenv(BASE_DIR / ".env", override=False)


def env_secret(name):
    filename = os.environ.get(f"{name}_FILE")
    value = Path(filename).read_text(encoding="utf-8").strip() if filename else os.environ.get(name, "")
    if not value:
        raise ImproperlyConfigured(f"Configure {name} or {name}_FILE.")
    return value


def signing_secret(name):
    value = env_secret(name)
    if len(value) < 50 or value.startswith("django-insecure-"):
        raise ImproperlyConfigured(f"{name} must be random and at least 50 characters long.")
    return value


def env_list(name, default=""):
    return [part.strip() for part in os.environ.get(name, default).split(",") if part.strip()]


ENVIRONMENT = os.environ.get("DJANGO_ENV", "production")
if ENVIRONMENT not in {"production", "development", "test"}:
    raise ImproperlyConfigured("DJANGO_ENV must be production, development or test.")
PRODUCTION = ENVIRONMENT == "production"
SECRET_KEY = signing_secret("SECRET_KEY")
JWT_SIGNING_KEY = signing_secret("JWT_SIGNING_KEY")
if SECRET_KEY == JWT_SIGNING_KEY:
    raise ImproperlyConfigured("Django and JWT must use independent signing keys.")
DEBUG = ENVIRONMENT == "development" and os.environ.get("DJANGO_DEBUG") == "1"
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1" if not PRODUCTION else "")
if not ALLOWED_HOSTS or any(host == "*" or "/" in host for host in ALLOWED_HOSTS):
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must contain explicit hostnames.")

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "rest_framework", "rest_framework_simplejwt", "rest_framework_simplejwt.token_blacklist",
    "corsheaders", "axes", "amandaye_backend.security.apps.SecurityConfig",
    "apps.alertas", "apps.brevet", "apps.horarios", "apps.usuarios", "apps.cobranzas",
    "apps.conditions.apps.ConditionsConfig",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware", "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware", "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware", "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware", "axes.middleware.AxesMiddleware",
]
ROOT_URLCONF = "amandaye_backend.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True, "OPTIONS": {"context_processors": [
        "django.template.context_processors.debug", "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "amandaye_backend.wsgi.application"
DB_USER = os.environ.get("DB_USER", "amandaye_app")
if DB_USER.lower() == "root":
    raise ImproperlyConfigured("Use a dedicated application database user, not root.")
DB_OPTIONS = {"init_command": "SET sql_mode='STRICT_TRANS_TABLES'", "charset": "utf8mb4"}
if os.environ.get("DB_SSL_CA"):
    DB_OPTIONS.update({"ssl": {"ca": os.environ["DB_SSL_CA"]}, "ssl_mode": "VERIFY_IDENTITY"})
elif PRODUCTION and os.environ.get("DB_PRIVATE_NETWORK") != "1":
    raise ImproperlyConfigured("Configure DB_SSL_CA or explicitly isolate MySQL on a private network.")
DATABASES = {"default": {
    "ENGINE": "django.db.backends.mysql", "NAME": os.environ.get("DB_NAME", "amandaye"),
    "USER": DB_USER, "PASSWORD": env_secret("DB_PASSWORD"),
    "HOST": os.environ.get("DB_HOST", "127.0.0.1"), "PORT": os.environ.get("DB_PORT", "3306"),
    "OPTIONS": DB_OPTIONS, "CONN_MAX_AGE": 60,
}}
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
AUTHENTICATION_BACKENDS = ["axes.backends.AxesStandaloneBackend", "django.contrib.auth.backends.ModelBackend"]
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_LOCKOUT_PARAMETERS = ["username", "ip_address"]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_CALLABLE = "amandaye_backend.security.authentication.lockout_response"
AXES_CLIENT_IP_CALLABLE = "amandaye_backend.security.authentication.client_ip"
AXES_SENSITIVE_PARAMETERS = ["username", "ip_address", "user_agent", "path_info"]
LANGUAGE_CODE = "es-uy"
TIME_ZONE = "America/Montevideo"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
if PRODUCTION and any(not origin.startswith("https://") for origin in CORS_ALLOWED_ORIGINS + CSRF_TRUSTED_ORIGINS):
    raise ImproperlyConfigured("Production origins must use HTTPS.")
LOGOUT_REDIRECT_URL = "/"
LOGIN_REDIRECT_URL = "/admin/"
SECURE_SSL_REDIRECT = PRODUCTION
SESSION_COOKIE_SECURE = PRODUCTION
CSRF_COOKIE_SECURE = PRODUCTION
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_HSTS_SECONDS = 31536000 if PRODUCTION else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
# Enable only behind a gateway that replaces forwarded headers; backend port stays private.
TRUST_PROXY_HEADERS = os.environ.get("TRUST_PROXY_HEADERS") == "1"
if TRUST_PROXY_HEADERS:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 500
REDIS_URL = env_secret("REDIS_URL") if os.environ.get("REDIS_URL") or os.environ.get("REDIS_URL_FILE") else None
if PRODUCTION and not REDIS_URL:
    raise ImproperlyConfigured("Production requires shared REDIS_URL for rate limiting.")
CACHES = {"default": {
    "BACKEND": "django.core.cache.backends.redis.RedisCache" if REDIS_URL else "django.core.cache.backends.locmem.LocMemCache",
    "LOCATION": REDIS_URL or "amandaye-development",
}}
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": ("apps.usuarios.permissions.ClubPermissions",),
    "DEFAULT_THROTTLE_CLASSES": ("rest_framework.throttling.ScopedRateThrottle",),
    "DEFAULT_THROTTLE_RATES": {"solicitudes": "5/hour", "login": "10/minute", "refresh": "30/minute", "conditions": "60/minute"},
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination", "PAGE_SIZE": 50,
    "NUM_PROXIES": 1 if TRUST_PROXY_HEADERS else 0,
    "EXCEPTION_HANDLER": "amandaye_backend.security.exceptions.exception_handler",
}
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=10), "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True, "BLACKLIST_AFTER_ROTATION": True, "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256", "SIGNING_KEY": JWT_SIGNING_KEY, "AUTH_HEADER_TYPES": ("Bearer",),
    "TOKEN_OBTAIN_SERIALIZER": "amandaye_backend.security.authentication.LoginSerializer",
}
LOGGING = {
    "version": 1, "disable_existing_loggers": False,
    "formatters": {"security": {"format": "{asctime} {levelname} {name} {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "security"}},
    "loggers": {
        "amandaye.security": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "amandaye.conditions": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "axes": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}

from apps.conditions.config import environment_settings

CONDITIONS = environment_settings()
