import datetime
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connections
from django.db.models.deletion import ProtectedError
from django.test import RequestFactory, TestCase, TransactionTestCase, skipUnlessDBFeature

from apps.cobranzas.admin import AplicacionPagoAdmin, CargoAdmin, CuentaCorrienteAdmin, PagoAdmin
from apps.cobranzas.models import AplicacionPago, Cargo, ConceptoCobro, CuentaCorriente, Pago
from apps.cobranzas.services.cargos import anular_cargo, crear_cargo
from apps.cobranzas.services.pagos import aplicar_pago, registrar_pago, revertir_aplicacion
from apps.usuarios.models import Socios


class FinancialFixtures:
    def setUp(self):
        super().setUp()
        self.actor = User.objects.create_superuser(username='financial_actor', password='test-only')
        self.socio = Socios.objects.create(numero=9901, cedulaTitular='9901001', activo=1)
        self.cuenta = CuentaCorriente.objects.create(socio_titular=self.socio, tipo_cuenta='INDIVIDUAL')
        self.concepto = ConceptoCobro.objects.create(codigo='SECURITY_TEST', nombre='Synthetic')
        self.cargo = self.make_charge()
        self.pago = self.make_payment()

    def make_charge(self):
        today = datetime.date.today()
        return crear_cargo(self.cuenta, self.concepto, today.strftime('%Y-%m'), today, today,
                           Decimal('100.00'), usuario=self.actor)

    def make_payment(self):
        return registrar_pago(self.cuenta, datetime.date.today(), Decimal('100.00'),
                              'EFECTIVO', usuario=self.actor)


class FinancialSecurityTests(FinancialFixtures, TestCase):
    def test_services_require_authorized_active_actor(self):
        unprivileged = User.objects.create_user('ordinary')
        for actor in (None, unprivileged):
            with self.subTest(actor=actor):
                with self.assertRaises(PermissionDenied):
                    aplicar_pago(self.pago, self.cargo, 10, usuario=actor)
                with self.assertRaises(PermissionDenied):
                    anular_cargo(self.cargo, usuario=actor)
                with self.assertRaises(PermissionDenied):
                    registrar_pago(self.cuenta, datetime.date.today(), 10, 'EFECTIVO', usuario=actor)
        self.actor.is_active = False
        with self.assertRaises(PermissionDenied):
            aplicar_pago(self.pago, self.cargo, 10, usuario=self.actor)
        self.assertFalse(AplicacionPago.objects.exists())

    def test_invalid_amounts_create_no_application(self):
        for value in ('NaN', 'Infinity', '-Infinity', '0', '-1', '0.001', '100000000', 'bad'):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                aplicar_pago(self.pago, self.cargo, value, usuario=self.actor)
        self.assertFalse(AplicacionPago.objects.exists())

    def test_stale_payment_cannot_spend_twice(self):
        other = self.make_charge()
        aplicar_pago(self.pago, self.cargo, 100, usuario=self.actor)
        with self.assertRaises(ValidationError):
            aplicar_pago(self.pago, other, 100, usuario=self.actor)
        self.assertEqual(self.pago.total_aplicado, Decimal('100.00'))

    def test_stale_charge_cannot_be_overpaid(self):
        other = self.make_payment()
        aplicar_pago(self.pago, self.cargo, 100, usuario=self.actor)
        with self.assertRaises(ValidationError):
            aplicar_pago(other, self.cargo, 100, usuario=self.actor)
        self.assertEqual(self.cargo.total_aplicado, Decimal('100.00'))

    def test_reversal_is_once_and_allows_annulment_preserving_audit(self):
        application = aplicar_pago(self.pago, self.cargo, 100, usuario=self.actor)
        with self.assertRaises(ValidationError):
            anular_cargo(self.cargo, usuario=self.actor)
        revertir_aplicacion(application, motivo='Synthetic correction', usuario=self.actor)
        with self.assertRaises(ValidationError):
            revertir_aplicacion(application, usuario=self.actor)
        anular_cargo(self.cargo, usuario=self.actor)
        application.refresh_from_db()
        self.cargo.refresh_from_db()
        self.assertEqual(application.revertido_por, self.actor)
        self.assertEqual(application.registrado_por, self.actor)
        self.assertEqual(self.cargo.anulado_por, self.actor)
        self.assertEqual(self.cargo.estado, 'ANULADO')
        self.assertEqual(self.pago.saldo_disponible, Decimal('100.00'))
        self.assertEqual(AplicacionPago.objects.count(), 1)

    def test_payment_delete_protected_even_after_reversal(self):
        application = aplicar_pago(self.pago, self.cargo, 100, usuario=self.actor)
        revertir_aplicacion(application, usuario=self.actor)
        with self.assertRaises(ProtectedError):
            self.pago.delete()

    def test_recalculation_failure_rolls_back_payment_application(self):
        with patch('apps.usuarios.services.habilitacion.recalcular_habilitados', side_effect=RuntimeError('synthetic')):
            with self.assertRaises(RuntimeError):
                aplicar_pago(self.pago, self.cargo, 100, usuario=self.actor)
        self.assertFalse(AplicacionPago.objects.exists())
        self.cargo.refresh_from_db()
        self.assertEqual(self.cargo.estado, 'PENDIENTE')

    def test_admin_disallows_financial_delete_and_account_reassignment(self):
        request = RequestFactory().get('/')
        request.user = self.actor
        for model, admin_class, instance in (
            (Pago, PagoAdmin, self.pago), (Cargo, CargoAdmin, self.cargo),
            (CuentaCorriente, CuentaCorrienteAdmin, self.cuenta),
            (AplicacionPago, AplicacionPagoAdmin, None),
        ):
            model_admin = admin_class(model, admin.site)
            self.assertFalse(model_admin.has_delete_permission(request, instance))
        self.assertFalse(CuentaCorrienteAdmin(CuentaCorriente, admin.site).has_change_permission(request, self.cuenta))
        for model, admin_class, instance, fields in (
            (Pago, PagoAdmin, self.pago, ('cuenta', 'importe_total', 'registrado_por')),
            (Cargo, CargoAdmin, self.cargo, ('cuenta', 'importe', 'estado', 'concepto')),
        ):
            form = admin_class(model, admin.site).get_form(request, instance)
            for name in fields:
                self.assertNotIn(name, form.base_fields)

    def test_stale_admin_annotation_cannot_undo_paid_state(self):
        request = RequestFactory().post('/')
        request.user = self.actor
        aplicar_pago(self.pago, self.cargo, 100, usuario=self.actor)
        self.cargo.observaciones = 'Annotation'
        CargoAdmin(Cargo, admin.site).save_model(request, self.cargo, None, True)
        self.cargo.refresh_from_db()
        self.assertEqual(self.cargo.estado, 'PAGADO')
        self.assertEqual(self.cargo.observaciones, 'Annotation')

    def test_application_admin_cannot_overwrite_reversal_with_stale_empty_form(self):
        application = aplicar_pago(self.pago, self.cargo, 100, usuario=self.actor)
        self.client.force_login(self.actor, backend='django.contrib.auth.backends.ModelBackend')
        from django.urls import reverse
        response = self.client.post(reverse('admin:cobranzas_aplicacionpago_change', args=[application.pk]), {'_save': 'Save'})
        self.assertEqual(response.status_code, 403)

    def test_exact_cent_tariff_products_are_normalized_without_rounding(self):
        from apps.cobranzas.services.movimientos import validar_importe
        self.assertEqual(validar_importe(Decimal('2000.00') * Decimal('2.00')).as_tuple().exponent, -2)
        with self.assertRaises(ValidationError):
            validar_importe('12.345')


