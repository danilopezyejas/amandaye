"""Exercise production fail-closed startup without opening a database or reading .env."""
import os
from pathlib import Path
import subprocess
import sys

from django.test import SimpleTestCase


class ProductionConfigurationTests(SimpleTestCase):
    def load_settings(self, overrides=None, code=""):
        # Keep the interpreter's OS configuration only; never inherit real app secrets.
        env = {key: value for key, value in os.environ.items()
               if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PYTHONHOME"}}
        env.update({
            "AMANDAYE_SKIP_DOTENV": "1", "DJANGO_ENV": "production",
            "SECRET_KEY": "synthetic-django-" + "d" * 60,
            "JWT_SIGNING_KEY": "synthetic-jwt-" + "j" * 60,
            "DJANGO_ALLOWED_HOSTS": "club.example.test", "DB_USER": "synthetic_runner",
            "DB_PASSWORD": "synthetic-password", "DB_PRIVATE_NETWORK": "1",
            "REDIS_URL": "redis://127.0.0.1:6379/15",
        })
        for key, value in (overrides or {}).items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        return subprocess.run(
            [sys.executable, "-c", "from amandaye_backend import settings as s; " + (code or "assert s.PRODUCTION")],
            cwd=Path(__file__).resolve().parents[2], env=env,
            text=True, capture_output=True, timeout=20,
        )

    def test_production_enforces_secure_defaults_even_if_debug_requested(self):
        result = self.load_settings({"DJANGO_DEBUG": "1"},
            "assert not s.DEBUG; assert s.SECURE_SSL_REDIRECT; "
            "assert s.SESSION_COOKIE_SECURE and s.CSRF_COOKIE_SECURE; "
            "assert s.SECRET_KEY != s.SIMPLE_JWT['SIGNING_KEY']; "
            "assert s.REST_FRAMEWORK['NUM_PROXIES'] == 0; "
            "assert not hasattr(s, 'SECURE_PROXY_SSL_HEADER')")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_or_shared_signing_keys_are_rejected(self):
        for override in ({"SECRET_KEY": None}, {"JWT_SIGNING_KEY": None}, {"SECRET_KEY": "short"},
                         {"JWT_SIGNING_KEY": "synthetic-django-" + "d" * 60}):
            with self.subTest(override=list(override)):
                self.assertNotEqual(self.load_settings(override).returncode, 0)

    def test_unsafe_database_and_missing_shared_cache_are_rejected(self):
        for override in ({"DB_USER": "root"}, {"DB_PASSWORD": None},
                         {"DB_PRIVATE_NETWORK": None}, {"REDIS_URL": None}):
            with self.subTest(override=list(override)):
                self.assertNotEqual(self.load_settings(override).returncode, 0)

    def test_missing_hosts_wildcard_and_insecure_origins_are_rejected(self):
        for override in ({"DJANGO_ALLOWED_HOSTS": None}, {"DJANGO_ALLOWED_HOSTS": "*"},
                         {"CORS_ALLOWED_ORIGINS": "http://club.example.test"},
                         {"CSRF_TRUSTED_ORIGINS": "http://club.example.test"}):
            with self.subTest(override=list(override)):
                self.assertNotEqual(self.load_settings(override).returncode, 0)

    def test_forwarded_headers_require_explicit_trust(self):
        result = self.load_settings({"TRUST_PROXY_HEADERS": "1"},
            "assert s.REST_FRAMEWORK['NUM_PROXIES'] == 1; "
            "assert s.SECURE_PROXY_SSL_HEADER == ('HTTP_X_FORWARDED_PROTO', 'https')")
        self.assertEqual(result.returncode, 0, result.stderr)
