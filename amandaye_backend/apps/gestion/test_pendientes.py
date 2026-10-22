import datetime
from decimal import Decimal

from django.contrib.auth.models import Permission, User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.cobranzas.models import AplicacionPago, Cargo, IntencionSaldoPago, Pago
from apps.gestion import tests as fixtures
from apps.usuarios.models import Personas, Socios


class PendientesTests(TestCase):
    setUp = fixtures.GestionViewsTests.setUp

    def panel(self, **params):
        self.client.force_login(self.user)
        return self.client.get(reverse('gestion:dashboard'), params)

    def only(self, *perms):
        self.user.user_permissions.set([Permission.objects.get(content_type__app_label=p.split('.')[0], codename=p.split('.')[1]) for p in perms])

    def test_all_credit_intentions_include_legacy_unclassified(self):
        original = Pago.objects.get()
        for intent in ('ANTICIPO', 'APLICAR'):
            pago = Pago.objects.create(cuenta=self.cuenta, fecha_pago=timezone.localdate(), importe_total=10, medio_pago='EFECTIVO')
            IntencionSaldoPago.objects.create(pago=pago, intencion=intent)
        response = self.panel()
        self.assertEqual(response.context['pagos_sin_aplicar'].paginator.count, 3)
        for text in ('Anticipo intencional', 'Pendiente de aplicación', 'Sin clasificar'):
            self.assertContains(response, text)
        response = self.panel(intencion='SIN_CLASIFICAR')
        self.assertEqual([p.pk for p in response.context['pagos_sin_aplicar']], [original.pk])
        self.assertEqual(self.panel(intencion='ANTICIPO').context['pagos_sin_aplicar'].paginator.count, 1)

    def test_debt_and_credit_use_active_applications_only(self):
        cargo, pago = Cargo.objects.get(), Pago.objects.get()
        AplicacionPago.objects.create(cargo=cargo, pago=pago, importe_aplicado=10, estado='ACTIVA')
        AplicacionPago.objects.create(cargo=cargo, pago=pago, importe_aplicado=5, estado='REVERTIDA')
        response = self.panel()
        self.assertEqual(response.context['deudas_vencidas'][0].saldo_pendiente_panel, Decimal('90.00'))
        self.assertEqual(response.context['pagos_sin_aplicar'][0].saldo_sin_aplicar, Decimal('15.00'))
        Cargo.objects.filter(pk=cargo.pk).update(estado='ANULADO')
        self.assertEqual(self.panel().context['deudas_vencidas'].paginator.count, 0)

    def test_due_today_is_not_overdue(self):
        Cargo.objects.update(fecha_vencimiento=timezone.localdate())
        self.assertEqual(self.panel().context['deudas_vencidas'].paginator.count, 0)

    def test_pagination_and_counts_preserve_filters_and_other_pages(self):
        Pago.objects.bulk_create([Pago(cuenta=self.cuenta, fecha_pago=timezone.localdate(), importe_total=1, medio_pago='EFECTIVO') for _ in range(30)])
        response = self.panel(socio='7001', saldos_page='2', habilitaciones_page='1', unexpected='discard')
        page = response.context['pagos_sin_aplicar']
        self.assertEqual(page.paginator.count, 31)
        self.assertEqual(len(page), 6)
        self.assertIn('socio=7001', page.anterior_url)
        self.assertIn('habilitaciones_page=1', page.anterior_url)
        self.assertNotIn('unexpected', page.anterior_url)
        self.assertContains(response, 'Pagos con saldo (31)')

    def test_invalid_filters_do_not_silently_show_all_records(self):
        for params in ({'socio': '²'}, {'socio': '9999999999'}, {'intencion': 'invalid'},
                       {'solicitudes_desde': '2026-02-01', 'solicitudes_hasta': '2026-01-01'}):
            response = self.panel(**params)
            self.assertTrue(response.context['filtros'].errors)
            self.assertEqual(response.context['pagos_sin_aplicar'].paginator.count, 0)

    def test_member_and_request_date_filters(self):
        Socios.objects.filter(pk=self.socio.pk).update(activo=2, fechaSolicitud=datetime.date(2026, 10, 1))
        self.assertEqual(self.panel(solicitudes_desde='2026-10-02').context['solicitudes'].paginator.count, 0)
        self.assertEqual(self.panel(solicitudes_hasta='2026-10-01').context['solicitudes'].paginator.count, 1)
        self.assertEqual(self.panel(socio='999').context['pagos_sin_aplicar'].paginator.count, 0)

    def test_person_only_sees_no_financial_queue_or_diagnosis(self):
        self.only('usuarios.view_personas')
        response = self.panel()
        self.assertNotIn('pagos_sin_aplicar', response.context)
        self.assertNotContains(response, 'id="saldos"')
        self.assertNotContains(response, 'Falta aprobación')
        self.assertNotContains(response, reverse('gestion:ficha_socio', args=[7001]))
        self.assertContains(response, 'Ver persona')
        self.assertNotIn('intencion', response.context['filtros'].fields)

    def test_account_only_does_not_get_broken_member_links(self):
        self.only('cobranzas.view_cuentacorriente')
        response = self.panel()
        self.assertNotIn('habilitaciones', response.context)
        self.assertNotIn('solicitudes', response.context)
        self.assertNotContains(response, reverse('gestion:ficha_socio', args=[7001]))
        self.assertNotContains(response, 'Aplicar saldo</a>')

    def test_orphan_person_links_to_person_not_missing_member(self):
        Personas.objects.create(Cedula='ORPHAN', numeroSocio=999, PrimerNombre='Prueba', PrimerApellido='Sin socio')
        response = self.panel(socio='999')
        self.assertContains(response, 'No existe un socio vinculado')
        self.assertNotContains(response, reverse('gestion:ficha_socio', args=[999]))

    def test_diagnosis_is_read_only_and_distinguishes_saved_state(self):
        Personas.objects.filter(numeroSocio=7001).update(estado_habilitacion='HABILITADO')
        before = list(Personas.objects.values('estado_habilitacion', 'fecha_ultimo_calculo_habilitacion'))
        self.client.force_login(self.user)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('gestion:dashboard'), {'habilitacion': 'TODOS'})
        self.assertContains(response, 'La evaluación difiere del estado registrado')
        self.assertContains(response, 'Falta aprobación de profesor')
        self.assertEqual(list(Personas.objects.values('estado_habilitacion', 'fecha_ultimo_calculo_habilitacion')), before)
        self.assertFalse(any(q['sql'].lstrip().upper().startswith(('UPDATE ', 'INSERT ', 'DELETE ')) for q in queries))
        self.assertIn('no-store', response['Cache-Control'])

    def test_queries_do_not_grow_per_person_or_payment(self):
        self.panel()
        with CaptureQueriesContext(connection) as small:
            self.client.get(reverse('gestion:dashboard'))
        Personas.objects.bulk_create([Personas(Cedula=f'SYNTHETIC{i}', numeroSocio=7001, PrimerNombre='Prueba', PrimerApellido=str(i)) for i in range(20)])
        Pago.objects.bulk_create([Pago(cuenta=self.cuenta, fecha_pago=timezone.localdate(), importe_total=1, medio_pago='EFECTIVO') for _ in range(20)])
        with CaptureQueriesContext(connection) as large:
            self.client.get(reverse('gestion:dashboard'))
        self.assertLessEqual(len(large), len(small) + 1)

    def test_admin_and_ficha_use_same_diagnosis_without_exposing_it_to_unprivileged(self):
        self.client.force_login(self.user)
        persona = Personas.objects.get(numeroSocio=7001)
        for url in (reverse('gestion:ficha_socio', args=[7001]), reverse('admin:usuarios_personas_change', args=[persona.pk])):
            self.assertContains(self.client.get(url), 'Falta aprobación de profesor')
        self.only('usuarios.view_personas')
        response = self.client.get(reverse('admin:usuarios_personas_change', args=[persona.pk]))
        self.assertNotContains(response, 'Falta aprobación de profesor')