class FinancialConcurrencyTests(FinancialFixtures, TransactionTestCase):
    """Run these on a disposable MySQL/InnoDB DB; SQLite has no row locks."""
    def race(self, operations):
        barrier = Barrier(len(operations))

        def worker(operation):
            connections.close_all()
            try:
                actor = User.objects.get(pk=self.actor.pk)
                barrier.wait(timeout=10)
                try:
                    operation(actor)
                    return 'ok'
                except ValidationError:
                    return 'rejected'
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(operations)) as pool:
            futures = [pool.submit(worker, operation) for operation in operations]
            return [future.result(timeout=30) for future in futures]

    @skipUnlessDBFeature('has_select_for_update')
    def test_one_payment_two_charges(self):
        other = self.make_charge()
        outcomes = self.race([
            lambda actor: aplicar_pago(self.pago, self.cargo, 100, usuario=actor),
            lambda actor: aplicar_pago(self.pago, other, 100, usuario=actor),
        ])
        self.assertCountEqual(outcomes, ['ok', 'rejected'])
        self.assertEqual(self.pago.total_aplicado, Decimal('100.00'))

    @skipUnlessDBFeature('has_select_for_update')
    def test_two_payments_one_charge(self):
        other = self.make_payment()
        outcomes = self.race([
            lambda actor: aplicar_pago(self.pago, self.cargo, 100, usuario=actor),
            lambda actor: aplicar_pago(other, self.cargo, 100, usuario=actor),
        ])
        self.assertCountEqual(outcomes, ['ok', 'rejected'])
        self.assertEqual(self.cargo.total_aplicado, Decimal('100.00'))

    @skipUnlessDBFeature('has_select_for_update')
    def test_apply_vs_annul(self):
        outcomes = self.race([
            lambda actor: aplicar_pago(self.pago, self.cargo, 100, usuario=actor),
            lambda actor: anular_cargo(self.cargo, usuario=actor),
        ])
        self.assertCountEqual(outcomes, ['ok', 'rejected'])
        self.cargo.refresh_from_db()
        self.assertEqual(self.cargo.total_aplicado, Decimal('0.00') if self.cargo.estado == 'ANULADO' else Decimal('100.00'))

    @skipUnlessDBFeature('has_select_for_update')
    def test_double_reversal(self):
        application = aplicar_pago(self.pago, self.cargo, 100, usuario=self.actor)
        outcomes = self.race([
            lambda actor: revertir_aplicacion(application, usuario=actor),
            lambda actor: revertir_aplicacion(application, usuario=actor),
        ])
        self.assertCountEqual(outcomes, ['ok', 'rejected'])
        self.assertEqual(self.pago.total_aplicado, Decimal('0.00'))
