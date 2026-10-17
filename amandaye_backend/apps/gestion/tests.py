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

    def test_anonymous_visitors_reach_login_from_every_gestion_page(self):
        routes = (
            ('gestion:dashboard', []),
            ('gestion:buscar_socios', []),
            ('gestion:ficha_socio', [self.socio.pk]),
            ('gestion:nuevo_cobro', [self.socio.pk]),
            ('gestion:comprobante_pago', [Pago.objects.get(cuenta=self.cuenta).pk]),
        )
        for name, args in routes:
            with self.subTest(route=name):
                url = reverse(name, args=args)
                response = self.client.get(url)
                self.assertRedirects(response, f'{reverse("login")}?next={url}')

    def test_login_returns_to_gestion_dashboard(self):
        url = reverse('gestion:dashboard')
        login = self.client.get(url, follow=True)
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.context['next'], url)
        response = self.client.post(login.redirect_chain[-1][0], {
            'username': 'secretaria', 'password': 'test-only', 'next': url,
        }, follow=True)
        self.assertRedirects(response, url)
        self.assertContains(response, 'Gestión diaria')
        self.assertContains(response, f'href="{url}"')

    def test_gestion_pages_keep_admin_navigation(self):
        self.client.force_login(self.user)
        for name, args in (
            ('gestion:dashboard', []),
            ('gestion:buscar_socios', []),
            ('gestion:ficha_socio', [self.socio.pk]),
            ('gestion:nuevo_cobro', [self.socio.pk]),
        ):
            with self.subTest(route=name):
                response = self.client.get(reverse(name, args=args))
                self.assertContains(response, f'href="{reverse("gestion:dashboard")}"')
                self.assertContains(response, 'id="logout-form"')

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


class GestionAdminEntryTests(TestCase):
    def setUp(self):
        self.operator = User.objects.create_user('gestion_entry_test', is_staff=True)

    def test_admin_home_offers_working_entry_for_each_supported_permission(self):
        for app_label, codename in (
            ('usuarios', 'view_socios'),
            ('usuarios', 'view_personas'),
            ('cobranzas', 'view_cuentacorriente'),
        ):
            with self.subTest(permission=codename):
                self.operator.user_permissions.set([Permission.objects.get(
                    content_type__app_label=app_label, codename=codename,
                )])
                self.client.force_login(self.operator)
                response = self.client.get(reverse('admin:index'))
                self.assertContains(response, 'id="gestion-entry"', count=1)
                self.assertContains(
                    response,
                    f'<a class="button" href="{reverse("gestion:dashboard")}">Abrir Gestión diaria</a>',
                    html=True,
                )
                self.assertContains(self.client.get(reverse('gestion:dashboard')), 'Gestión diaria')

    def test_admin_home_hides_entry_without_supported_permissions(self):
        self.client.force_login(self.operator)
        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="gestion-entry"')
        self.assertNotContains(response, f'href="{reverse("gestion:dashboard")}"')
        self.assertEqual(self.client.get(reverse('gestion:dashboard')).status_code, 403)

    def test_superuser_sees_entry_before_model_list(self):
        self.operator.is_superuser = True
        self.operator.save(update_fields=['is_superuser'])
        self.client.force_login(self.operator)
        response = self.client.get(reverse('admin:index'))
        self.assertContains(response, 'id="gestion-entry"')
        html = response.content.decode()
        self.assertLess(html.index('id="gestion-entry"'), html.index('class="app-'))
