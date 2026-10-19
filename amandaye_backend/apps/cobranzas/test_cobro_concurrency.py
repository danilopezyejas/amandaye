import datetime
from decimal import Decimal
from uuid import uuid4

from django.test import TransactionTestCase, skipUnlessDBFeature

from apps.cobranzas import test_security as fixtures
from apps.cobranzas.models import OperacionCobro, Pago, IntencionSaldo
from apps.cobranzas.services.cobros import aplicar_saldo, confirmar_cobro, proponer_aplicaciones


class CobroConcurrencyTests(fixtures.FinancialFixtures, TransactionTestCase):
    race = fixtures.FinancialConcurrencyTests.race

    @skipUnlessDBFeature('has_select_for_update')
    def test_simultaneous_confirmation_creates_only_one_payment(self):
        key = uuid4()
        proposal = proponer_aplicaciones(self.cuenta, 100, usuario=self.actor)
        def collect(actor):
            confirmar_cobro(cuenta=self.cuenta, usuario=actor, clave=key,
                fecha_pago=datetime.date.today(), importe_total=Decimal('100.00'),
                medio_pago=Pago.MedioPago.EFECTIVO, intencion_saldo=IntencionSaldo.SIN_CLASIFICAR,
                aplicaciones=[{'cargo_id': self.cargo.pk, 'importe': '100.00'}], version=proposal['version'])
        self.assertEqual(self.race([collect, collect]), ['ok', 'ok'])
        self.assertEqual(Pago.objects.count(), 2)  # One fixture payment plus one new collection.
        self.assertEqual(OperacionCobro.objects.count(), 1)
        self.assertEqual(self.cargo.total_aplicado, Decimal('100.00'))

    @skipUnlessDBFeature('has_select_for_update')
    def test_existing_balance_cannot_be_spent_twice(self):
        other = self.make_charge()
        proposal = proponer_aplicaciones(self.cuenta, 100, pago=self.pago, usuario=self.actor)
        def apply(cargo):
            def operation(actor):
                aplicar_saldo(pago=self.pago, usuario=actor, clave=uuid4(),
                    aplicaciones=[{'cargo_id': cargo.pk, 'importe': '100.00'}],
                    intencion_saldo=IntencionSaldo.SIN_CLASIFICAR, version=proposal['version'])
            return operation
        self.assertCountEqual(self.race([apply(self.cargo), apply(other)]), ['ok', 'rejected'])
        self.assertEqual(Pago.objects.count(), 1)
        self.assertEqual(OperacionCobro.objects.count(), 1)
        self.assertEqual(self.pago.total_aplicado, Decimal('100.00'))

    @skipUnlessDBFeature('has_select_for_update')
    def test_same_existing_balance_confirmation_is_idempotent(self):
        key = uuid4()
        proposal = proponer_aplicaciones(self.cuenta, 100, pago=self.pago, usuario=self.actor)
        def apply(actor):
            aplicar_saldo(pago=self.pago, usuario=actor, clave=key,
                aplicaciones=[{'cargo_id': self.cargo.pk, 'importe': '100.00'}],
                intencion_saldo=IntencionSaldo.SIN_CLASIFICAR, version=proposal['version'])
        self.assertEqual(self.race([apply, apply]), ['ok', 'ok'])
        self.assertEqual(Pago.objects.count(), 1)
        self.assertEqual(OperacionCobro.objects.count(), 1)
