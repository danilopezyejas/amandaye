import datetime
import json
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse

from apps.cobranzas.models import Cargo, ConceptoCobro, CuentaCorriente, IntencionSaldo, Pago
from apps.cobranzas.services.cobros import proponer_aplicaciones
from apps.usuarios.models import Personas, Socios


class GestionViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('secretaria', password='test-only', is_staff=True)
        for codename, app_label in (
            ('view_socios', 'usuarios'), ('view_personas', 'usuarios'),
            ('view_cuentacorriente', 'cobranzas'), ('view_pago', 'cobranzas'),
            ('add_pago', 'cobranzas'), ('puede_aplicar_pago', 'cobranzas'),
        ):
            self.user.user_permissions.add(Permission.objects.get(codename=codename, content_type__app_label=app_label))
        self.socio = Socios.objects.create(
            numero=7001, activo=1, tipo_socio='INDIVIDUAL', tipo_cuota='ANUAL',
            cedulaTitular='7001001', fechaAlta=datetime.date.today(),
        )
        Personas.objects.create(
            Cedula='7001001', numeroSocio=7001, PrimerNombre='Ana',
            PrimerApellido='Rivera', Correo='ana@example.test', relacionTitular='Titular',
        )
        self.cuenta = CuentaCorriente.objects.create(
            socio_titular=self.socio, tipo_cuenta=CuentaCorriente.TipoCuenta.INDIVIDUAL,
        )
        concepto = ConceptoCobro.objects.create(codigo='GESTION_TEST', nombre='Cuota sintética')
        Cargo.objects.create(
            cuenta=self.cuenta, concepto=concepto, periodo='2026-09',
            fecha_emision=datetime.date(2026, 9, 1),
            fecha_vencimiento=datetime.date(2026, 9, 10), importe=Decimal('100.00'),
        )
        Pago.objects.create(
            cuenta=self.cuenta, fecha_pago=datetime.date.today(),
            importe_total=Decimal('25.00'), medio_pago=Pago.MedioPago.EFECTIVO,
            registrado_por=self.user,
        )

    def test_search_and_ficha_show_related_data(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('gestion:buscar_socios'), {'q': 'Ana'})
        self.assertContains(response, '7001')
        response = self.client.get(reverse('gestion:ficha_socio', args=[7001]))
        self.assertContains(response, 'Ana Rivera')
        self.assertContains(response, '100,00')
        self.assertContains(response, '25,00')

    def test_dashboard_shows_unapplied_payment(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('gestion:dashboard'))
        self.assertContains(response, 'Pago')
        self.assertContains(response, '25,00')
        self.assertContains(response, 'Deuda vencida')

    def test_dashboard_requires_one_supported_permission(self):
        self.user.user_permissions.clear()
        self.client.force_login(self.user)
        response = self.client.get(reverse('gestion:dashboard'))
        self.assertEqual(response.status_code, 403)

    def test_search_does_not_expose_results_without_permission(self):
        self.user.user_permissions.clear()
        self.client.force_login(self.user)
        response = self.client.get(reverse('gestion:buscar_socios'), {'q': 'Ana'})
        self.assertEqual(response.status_code, 403)

    def test_cobro_screen_reviews_and_confirms_atomic_operation(self):
        self.client.force_login(self.user)
        url = reverse('gestion:nuevo_cobro', args=[7001])
        fields = {
            'fecha_pago': '2026-10-02', 'importe_total': '25.00',
            'medio_pago': Pago.MedioPago.TRANSFERENCIA, 'referencia': 'TRF-UI-1',
            'intencion_saldo': IntencionSaldo.SIN_CLASIFICAR,
        }
        review = self.client.post(url, fields)
        self.assertEqual(review.status_code, 200)
        self.assertContains(review, 'Confirmar cobro y emitir comprobante')

        proposal = proponer_aplicaciones(self.cuenta, Decimal('25.00'), usuario=self.user)
        fields.update({
            'confirmar': '1', 'version': proposal['version'],
            'aplicaciones': json.dumps(proposal['filas']), 'clave': str(uuid4()),
        })
        confirmed = self.client.post(url, fields)
        self.assertEqual(confirmed.status_code, 302)
        pago_id = Pago.objects.latest('pk').pk
        self.assertEqual(confirmed.url, reverse('gestion:comprobante_pago', args=[pago_id]))
        pdf = self.client.get(confirmed.url)
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf['Content-Type'], 'application/pdf')
        self.assertTrue(pdf.content.startswith(b'%PDF'))
