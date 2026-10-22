from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import resolve, reverse
from types import SimpleNamespace

from .templatetags.ayuda import ayuda_contextual


class HelpSelectionTests(SimpleTestCase):
    def test_context_uses_resolved_routes_not_untrusted_query(self):
        for url, expected in (
            ('/admin/gestion/', 'Panel de pendientes'),
            ('/admin/gestion/socios/7001/cobro/', 'Registrar un cobro'),
            ('/admin/usuarios/personas/', 'Personas, familia y habilitación'),
            ('/admin/cobranzas/pago/resumen-mensual/', 'Pagos'),
            ('/admin/cobranzas/aplicacionpago/', 'Aplicaciones y reversiones'),
            ('/login/', 'Acceso al sistema'),
        ):
            with self.subTest(url=url):
                request = SimpleNamespace(resolver_match=resolve(url), GET={'help': '<script>'})
                self.assertEqual(ayuda_contextual({'request': request})['help_title'], expected)


class HelpRenderingTests(TestCase):
    def test_guides_render_once_in_admin_and_gestion(self):
        user = User.objects.create_superuser('help-test', password='synthetic-only')
        self.client.force_login(user)
        for name, expected in (
            ('admin:index', 'Administración del club'),
            ('admin:usuarios_socios_changelist', 'Socios y solicitudes'),
            ('admin:cobranzas_cargo_changelist', 'Cargos'),
            ('gestion:dashboard', 'Panel de pendientes'),
        ):
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertContains(response, '<details class="club-help">', count=1)
                self.assertContains(response, 'Ayuda: ' + expected)
                self.assertContains(response, 'ayuda/ayuda.js')
                self.assertContains(response, 'ayuda/ayuda.css')

    def test_login_contains_only_access_guide(self):
        response = self.client.get(reverse('login'))
        self.assertContains(response, 'Ayuda: Acceso al sistema')
        self.assertNotContains(response, 'Anular cargos')
