"""Synthetic credentials and a disposable DB; never load project .env."""
import os

os.environ.update({
    "AMANDAYE_SKIP_DOTENV": "1", "DJANGO_ENV": "test",
    "SECRET_KEY": "test-only-django-" + "a" * 60, "JWT_SIGNING_KEY": "test-only-jwt-" + "b" * 60,
    "DB_USER": "synthetic_test_user", "DB_PASSWORD": "synthetic-test-password",
    "DJANGO_ALLOWED_HOSTS": "testserver,localhost,127.0.0.1", "TRUST_PROXY_HEADERS": "0",
})
for name in ("SECRET_KEY_FILE", "JWT_SIGNING_KEY_FILE", "DB_PASSWORD_FILE", "DB_SSL_CA", "REDIS_URL", "REDIS_URL_FILE"):
    os.environ.pop(name, None)
from .settings import *  # noqa: E402,F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "test-only"}}
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
