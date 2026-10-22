from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.cobranzas.models import Cargo, ComprobantePago, IntencionSaldo, OperacionCobro, Pago
from apps.gestion import tests as fixtures


class CobroCompletoViewsTests(TestCase):
    setUp = fixtures.GestionViewsTests.setUp

    def prepare(self, existing=False):
        self.client.force_login(self.user)
        payment = Pago.objects.get(cuenta=self.cuenta)
        url = reverse('gestion:aplicar_saldo_pago', args=[payment.pk]) if existing else reverse('gestion:nuevo_cobro', args=[self.socio.pk])
        fields = {'intencion_saldo': IntencionSaldo.APLICAR}
        if not existing:
            fields.update(fecha_pago='2026-10-17', importe_total='25.00', medio_pago=Pago.MedioPago.EFECTIVO, referencia='SYNTHETIC')
        proposal = self.client.post(url, fields)
        self.assertEqual(proposal.status_code, 200)
        self.assertEqual(Pago.objects.count(), 1)
        fields.update(clave=proposal.context['clave'], version=proposal.context['propuesta']['version'], revisar='1')
        fields.update({f"cargo_{row['cargo_id']}": row['importe'] for row in proposal.context['propuesta']['filas']})
        return url, fields

    def confirm(self, url, fields):
        preview = self.client.post(url, fields)
        self.assertTrue(preview.context['revision'], preview.content.decode())
        return {'confirmar': '1', 'revision': preview.context['revision']}

    def test_edit_partial_distribution_and_confirm_twice(self):
        url, fields = self.prepare()
        fields[f'cargo_{Cargo.objects.get(cuenta=self.cuenta).pk}'] = '10,50'
        post = self.confirm(url, fields)
        self.assertEqual(Pago.objects.count(), 1)
        first = self.client.post(url, post)
        second = self.client.post(url, post)
        self.assertEqual(first.status_code, 302)
        self.assertEqual(first.url, second.url)
        self.assertEqual(Pago.objects.count(), 2)
        self.assertEqual(Pago.objects.latest('pk').saldo_disponible, Decimal('14.50'))
        self.assertEqual(OperacionCobro.objects.count(), 1)
        receipt = self.client.get(first.url)
        self.assertTrue(receipt.content.startswith(b'%PDF'))

    def test_existing_balance_without_add_payment_permission(self):
        self.user.user_permissions.remove(Permission.objects.get(codename='add_pago', content_type__app_label='cobranzas'))
        url, fields = self.prepare(existing=True)
        post = self.confirm(url, fields)
        self.assertEqual(self.client.post(url, post).status_code, 302)
        self.assertEqual(self.client.post(url, post).status_code, 302)
        self.assertEqual(Pago.objects.count(), 1)
        self.assertEqual(OperacionCobro.objects.count(), 1)
        self.assertEqual(Pago.objects.get().saldo_disponible, Decimal('0.00'))
        self.assertTrue(ComprobantePago.objects.get().reconstruido)
        self.assertContains(self.client.get(url), 'no tiene saldo disponible')

    def test_invalid_review_and_signature_write_nothing(self):
        url, fields = self.prepare()
        name = f'cargo_{Cargo.objects.get(cuenta=self.cuenta).pk}'
        for value in ('26', '-1', 'NaN', '0.001', ''):
            with self.subTest(value=value):
                response = self.client.post(url, {**fields, name: value})
                self.assertIsNone(response.context['revision'])
        valid = self.confirm(url, fields)
        invalid = self.client.post(url, {**valid, 'revision': valid['revision'] + 'bad'})
        self.assertContains(invalid, 'confirmación venció o no es válida')
        self.assertEqual(Pago.objects.count(), 1)
        self.assertFalse(OperacionCobro.objects.exists())

    def test_confirmation_ignores_unreviewed_hidden_field_edits(self):
        url, fields = self.prepare()
        post = self.confirm(url, fields)
        response = self.client.post(url, {**post, 'importe_total': '999', 'aplicaciones': '[]'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Pago.objects.latest('pk').importe_total, Decimal('25.00'))
        self.assertEqual(Pago.objects.latest('pk').total_aplicado, Decimal('25.00'))

    def test_stale_charge_blocks_confirmation(self):
        url, fields = self.prepare()
        post = self.confirm(url, fields)
        Cargo.objects.filter(cuenta=self.cuenta).update(importe=Decimal('120.00'))
        self.assertContains(self.client.post(url, post), 'La propuesta cambió')
        self.assertEqual(Pago.objects.count(), 1)

    def test_expired_and_other_actor_review_rejected(self):
        url, fields = self.prepare()
        with patch('django.core.signing.time.time', return_value=1):
            old = self.confirm(url, fields)
        self.assertContains(self.client.post(url, old), 'confirmación venció')
        post = self.confirm(url, fields)
        other = User.objects.create_superuser('other_cashier', password='synthetic')
        self.client.force_login(other)
        self.assertContains(self.client.post(url, post), 'confirmación venció')
        self.assertEqual(Pago.objects.count(), 1)

    def test_apply_links_permissions_get_and_csrf(self):
        url, fields = self.prepare(existing=True)
        for page in (reverse('gestion:dashboard'), reverse('gestion:ficha_socio', args=[self.socio.pk])):
            self.assertContains(self.client.get(page), f'href="{url}"')
        self.assertIn('no-store', self.client.get(url)['Cache-Control'])
        self.assertFalse(OperacionCobro.objects.exists())
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(csrf.post(url, fields).status_code, 403)
        self.user.user_permissions.remove(Permission.objects.get(codename='view_pago', content_type__app_label='cobranzas'))
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertNotContains(self.client.get(reverse('gestion:ficha_socio', args=[self.socio.pk])), f'href="{url}"')

    def test_back_to_edit_keeps_selected_amounts(self):
        url, fields = self.prepare()
        name = f'cargo_{Cargo.objects.get(cuenta=self.cuenta).pk}'
        fields[name] = '12.00'
        self.confirm(url, fields)
        fields.pop('revisar')
        response = self.client.post(url, {**fields, 'editar': '1'})
        self.assertIsNone(response.context['revision'])
        self.assertEqual(response.context['distribucion'][name].value(), '12.00')

    def test_initial_date_is_valid_for_browser_date_input(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('gestion:nuevo_cobro', args=[self.socio.pk]))
        self.assertContains(response, f'value="{timezone.localdate().isoformat()}"')
