"""End-to-end auth regressions against Django's disposable test database."""
from unittest.mock import patch

import jwt
from axes.models import AccessAttempt
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient


class AuthenticationSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("synthetic", password="test-only-password-123", is_staff=True)
        self.client = APIClient()

    def token(self, password="test-only-password-123", **headers):
        return self.client.post("/api/token/", {"username": "synthetic", "password": password}, format="json", **headers)

    def test_valid_login_and_access_without_updating_last_login(self):
        response = self.token()
        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.last_login)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + response.data["access"])
        self.assertEqual(self.client.get("/api/me/").status_code, 200)

    def test_login_locks_account_after_five_failures_including_changed_ip(self):
        for n in range(4):
            self.assertEqual(self.token("incorrect", REMOTE_ADDR=f"192.0.2.{n + 1}").status_code, 401)
        self.assertEqual(self.token("incorrect", REMOTE_ADDR="192.0.2.5").status_code, 429)
        self.assertEqual(self.token(REMOTE_ADDR="192.0.2.6").status_code, 429)
        self.assertTrue(AccessAttempt.objects.exists())

    def test_forged_proxy_headers_do_not_bypass_ip_limit(self):
        for n in range(5):
            response = self.client.post("/api/token/", {"username": f"nonexistent-{n}", "password": "wrong"}, format="json", HTTP_X_FORWARDED_FOR=f"192.0.2.{n}", HTTP_X_REAL_IP=f"192.0.2.{n}")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(self.token(HTTP_X_FORWARDED_FOR="198.51.100.1").status_code, 429)

    def test_admin_login_obeys_same_lockout_as_jwt(self):
        for _ in range(5):
            self.token("wrong")
        for path in ("/login/", "/admin/login/"):
            response = self.client.post(path, {"username": "synthetic", "password": "test-only-password-123"})
            self.assertEqual(response.status_code, 429, path)

    def test_refresh_is_rotated_and_previous_token_is_rejected(self):
        login = self.token().data
        rotated = self.client.post("/api/token/refresh/", {"refresh": login["refresh"]}, format="json")
        self.assertEqual(rotated.status_code, 200)
        self.assertNotEqual(login["refresh"], rotated.data["refresh"])
        reused = self.client.post("/api/token/refresh/", {"refresh": login["refresh"]}, format="json")
        self.assertEqual(reused.status_code, 401)

    def test_token_signed_with_wrong_key_is_rejected(self):
        original = self.token().data["access"]
        payload = jwt.decode(original, options={"verify_signature": False})
        forged = jwt.encode(payload, "synthetic-wrong-key-" + "x" * 60, algorithm="HS256")
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + forged)
        self.assertEqual(self.client.get("/api/me/").status_code, 401)

    def test_inactive_user_cannot_use_previous_access_token(self):
        access = self.token().data["access"]
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + access)
        self.assertEqual(self.client.get("/api/me/").status_code, 401)

    def test_no_referer_redirect_for_missing_or_root_routes(self):
        missing = self.client.get("/does-not-exist/", HTTP_REFERER="https://attacker.invalid/")
        self.assertEqual(missing.status_code, 404)
        self.assertNotIn("Location", missing)
        root = self.client.get("/", HTTP_REFERER="https://attacker.invalid/")
        self.assertEqual(root["Location"], "/login/")

    def test_admin_form_requires_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        response = client.post("/admin/login/", {"username": "synthetic", "password": "test-only-password-123"})
        self.assertEqual(response.status_code, 403)

    @override_settings(SECURE_SSL_REDIRECT=True, SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True)
    def test_https_redirect_and_secure_csrf_cookie(self):
        self.assertEqual(self.client.get("/login/").status_code, 301)
        response = self.client.get("/login/", secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.cookies[settings.CSRF_COOKIE_NAME]["secure"])
