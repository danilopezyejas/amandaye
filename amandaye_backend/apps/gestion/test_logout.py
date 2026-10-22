from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse


class LogoutRedirectTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('logout-test', password='synthetic-only', is_staff=True)
        self.client.force_login(self.user)

    @override_settings(LOGOUT_REDIRECT_URL='http://localhost:5173/')
    def test_logout_from_backend_returns_to_frontend_and_clears_session(self):
        response = self.client.post(reverse('admin:logout'))
        self.assertRedirects(response, 'http://localhost:5173/', fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)

    @override_settings(LOGOUT_REDIRECT_URL='/')
    def test_production_returns_to_public_root(self):
        response = self.client.post(reverse('admin:logout'))
        self.assertRedirects(response, '/', fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_logout_requires_post_and_csrf(self):
        self.assertEqual(self.client.get(reverse('admin:logout')).status_code, 405)
        self.assertIn('_auth_user_id', self.client.session)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(reverse('admin:logout')).status_code, 403)
        self.assertIn('_auth_user_id', client.session)
