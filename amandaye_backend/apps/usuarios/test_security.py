import datetime
from unittest.mock import patch, Mock

from django.contrib import admin
from django.contrib.auth.models import Permission, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.cobranzas.models import Cargo, ConceptoCobro, CuentaCorriente
from apps.cobranzas.services.cuotas import generar_cuotas_mensuales
from apps.usuarios.admin import SociosAdmin
from apps.usuarios.models import Personas, Socios, Socios_cambios
from apps.usuarios.services.habilitacion import _calcular_estado_individual
from apps.usuarios.services.socios import aprobar_socio, dar_baja_socio, rechazar_socio, reactivar_socio, cambiar_tipo_cuota


class MembershipSecurityTests(TestCase):
    def setUp(self):
        self.secretary = User.objects.create_user('secretary', is_staff=True)
        self.secretary.user_permissions.add(*Permission.objects.filter(
            content_type__app_label='usuarios', codename__in=('view_socios', 'add_socios', 'change_socios'),
        ))
        self.board = User.objects.create_user('board', is_staff=True)
        self.board.user_permissions.add(*Permission.objects.filter(
            content_type__app_label='usuarios', codename__in=(
                'view_socios', 'puede_aprobar_socio', 'puede_rechazar_socio', 'puede_dar_baja_socio',
            ),
        ))
        self.socio = Socios.objects.create(numero=8801, cedulaTitular='8801001', activo=2)
        self.model_admin = SociosAdmin(Socios, admin.site)
        for code in ('MATRICULA', 'CUOTA_INDIVIDUAL', 'CUOTA_FAMILIAR', 'CUOTA_TEMPORADA'):
            ConceptoCobro.objects.create(codigo=code, nombre=code, importe_por_defecto=100)

    def request(self, user):
        request = RequestFactory().post('/')
        request.user = user
        return request

    def test_secretary_has_no_transition_actions_or_service_access(self):
        actions = self.model_admin.get_actions(self.request(self.secretary))
        self.assertNotIn('aprobar_socios_seleccionados', actions)
        self.assertNotIn('rechazar_socios_seleccionados', actions)
        self.assertNotIn('dar_baja_socios_seleccionados', actions)
        self.assertNotIn('cambiar_cuota_socios_seleccionados', actions)
        for service in (aprobar_socio, rechazar_socio, dar_baja_socio, reactivar_socio):
            with self.subTest(service=service), self.assertRaises(PermissionDenied):
                service(self.socio, usuario=self.secretary)
        self.socio.refresh_from_db()
        self.assertEqual(self.socio.activo, 2)
        self.assertFalse(CuentaCorriente.objects.exists())

    def test_direct_action_call_cannot_bypass_permission(self):
        with self.assertRaises(PermissionDenied):
            self.model_admin.aprobar_socios_seleccionados(self.request(self.secretary), Socios.objects.all())

    def test_secretary_cannot_submit_state_or_identity_changes(self):
        self.client.force_login(self.secretary, backend='django.contrib.auth.backends.ModelBackend')
        response = self.client.post(reverse('admin:usuarios_socios_change', args=[self.socio.pk]), {
            'numero': 7777, 'cedulaTitular': self.socio.cedulaTitular, 'activo': 1,
            'tipo_socio': 'INDIVIDUAL', 'tipo_cuota': 'EXONERADO', 'comentarios': 'Safe edit', '_save': 'Save',
        })
        self.assertEqual(response.status_code, 302)
        self.socio.refresh_from_db()
        self.assertEqual(self.socio.activo, 2)
        self.assertEqual(self.socio.tipo_cuota, 'ANUAL')
        self.assertEqual(self.socio.comentarios, 'Safe edit')
        self.assertFalse(Socios.objects.filter(pk=7777).exists())
        self.assertFalse(CuentaCorriente.objects.exists())

    def test_admin_new_member_is_pending_even_with_forged_active_state(self):
        self.client.force_login(self.secretary, backend='django.contrib.auth.backends.ModelBackend')
        response = self.client.post(reverse('admin:usuarios_socios_add'), {
            'numero': 8802, 'cedulaTitular': '8802002', 'activo': 1,
            'tipo_socio': 'INDIVIDUAL', 'tipo_cuota': 'EXONERADO', '_save': 'Save',
        })
        self.assertEqual(response.status_code, 302)
        created = Socios.objects.get(pk=8802)
        self.assertEqual(created.activo, 2)
        self.assertEqual(created.tipo_cuota, 'ANUAL')
        self.assertIsNone(created.fechaAlta)
        self.assertIsNone(created.fechaAprobacion)
        self.assertIsNotNone(created.fechaSolicitud)

    def test_board_can_approve_without_generic_change_permission(self):
        self.assertFalse(self.board.has_perm('usuarios.change_socios'))
        self.client.force_login(self.board, backend='django.contrib.auth.backends.ModelBackend')
        response = self.client.post(reverse('admin:usuarios_socios_changelist'), {
            'action': 'aprobar_socios_seleccionados', '_selected_action': self.socio.pk,
        })
        self.assertEqual(response.status_code, 302)
        self.socio.refresh_from_db()
        self.assertEqual(self.socio.activo, 1)
        self.assertEqual(Cargo.objects.filter(cuenta__socio_titular=self.socio).count(), 2)
        self.assertTrue(Socios_cambios.objects.filter(comentario__contains=f'[actor:{self.board.pk}]').exists())

    def test_closure_failure_rolls_back_member_account_and_audit(self):
        socio = aprobar_socio(self.socio, usuario=self.board)
        original_logs = Socios_cambios.objects.count()
        with patch.object(CuentaCorriente, 'save', side_effect=DatabaseError('synthetic failure')):
            with self.assertRaises(DatabaseError):
                dar_baja_socio(socio, usuario=self.board)
        socio.refresh_from_db()
        self.assertEqual(socio.activo, 1)
        self.assertIsNone(socio.fechaBaja)
        self.assertEqual(socio.cuenta_corriente.estado, 'ACTIVA')
        self.assertEqual(Socios_cambios.objects.count(), original_logs)

    def test_debt_failure_is_never_treated_as_eligible(self):
        persona = Personas(Cedula='synthetic', numeroSocio=self.socio.pk, estado_habilitacion='NO_HABILITADO')
        socio = Mock()
        socio.cuenta_corriente.cargos.all.side_effect = DatabaseError('synthetic failure')
        with self.assertRaises(DatabaseError):
            _calcular_estado_individual(persona, socio, datetime.date.today())

    def test_generation_ignores_inactive_member_with_legacy_active_account(self):
        self.socio.activo = 0
        self.socio.save(update_fields=['activo'])
        CuentaCorriente.objects.create(socio_titular=self.socio, tipo_cuenta='INDIVIDUAL', estado='ACTIVA')
        outcome = generar_cuotas_mensuales('2027-03')
        self.assertEqual(outcome['cuotas_creadas'], 0)
        self.assertFalse(Cargo.objects.exists())

    def test_generation_failure_rolls_back_account_batch_and_hides_exception(self):
        aprobar_socio(self.socio, generar_cargos_iniciales=False, usuario=self.board)
        with patch('apps.cobranzas.services.cuotas.crear_cargo', side_effect=DatabaseError('private database detail')):
            outcome = generar_cuotas_mensuales('2027-03')
        self.assertEqual(outcome['cuotas_creadas'], 0)
        self.assertTrue(outcome['errores'])
        self.assertNotIn('private database detail', str(outcome))
        self.assertFalse(Cargo.objects.exists())

    def test_fee_change_requires_board_and_reason(self):
        with self.assertRaises(PermissionDenied):
            cambiar_tipo_cuota(self.socio, 'EXONERADO', 'Synthetic reason', usuario=self.secretary)
        with self.assertRaises(PermissionDenied):
            self.model_admin.cambiar_cuota_socios_seleccionados(self.request(self.secretary), Socios.objects.all())
        with self.assertRaises(ValidationError):
            cambiar_tipo_cuota(self.socio, 'BECA', '', usuario=self.board)
        with self.assertRaises(ValidationError):
            cambiar_tipo_cuota(self.socio, 'INVALID', 'Synthetic reason', usuario=self.board)
        self.socio.refresh_from_db()
        self.assertEqual(self.socio.tipo_cuota, 'ANUAL')

    def test_board_fee_action_updates_future_charges_and_audit(self):
        socio = aprobar_socio(self.socio, usuario=self.board)
        self.client.force_login(self.board, backend='django.contrib.auth.backends.ModelBackend')
        action = {'action': 'cambiar_cuota_socios_seleccionados', '_selected_action': socio.pk}
        response = self.client.post(reverse('admin:usuarios_socios_changelist'), action)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Motivo')
        response = self.client.post(reverse('admin:usuarios_socios_changelist'), {
            **action, 'confirmar_cuota': '1', 'tipo_cuota': 'BECA', 'motivo': 'Synthetic board decision',
        })
        self.assertEqual(response.status_code, 302)
        socio.refresh_from_db()
        self.assertEqual(socio.tipo_cuota, 'BECA')
        self.assertTrue(Socios_cambios.objects.filter(comentario__contains='ANUAL → BECA').exists())
        generar_cuotas_mensuales('2027-06')
        charge = Cargo.objects.get(cuenta__socio_titular=socio, periodo='2027-06')
        self.assertEqual(charge.importe, 50)
        self.assertEqual(Cargo.objects.exclude(pk=charge.pk).count(), 2)
