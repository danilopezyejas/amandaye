from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse

from apps.usuarios.models import Personas


class PersonasAdminRenderingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.operator = User.objects.create_user('personas_test', is_staff=True)
        cls.operator.user_permissions.add(*Permission.objects.filter(
            content_type__app_label='usuarios',
            codename__in=('view_personas', 'change_personas'),
        ))
        cls.personas = []
        for number, (state, _) in enumerate(Personas.ESTADO_HABILITACION, start=9901):
            cls.personas.append(Personas.objects.create(
                Cedula=f'TEST-{number}', numeroSocio=number,
                PrimerNombre='Persona', PrimerApellido=f'Sintetica {number}',
                estado_habilitacion=state,
            ))

    def setUp(self):
        self.client.force_login(self.operator)

    def test_list_renders_all_states_without_inline_css_text(self):
        response = self.client.get(reverse('admin:usuarios_personas_changelist'))
        for color, label in (
            ('gray', 'No habilitado'), ('green', 'Habilitado'),
            ('orange', 'Suspendido'), ('red', 'Revocado'),
        ):
            self.assertContains(
                response,
                f'<span style="color: {color}; font-weight: bold;">{label}</span>',
                html=True,
            )
        self.assertContains(response, '/static/admin/css/custom_admin.css')
        self.assertNotContains(response, '.inline-group td.delete')

    def test_detail_keeps_styles_and_admin_navigation(self):
        response = self.client.get(reverse(
            'admin:usuarios_personas_change', args=[self.personas[0].pk],
        ))
        self.assertContains(response, '/static/admin/css/custom_admin.css')
        self.assertContains(response, 'Diagnóstico de habilitación')
        self.assertContains(response, f'href="{reverse("gestion:dashboard")}"')
