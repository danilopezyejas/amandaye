import datetime
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from apps.cobranzas.models import CuentaCorriente, ConceptoCobro, Cargo, Pago, AplicacionPago
from apps.usuarios.models import Socios
from apps.cobranzas.services.cuentas import crear_cuenta_corriente_para_titular, obtener_estado_cuenta
from apps.cobranzas.services.cargos import crear_cargo, anular_cargo
from apps.cobranzas.services.pagos import registrar_pago, aplicar_pago, revertir_aplicacion
from apps.cobranzas.services.cuotas import generar_cuotas_mensuales

class CobranzasServicesTestCase(TestCase):
    def setUp(self):
        self.socio = Socios.objects.create(
            numero=1001,
            tipo="INDIVIDUAL",
            cedulaTitular="12345678",
            activo=1,
            fechaAlta=datetime.date(2025, 1, 1)
        )
        self.cuenta = crear_cuenta_corriente_para_titular(self.socio)
        self.concepto = ConceptoCobro.objects.create(
            codigo='TEST_CONCEPTO',
            nombre='Concepto Test'
        )

    def test_crear_cuenta(self):
        self.assertEqual(CuentaCorriente.objects.count(), 1)
        self.assertEqual(self.cuenta.tipo_cuenta, CuentaCorriente.TipoCuenta.INDIVIDUAL)

    def test_crear_cargo(self):
        cargo = crear_cargo(
            cuenta=self.cuenta,
            concepto=self.concepto,
            periodo="2026-04",
            fecha_emision=datetime.date(2026, 4, 1),
            fecha_vencimiento=datetime.date(2026, 4, 10),
            importe=Decimal('1000.00')
        )
        self.assertEqual(cargo.importe, Decimal('1000.00'))
        self.assertEqual(cargo.saldo_pendiente, Decimal('1000.00'))
        
    def test_aplicar_pago_completo(self):
        cargo = crear_cargo(
            cuenta=self.cuenta, concepto=self.concepto, periodo="2026-04",
            fecha_emision=datetime.date.today(), fecha_vencimiento=datetime.date.today(), importe=Decimal('1000.00')
        )
        pago = registrar_pago(self.cuenta, datetime.date.today(), Decimal('1000.00'), 'EFECTIVO')
        
        aplicacion = aplicar_pago(pago, cargo, Decimal('1000.00'))
        
        cargo.refresh_from_db()
        pago.refresh_from_db()
        
        self.assertEqual(cargo.estado, Cargo.Estado.PAGADO)
        self.assertEqual(cargo.saldo_pendiente, Decimal('0.00'))
        self.assertEqual(pago.saldo_disponible, Decimal('0.00'))

    def test_aplicar_pago_parcial(self):
        cargo = crear_cargo(
            cuenta=self.cuenta, concepto=self.concepto, periodo="2026-04",
            fecha_emision=datetime.date.today(), fecha_vencimiento=datetime.date.today(), importe=Decimal('1000.00')
        )
        pago = registrar_pago(self.cuenta, datetime.date.today(), Decimal('500.00'), 'EFECTIVO')
        
        aplicar_pago(pago, cargo, Decimal('500.00'))
        
        cargo.refresh_from_db()
        self.assertEqual(cargo.estado, Cargo.Estado.PARCIAL)
        self.assertEqual(cargo.saldo_pendiente, Decimal('500.00'))

    def test_revertir_aplicacion(self):
        cargo = crear_cargo(
            cuenta=self.cuenta, concepto=self.concepto, periodo="2026-04",
            fecha_emision=datetime.date.today(), fecha_vencimiento=datetime.date.today(), importe=Decimal('1000.00')
        )
        pago = registrar_pago(self.cuenta, datetime.date.today(), Decimal('1000.00'), 'EFECTIVO')
        aplicacion = aplicar_pago(pago, cargo, Decimal('1000.00'))
        
        revertir_aplicacion(aplicacion)
        cargo.refresh_from_db()
        
        self.assertEqual(cargo.estado, Cargo.Estado.PENDIENTE)
        self.assertEqual(cargo.saldo_pendiente, Decimal('1000.00'))

    def test_anular_cargo_sin_pagos(self):
        cargo = crear_cargo(
            cuenta=self.cuenta, concepto=self.concepto, periodo="2026-04",
            fecha_emision=datetime.date.today(), fecha_vencimiento=datetime.date.today(), importe=Decimal('1000.00')
        )
        anular_cargo(cargo)
        cargo.refresh_from_db()
        self.assertEqual(cargo.estado, Cargo.Estado.ANULADO)
        self.assertEqual(cargo.saldo_pendiente, Decimal('0.00'))
