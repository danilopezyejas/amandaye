import datetime
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth.models import Permission, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from apps.cobranzas.models import Cargo, ComprobantePago, ConceptoCobro, CuentaCorriente, IntencionSaldo, OperacionCobro, Pago
from apps.cobranzas.services.cobros import aplicar_saldo, confirmar_cobro, proponer_aplicaciones
from apps.cobranzas.services.comprobantes import generar_pdf
from apps.usuarios.models import Socios


class CobroWorkflowTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user('tesoreria', password='test-only', is_staff=True)
        for codename, app_label in (
            ('add_pago', 'cobranzas'), ('view_pago', 'cobranzas'),
            ('view_cuentacorriente', 'cobranzas'), ('puede_aplicar_pago', 'cobranzas'),
        ):
            self.actor.user_permissions.add(Permission.objects.get(codename=codename, content_type__app_label=app_label))
        socio = Socios.objects.create(numero=7101, cedulaTitular='7101001', activo=1)
        self.account = CuentaCorriente.objects.create(socio_titular=socio, tipo_cuenta='INDIVIDUAL')
        concept = ConceptoCobro.objects.create(codigo='WORKFLOW', nombre='Cuota de prueba')
        today = datetime.date.today()
        self.charge = Cargo.objects.create(
            cuenta=self.account, concepto=concept, periodo=today.strftime('%Y-%m'),
            fecha_emision=today, fecha_vencimiento=today, importe=Decimal('100.00'),
        )

    def test_proposal_and_atomic_collection_create_receipt(self):
        proposal = proponer_aplicaciones(self.account, Decimal('60.00'), usuario=self.actor)
        self.assertEqual(proposal['filas'][0]['importe'], '60.00')
        operation = confirmar_cobro(
            cuenta=self.account, usuario=self.actor, clave=uuid4(),
            fecha_pago=datetime.date.today(), importe_total=Decimal('60.00'),
            medio_pago=Pago.MedioPago.EFECTIVO, aplicaciones=[
                {'cargo_id': self.charge.pk, 'importe': '60.00'},
            ], intencion_saldo=IntencionSaldo.SIN_CLASIFICAR,
        )
        self.assertEqual(operation.pago.saldo_disponible, Decimal('0.00'))
        receipt = ComprobantePago.objects.get(pago=operation.pago)
        self.assertEqual(receipt.datos['aplicaciones'][0]['cargo_id'], self.charge.pk)
        self.assertGreater(len(generar_pdf(receipt, usuario=self.actor)), 500)

    def test_same_key_same_payload_is_idempotent(self):
        key = uuid4()
        kwargs = dict(
            cuenta=self.account, usuario=self.actor, clave=key,
            fecha_pago=datetime.date.today(), importe_total=Decimal('25.00'),
            medio_pago=Pago.MedioPago.TRANSFERENCIA, referencia='SYNTHETIC-1',
            aplicaciones=[], intencion_saldo=IntencionSaldo.ANTICIPO,
        )
        first = confirmar_cobro(**kwargs)
        second = confirmar_cobro(**kwargs)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Pago.objects.count(), 1)

    def test_same_key_with_changed_payload_is_rejected(self):
        key = uuid4()
        base = dict(
            cuenta=self.account, usuario=self.actor, clave=key,
            fecha_pago=datetime.date.today(), medio_pago=Pago.MedioPago.EFECTIVO,
            aplicaciones=[], intencion_saldo=IntencionSaldo.ANTICIPO,
        )
        confirmar_cobro(**base, importe_total=Decimal('25.00'))
        with self.assertRaises(ValidationError):
            confirmar_cobro(**base, importe_total=Decimal('26.00'))

    def test_stale_proposal_is_rejected(self):
        proposal = proponer_aplicaciones(self.account, Decimal('100.00'), usuario=self.actor)
        Cargo.objects.filter(pk=self.charge.pk).update(importe=Decimal('120.00'))
        with self.assertRaises(ValidationError):
            confirmar_cobro(
                cuenta=self.account, usuario=self.actor, clave=uuid4(),
                fecha_pago=datetime.date.today(), importe_total=Decimal('100.00'),
                medio_pago=Pago.MedioPago.EFECTIVO,
                aplicaciones=[{'cargo_id': self.charge.pk, 'importe': '100.00'}],
                intencion_saldo=IntencionSaldo.SIN_CLASIFICAR, version=proposal['version'],
            )

    def test_existing_payment_application_does_not_create_second_payment(self):
        payment = Pago.objects.create(
            cuenta=self.account, fecha_pago=datetime.date.today(), importe_total=Decimal('40.00'),
            medio_pago=Pago.MedioPago.EFECTIVO, registrado_por=self.actor,
        )
        proposal = proponer_aplicaciones(self.account, payment.saldo_disponible, pago=payment, usuario=self.actor)
        operation = aplicar_saldo(
            pago=payment, usuario=self.actor, clave=uuid4(),
            aplicaciones=[{'cargo_id': self.charge.pk, 'importe': '40.00'}],
            intencion_saldo=IntencionSaldo.SIN_CLASIFICAR, version=proposal['version'],
        )
        self.assertEqual(operation.pago_id, payment.pk)
        self.assertEqual(Pago.objects.count(), 1)

    def second_charge(self):
        return Cargo.objects.create(
            cuenta=self.account, concepto=self.charge.concepto, periodo='2027-01',
            fecha_emision=datetime.date.today(), fecha_vencimiento=datetime.date(2027, 1, 1),
            importe=Decimal('100.00'),
        )

    def collect(self, **changes):
        fields = dict(cuenta=self.account, usuario=self.actor, clave=uuid4(),
            fecha_pago=datetime.date.today(), importe_total=Decimal('40.00'),
            medio_pago=Pago.MedioPago.EFECTIVO, aplicaciones=[],
            intencion_saldo=IntencionSaldo.ANTICIPO)
        fields.update(changes)
        return confirmar_cobro(**fields)

    def test_manual_distribution_can_skip_earliest_charge(self):
        other = self.second_charge()
        proposal = proponer_aplicaciones(self.account, Decimal('40.00'), usuario=self.actor)
        self.assertEqual(len(proposal['filas']), 2)
        self.assertEqual(proposal['filas'][1]['importe'], '0.00')
        operation = self.collect(aplicaciones=[{'cargo_id': other.pk, 'importe': '40.00'}], version=proposal['version'])
        self.assertEqual(operation.pago.total_aplicado, Decimal('40.00'))
        self.assertEqual(self.charge.total_aplicado, Decimal('0.00'))

    def test_overallocation_rolls_back_all_records(self):
        other = self.second_charge()
        with self.assertRaises(ValidationError):
            self.collect(aplicaciones=[{'cargo_id': c.pk, 'importe': '30.00'} for c in (self.charge, other)])
        self.assertFalse(Pago.objects.exists())
        self.assertFalse(OperacionCobro.objects.exists())
        self.assertFalse(ComprobantePago.objects.exists())

    def test_invalid_distribution_payloads_make_no_payment(self):
        for rows in ('bad', {'cargo_id': 1}, [None], [{'cargo_id': self.charge.pk, 'importe': '-1'}],
                     [{'cargo_id': self.charge.pk, 'importe': '1'}] * 2,
                     [{'cargo_id': 999999, 'importe': '1'}]):
            with self.subTest(rows=rows), self.assertRaises(ValidationError):
                self.collect(aplicaciones=rows)
        self.assertFalse(Pago.objects.exists())

    def test_existing_balance_retry_preserves_original_receipt(self):
        original = self.collect()
        snapshot = ComprobantePago.objects.get(pago=original.pago).datos
        proposal = proponer_aplicaciones(self.account, 40, pago=original.pago, usuario=self.actor)
        fields = dict(pago=original.pago, usuario=self.actor, clave=uuid4(),
            aplicaciones=[{'cargo_id': self.charge.pk, 'importe': '40.00'}],
            intencion_saldo=IntencionSaldo.SIN_CLASIFICAR, version=proposal['version'])
        first = aplicar_saldo(**fields)
        self.assertEqual(aplicar_saldo(**fields).pk, first.pk)
        self.assertEqual(Pago.objects.count(), 1)
        self.assertEqual(OperacionCobro.objects.count(), 2)
        self.assertEqual(ComprobantePago.objects.get(pago=original.pago).datos, snapshot)
        with self.assertRaises(ValidationError):
            aplicar_saldo(**{**fields, 'aplicaciones': []})

    def test_permission_revocation_blocks_idempotent_retry(self):
        key = uuid4()
        self.collect(clave=key)
        permission = Permission.objects.get(codename='puede_aplicar_pago', content_type__app_label='cobranzas')
        self.actor.user_permissions.remove(permission)
        self.actor = User.objects.get(pk=self.actor.pk)
        with self.assertRaises(PermissionDenied):
            self.collect(clave=key)
        self.assertEqual(Pago.objects.count(), 1)

    def test_pending_charge_from_other_account_is_rejected(self):
        socio = Socios.objects.create(numero=7102, cedulaTitular='7102001', activo=1)
        other = CuentaCorriente.objects.create(socio_titular=socio, tipo_cuenta='INDIVIDUAL')
        Cargo.objects.filter(pk=self.charge.pk).update(cuenta=other)
        with self.assertRaises(ValidationError):
            self.collect(aplicaciones=[{'cargo_id': self.charge.pk, 'importe': '1.00'}])
        self.assertFalse(Pago.objects.exists())

    def test_proposal_query_count_does_not_grow_per_charge(self):
        self.actor.has_perm('cobranzas.view_cuentacorriente')
        for _ in range(5):
            self.second_charge()
        with self.assertNumQueries(1):
            proposal = proponer_aplicaciones(self.account, 40, usuario=self.actor)
        self.assertEqual(len(proposal['filas']), 6)
