import datetime
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db import DatabaseError, connection, connections
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.cobranzas.models import AplicacionPago, Cargo, ConceptoCobro, CuentaCorriente, Pago
from apps.cobranzas.services.cuentas import obtener_estado_cuenta
from apps.usuarios.models import EventoSocio, Personas, Socios, Socios_cambios
from apps.usuarios.services.socios import (
    aprobar_socio, cambiar_tipo_cuota, crear_solicitud_socio, dar_baja_socio,
    reactivar_socio, rechazar_socio,
)


class FichaCompletaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('operador_ficha', is_staff=True)
        self.set_permissions('usuarios.view_socios', 'usuarios.view_personas', 'cobranzas.view_cuentacorriente')
        self.socio = Socios.objects.create(numero=8101, cedulaTitular='8101001', activo=1)
        self.otro = Socios.objects.create(numero=8102, cedulaTitular='8102001', activo=1)
        self.titular = Personas.objects.create(Cedula='8101001', numeroSocio=8101,
            PrimerNombre='Ana', PrimerApellido='Lago', relacionTitular='TITULAR',
            salud='SALUD_RESERVADA', llave=918273, Correo='ana@example.test')
        self.familiar = Personas.objects.create(Cedula='8101002', numeroSocio=8101,
            PrimerNombre='Lucía', SegundoNombre='María', PrimerApellido='Lago', relacionTitular='HIJO')
        self.cuenta = CuentaCorriente.objects.create(socio_titular=self.socio, tipo_cuenta='FAMILIAR')
        self.concepto = ConceptoCobro.objects.create(codigo='FICHA', nombre='Cuota de prueba')
        self.url = reverse('gestion:ficha_socio', args=[8101])
        self.search = reverse('gestion:buscar_socios')

    def set_permissions(self, *names):
        self.user.user_permissions.set([Permission.objects.get(
            content_type__app_label=name.split('.')[0], codename=name.split('.')[1]) for name in names])
        self.client.force_login(self.user)

    def cargo(self, **kwargs):
        defaults = dict(cuenta=self.cuenta, concepto=self.concepto, periodo='2026-01',
                        fecha_emision=timezone.localdate(), fecha_vencimiento=timezone.localdate()-datetime.timedelta(days=2),
                        importe=Decimal('100.00'), registrado_por=self.user)
        return Cargo.objects.create(**(defaults | kwargs))

    def pago(self, **kwargs):
        return Pago.objects.create(**(dict(cuenta=self.cuenta, fecha_pago=timezone.localdate(),
            importe_total=Decimal('50.00'), medio_pago='EFECTIVO', registrado_por=self.user) | kwargs))

    def test_search_finds_member_by_relative_and_full_name_without_duplicates(self):
        for query in ('8101', '8101002', 'Lucía María Lago', 'Lago'):
            with self.subTest(query=query):
                response = self.client.get(self.search, {'q': query})
                self.assertEqual([s.pk for s in response.context['page']], [8101])
                self.assertContains(response, 'Ana Lago')
        Personas.objects.create(Cedula='8102002', numeroSocio=8102, PrimerNombre='Lucía', PrimerApellido='Lago')
        response = self.client.get(self.search, {'q': 'Lucía Lago'})
        self.assertEqual([s.pk for s in response.context['page']], [8101, 8102])

    def test_orphans_and_extreme_numeric_input_do_not_match_wrong_member(self):
        Personas.objects.create(Cedula='ORPHAN', numeroSocio=9999, PrimerNombre='Huérfana', PrimerApellido='Prueba')
        for query in ('Huérfana', '9'*100, '²', '１２'):
            with self.subTest(query=query):
                response = self.client.get(self.search, {'q': query})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['page'].paginator.count, 0)
                if not query.isascii() and query.isdigit():
                    self.assertContains(response, 'Usá dígitos del 0 al 9')

    def test_search_does_not_use_private_person_data_without_permission(self):
        self.set_permissions('usuarios.view_socios')
        response = self.client.get(self.search, {'q': 'Lucía'})
        self.assertEqual(response.context['page'].paginator.count, 0)
        response = self.client.get(self.search, {'q': '8101'})
        self.assertNotContains(response, 'Ana Lago')

    def test_inconsistent_titular_is_not_assigned_to_another_household(self):
        self.socio.cedulaTitular = '8102001'
        self.socio.save()
        Personas.objects.create(Cedula='8102001', numeroSocio=8102, PrimerNombre='Ajena', PrimerApellido='Privada', Correo='ajena@example.test')
        response = self.client.get(self.url)
        self.assertContains(response, 'titular figura vinculado a otro grupo')
        self.assertNotContains(response, 'ajena@example.test')
        self.assertNotContains(response, 'Ajena Privada')

    def test_ficha_respects_sections_and_hides_sensitive_free_text(self):
        self.cargo()
        LogEntry.objects.create(user=self.user, content_type=ContentType.objects.get_for_model(Socios),
            object_id=str(self.socio.pk), object_repr='PRIVATE_OBJECT_REPR', action_flag=CHANGE,
            change_message='PRIVATE_FREE_TEXT')
        response = self.client.get(self.url)
        for secret in ('SALUD_RESERVADA', '918273', 'PRIVATE_FREE_TEXT', 'PRIVATE_OBJECT_REPR'):
            self.assertNotContains(response, secret)
        self.assertContains(response, 'Datos actualizados')
        self.set_permissions('usuarios.view_socios')
        response = self.client.get(self.url)
        self.assertNotContains(response, 'ana@example.test')
        self.assertNotContains(response, 'Cargo emitido')
        self.assertNotContains(response, 'id="cuenta"')
        self.assertNotContains(response, 'id="familia"')
        self.set_permissions('cobranzas.view_cuentacorriente')
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_missing_member_and_pending_member_are_read_only(self):
        self.assertEqual(self.client.get(reverse('gestion:ficha_socio', args=[9999])).status_code, 404)
        self.otro.activo = 2
        self.otro.save()
        counts = (CuentaCorriente.objects.count(), EventoSocio.objects.count())
        response = self.client.get(reverse('gestion:ficha_socio', args=[self.otro.pk]))
        self.assertContains(response, 'No hay cuenta corriente')
        self.assertEqual(counts, (CuentaCorriente.objects.count(), EventoSocio.objects.count()))
        self.assertIn('no-store', response['Cache-Control'])

    def test_totals_match_services_with_partial_reverted_void_and_future_charges(self):
        partial = self.cargo(estado='PARCIAL', importe=Decimal('100.25'))
        future = self.cargo(fecha_vencimiento=timezone.localdate()+datetime.timedelta(days=20))
        self.cargo(estado='ANULADO', importe=Decimal('900.00'))
        pago = self.pago(importe_total=Decimal('200.00'))
        AplicacionPago.objects.create(pago=pago, cargo=partial, importe_aplicado=Decimal('30.10'))
        AplicacionPago.objects.create(pago=pago, cargo=partial, importe_aplicado=Decimal('5.00'),
            estado='REVERTIDA', fecha_reversion=timezone.now())
        response = self.client.get(self.url)
        actual = response.context['estado']
        expected = obtener_estado_cuenta(self.cuenta)
        self.assertEqual(actual['saldo_total'], expected['saldo_total'])
        self.assertEqual(actual['deuda_vencida'], expected['deuda_vencida'])
        self.assertEqual(actual['saldo_total'], Decimal('170.15'))
        self.assertEqual(actual['saldo_sin_aplicar'], Decimal('169.90'))
        self.assertContains(response, 'Aplicación revertida')
        self.assertContains(response, 'Actor no registrado')

    def test_pagination_is_independent_stable_and_keeps_totals(self):
        cargos = [self.cargo() for _ in range(27)]
        pagos = [self.pago() for _ in range(27)]
        for cargo, pago in zip(cargos, pagos):
            AplicacionPago.objects.create(pago=pago, cargo=cargo, importe_aplicado=Decimal('10.00'))
        response = self.client.get(self.url, {'cargos_page': 2, 'pagos_page': 2, 'aplicaciones_page': 2, 'historial_page': 2})
        self.assertEqual(len(response.context['cargos_page']), 2)
        self.assertEqual(len(response.context['pagos_page']), 2)
        self.assertEqual(len(response.context['aplicaciones_page']), 2)
        self.assertEqual(response.context['cargos_page'][0].pk, cargos[1].pk)
        self.assertEqual(response.context['estado']['saldo_total'], Decimal('2430.00'))
        self.assertEqual(response.context['estado']['saldo_sin_aplicar'], Decimal('1080.00'))
        self.assertEqual(response.context['historial_page'].paginator.count, 81)
        self.assertIn('pagos_page=2', response.context['cargos_page'].anterior_url)
        self.assertTrue(response.context['cargos_page'].anterior_url.endswith('#cargos'))
        response = self.client.get(self.url, {'cargos_page':'invalid', 'pagos_page':'999999'})
        self.assertEqual(response.context['cargos_page'].number, 1)
        self.assertEqual(response.context['pagos_page'].number, 2)

    def test_history_never_guesses_legacy_identity_and_does_not_mix_members(self):
        Socios_cambios.objects.create(id=1, fecha=timezone.localdate(), accion='Alta', comentario='PRIVATE_LEGACY Socio 8101')
        EventoSocio.objects.create(socio=self.otro, accion='RECHAZO', actor=self.user)
        EventoSocio.objects.create(socio=self.socio, accion='APROBACION', actor=self.user, detalle='PRIVATE_REASON')
        response = self.client.get(self.url)
        self.assertContains(response, 'Aprobación de socio')
        self.assertNotContains(response, 'Rechazo de solicitud')
        self.assertNotContains(response, 'PRIVATE_LEGACY')
        self.assertNotContains(response, 'PRIVATE_REASON')
        self.assertEqual(response.context['historial_page'].paginator.count, 1)
        self.assertTrue(Socios_cambios.objects.filter(pk=1).exists())

    def test_query_count_does_not_grow_per_movement(self):
        self.cargo()
        self.pago()
        self.client.get(self.url)  # Warm content-type cache equally.
        with CaptureQueriesContext(connection) as small:
            self.client.get(self.url)
        for _ in range(30):
            self.cargo()
            self.pago()
        with CaptureQueriesContext(connection) as large:
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(large), len(small) + 1)
        self.assertLess(len(large), 35)


class HistorialTransicionesTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_superuser('directiva_audit', 'audit@example.test', 'synthetic')
        self.socio = Socios.objects.create(numero=8201, cedulaTitular='8201001', activo=2)

    def test_transitions_record_member_actor_and_action(self):
        aprobar_socio(self.socio, generar_cargos_iniciales=False, usuario=self.actor)
        cambiar_tipo_cuota(self.socio, 'BECA', 'Acuerdo sintético', usuario=self.actor)
        dar_baja_socio(self.socio, usuario=self.actor)
        reactivar_socio(self.socio, usuario=self.actor)
        self.assertEqual(list(EventoSocio.objects.filter(socio=self.socio).order_by('pk').values_list('accion', flat=True)),
                         ['APROBACION', 'CUOTA', 'BAJA', 'REACTIVACION'])
        self.assertFalse(EventoSocio.objects.exclude(actor=self.actor).exists())
        otro = Socios.objects.create(numero=8202, cedulaTitular='8202001', activo=2)
        rechazar_socio(otro, usuario=self.actor)
        self.assertEqual(otro.eventos.get().accion, 'RECHAZO')

    def test_failed_transition_rolls_back_state_account_and_event(self):
        with patch('apps.usuarios.services.socios.recalcular_habilitados', side_effect=DatabaseError('synthetic')):
            with self.assertRaises(DatabaseError):
                aprobar_socio(self.socio, generar_cargos_iniciales=False, usuario=self.actor)
        self.socio.refresh_from_db()
        self.assertEqual(self.socio.activo, 2)
        self.assertFalse(EventoSocio.objects.exists())
        self.assertFalse(CuentaCorriente.objects.exists())

    def test_public_request_has_explicit_unknown_operator_and_legacy_is_preserved(self):
        Socios_cambios.objects.create(id=999, fecha=timezone.localdate(), accion='Alta', comentario='Conservar')
        socio = crear_solicitud_socio(dict(Cedula='8203001', PrimerNombre='Solicitud', PrimerApellido='Sintética',
            FechaNacimiento='1990-01-01', Celular='099000000', Direccion='Prueba'))
        event = socio.eventos.get()
        self.assertEqual(event.accion, 'SOLICITUD')
        self.assertIsNone(event.actor)
        self.assertEqual(Socios_cambios.objects.get(pk=999).comentario, 'Conservar')


class HistorialConcurrenteTests(TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_two_members_keep_distinct_audit_events(self):
        actor = User.objects.create_superuser('concurrent_audit', 'audit@example.test', 'synthetic')
        members = [Socios.objects.create(numero=n, cedulaTitular=str(n), activo=1) for n in (8301, 8302)]
        barrier = Barrier(2)

        def worker(pk):
            connections.close_all()
            try:
                user = User.objects.get(pk=actor.pk)
                member = Socios.objects.get(pk=pk)
                barrier.wait(timeout=15)
                dar_baja_socio(member, usuario=user)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker, member.pk) for member in members]
            for future in futures:
                future.result(timeout=30)
        self.assertCountEqual(list(EventoSocio.objects.values_list('socio_id', flat=True)), [8301, 8302])
        self.assertEqual(Socios.objects.filter(activo=0).count(), 2)
