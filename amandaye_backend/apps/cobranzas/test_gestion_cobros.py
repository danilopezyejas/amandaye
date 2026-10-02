import datetime
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth.models import Permission, User
from django.core.exceptions import ValidationError
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
