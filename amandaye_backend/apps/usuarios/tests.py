import datetime
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from apps.usuarios.models import Socios, Personas
from apps.cobranzas.models import ConceptoCobro, CuentaCorriente, Cargo, Pago, AplicacionPago
from apps.usuarios.services.socios import crear_solicitud_socio, aprobar_socio, rechazar_socio, dar_baja_socio
from apps.cobranzas.services.pagos import aplicar_pago, revertir_aplicacion, registrar_pago
from apps.cobranzas.services.cuentas import obtener_estado_cuenta
from apps.cobranzas.services.cargos import crear_cargo


# ---------------------------------------------------------------------------
# Helpers de test
# ---------------------------------------------------------------------------

TITULAR_VALIDO = {
    "Cedula": "12345678",
    "PrimerNombre": "Juan",
    "PrimerApellido": "Perez",
    "FechaNacimiento": "1990-01-15",
    "Celular": "099123456",
    "Direccion": "Calle Falsa 123",
}


def titular(**kwargs):
    d = TITULAR_VALIDO.copy()
    d.update(kwargs)
    return d


class SetUpConceptosMixin:
    def setUp(self):
        ConceptoCobro.objects.create(codigo="MATRICULA", nombre="Matrícula", importe_por_defecto=Decimal('2000.00'))
        ConceptoCobro.objects.create(codigo="CUOTA_INDIVIDUAL", nombre="Cuota Individual", importe_por_defecto=Decimal('1500.00'))
        ConceptoCobro.objects.create(codigo="CUOTA_FAMILIAR", nombre="Cuota Familiar", importe_por_defecto=Decimal('2500.00'))


# ---------------------------------------------------------------------------
# Tests: Flujo de Socios
# ---------------------------------------------------------------------------

class SocioSolicitudTest(SetUpConceptosMixin, TestCase):

    def test_01_crear_solicitud_pendiente_con_fecha_solicitud(self):
        """Crear solicitud setea activo=2 y fechaSolicitud, sin fechaAlta."""
        socio = crear_solicitud_socio(titular())
        self.assertEqual(socio.activo, 2)
        self.assertTrue(socio.esta_pendiente)
        self.assertIsNotNone(socio.fechaSolicitud)
        self.assertIsNone(socio.fechaAlta)

    def test_02_pendiente_no_crea_cuenta_corriente(self):
        """Un socio pendiente no debe tener CuentaCorriente."""
        socio = crear_solicitud_socio(titular())
        self.assertFalse(CuentaCorriente.objects.filter(socio_titular=socio).exists())

    def test_03_aprobar_crea_cuenta_y_setea_fechas(self):
        """Aprobar debe setear fechaAprobacion, fechaAlta y crear CuentaCorriente."""
        socio = crear_solicitud_socio(titular())
        socio_aprobado = aprobar_socio(socio)
        self.assertEqual(socio_aprobado.activo, 1)
        self.assertIsNotNone(socio_aprobado.fechaAprobacion)
        self.assertIsNotNone(socio_aprobado.fechaAlta)
        self.assertTrue(CuentaCorriente.objects.filter(socio_titular=socio_aprobado).exists())
        # Debe tener 2 cargos: matrícula + cuota
        cargos = Cargo.objects.filter(cuenta=socio_aprobado.cuenta_corriente)
        self.assertEqual(cargos.count(), 2)

    def test_04_rechazar_socio_pendiente(self):
        """Rechazar deja al socio en estado 3 (RECHAZADO) sin fechaAlta."""
        socio = crear_solicitud_socio(titular(Cedula="11111111"))
        rechazar_socio(socio, motivo="No cumple requisitos")
        socio.refresh_from_db()
        self.assertEqual(socio.activo, 3)
        self.assertTrue(socio.esta_rechazado)
        self.assertIsNone(socio.fechaAlta)
        self.assertFalse(CuentaCorriente.objects.filter(socio_titular=socio).exists())

    def test_05_no_se_puede_aprobar_socio_rechazado(self):
        """Intentar aprobar un RECHAZADO debe lanzar ValidationError."""
        socio = crear_solicitud_socio(titular(Cedula="22222222"))
        rechazar_socio(socio)
        with self.assertRaisesMessage(ValidationError, "RECHAZADO"):
            aprobar_socio(socio)

    def test_06_no_se_puede_rechazar_socio_activo(self):
        """No se puede rechazar un socio ya ACTIVO."""
        socio = crear_solicitud_socio(titular(Cedula="33333333"))
        aprobar_socio(socio)
        socio.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, "ALTA"):
            rechazar_socio(socio)

    def test_07_baja_cierra_cuenta_siempre(self):
        """Dar de baja debe cerrar la CuentaCorriente aunque tenga deuda."""
        socio = crear_solicitud_socio(titular(Cedula="44444444"))
        aprobar_socio(socio)
        socio.refresh_from_db()
        dar_baja_socio(socio, "Prueba")
        socio.refresh_from_db()
        self.assertEqual(socio.activo, 0)
        cc = CuentaCorriente.objects.get(socio_titular=socio)
        self.assertEqual(cc.estado, CuentaCorriente.Estado.CERRADA)

    def test_08_baja_con_deuda_estado_moroso(self):
        """Baja con deuda pendiente resulta en estado_cuenta=MOROSO."""
        socio = crear_solicitud_socio(titular(Cedula="55555555"))
        aprobar_socio(socio)
        socio.refresh_from_db()
        dar_baja_socio(socio, "Baja moroso")
        cc = CuentaCorriente.objects.get(socio_titular=socio)
        estado = obtener_estado_cuenta(cc)
        self.assertEqual(estado['estado_cuenta'], 'MOROSO')


# ---------------------------------------------------------------------------
# Tests: Validaciones de edad y datos
# ---------------------------------------------------------------------------

class ValidacionesTest(SetUpConceptosMixin, TestCase):

    def test_09_titular_menor_de_edad_falla(self):
        """Titular con menos de 18 años debe lanzar error."""
        datos = titular(Cedula="60000001", FechaNacimiento=str(datetime.date.today() - datetime.timedelta(days=365 * 17)))
        with self.assertRaisesMessage(ValidationError, "mayor de edad"):
            crear_solicitud_socio(datos)

    def test_10_pareja_menor_de_edad_falla(self):
        """Pareja/tutor menor de 18 años debe lanzar error."""
        familiar_menor = {
            "Cedula": "70000001",
            "PrimerNombre": "Ana",
            "PrimerApellido": "Lopez",
            "FechaNacimiento": str(datetime.date.today() - datetime.timedelta(days=365 * 16)),
            "relacionTitular": "PAREJA",
        }
        with self.assertRaisesMessage(ValidationError, "mayor de edad"):
            crear_solicitud_socio(titular(Cedula="60000002"), datos_familiares=[familiar_menor])

    def test_11_hijo_mayor_de_edad_falla(self):
        """Hijo con 18 o más años debe lanzar error."""
        hijo_mayor = {
            "Cedula": "70000002",
            "PrimerNombre": "Carlos",
            "PrimerApellido": "Gomez",
            "FechaNacimiento": str(datetime.date.today() - datetime.timedelta(days=365 * 20)),
            "relacionTitular": "HIJO",
        }
        with self.assertRaisesMessage(ValidationError, "menores de 18"):
            crear_solicitud_socio(titular(Cedula="60000003"), datos_familiares=[hijo_mayor])

    def test_12_titular_sin_campos_obligatorios_falla(self):
        """Faltar campo obligatorio del titular debe fallar."""
        with self.assertRaises(ValidationError):
            crear_solicitud_socio({"Cedula": "60000004", "PrimerNombre": "Test"})  # Falta Apellido, Tel, Dir, FechaNac

    def test_13_familiar_sin_campos_obligatorios_falla(self):
        """Faltar campo obligatorio en familiar debe fallar."""
        familiar_incompleto = {"Cedula": "70000003", "relacionTitular": "HIJO"}  # Sin nombre, fecha nac
        with self.assertRaises(ValidationError):
            crear_solicitud_socio(titular(Cedula="60000005"), datos_familiares=[familiar_incompleto])

    def test_14_mas_de_una_pareja_falla(self):
        """Más de 1 pareja/tutor debe lanzar error."""
        def hacer_pareja(cedula):
            return {
                "Cedula": cedula,
                "PrimerNombre": "Ana",
                "PrimerApellido": "X",
                "FechaNacimiento": "1990-01-01",
                "relacionTitular": "PAREJA",
            }
        with self.assertRaisesMessage(ValidationError, "1 pareja"):
            crear_solicitud_socio(titular(Cedula="60000006"), datos_familiares=[hacer_pareja("70000010"), hacer_pareja("70000011")])

    def test_15_mas_de_dos_hijos_falla(self):
        """Más de 2 hijos debe lanzar error."""
        def hacer_hijo(cedula):
            return {
                "Cedula": cedula,
                "PrimerNombre": "Nino",
                "PrimerApellido": "X",
                "FechaNacimiento": "2015-06-01",
                "relacionTitular": "HIJO",
            }
        with self.assertRaisesMessage(ValidationError, "2 hijos"):
            crear_solicitud_socio(titular(Cedula="60000007"), datos_familiares=[
                hacer_hijo("70000020"), hacer_hijo("70000021"), hacer_hijo("70000022")
            ])


# ---------------------------------------------------------------------------
# Tests: Cobranzas
# ---------------------------------------------------------------------------

class CobranzasTest(SetUpConceptosMixin, TestCase):

    def test_16_matricula_usa_importe_por_defecto(self):
        """La matrícula debe usar importe_por_defecto del ConceptoCobro, no un valor hardcodeado."""
        socio = crear_solicitud_socio(titular(Cedula="80000001"))
        aprobar_socio(socio)
        socio.refresh_from_db()
        cargo_mat = Cargo.objects.get(cuenta=socio.cuenta_corriente, concepto__codigo="MATRICULA")
        self.assertEqual(cargo_mat.importe, Decimal('2000.00'))

    def test_17_cuota_usa_importe_por_defecto(self):
        """La cuota mensual debe usar importe_por_defecto del ConceptoCobro."""
        socio = crear_solicitud_socio(titular(Cedula="80000002"))
        aprobar_socio(socio)
        socio.refresh_from_db()
        cargo_cuota = Cargo.objects.get(cuenta=socio.cuenta_corriente, concepto__codigo="CUOTA_INDIVIDUAL")
        self.assertEqual(cargo_cuota.importe, Decimal('1500.00'))

    def test_18_revertir_aplicacion_no_borra_registro(self):
        """Revertir aplicación no debe eliminar el registro de AplicacionPago."""
        socio = crear_solicitud_socio(titular(Cedula="80000003"))
        aprobar_socio(socio)
        socio.refresh_from_db()
        cc = socio.cuenta_corriente
        cargo = Cargo.objects.filter(cuenta=cc).first()

        pago = registrar_pago(cc, datetime.date.today(), Decimal('500.00'), 'EFECTIVO')
        aplicacion = aplicar_pago(pago, cargo, Decimal('500.00'))
        aplicacion_id = aplicacion.id

        revertir_aplicacion(aplicacion, motivo="Error de prueba")

        # El registro debe seguir existiendo
        self.assertTrue(AplicacionPago.objects.filter(id=aplicacion_id).exists())
        ap = AplicacionPago.objects.get(id=aplicacion_id)
        self.assertEqual(ap.estado, 'REVERTIDA')
        self.assertIsNotNone(ap.motivo_reversion)

    def test_19_aplicacion_revertida_no_suma_al_saldo(self):
        """Una aplicación revertida no debe influir en el saldo del cargo."""
        socio = crear_solicitud_socio(titular(Cedula="80000004"))
        aprobar_socio(socio)
        socio.refresh_from_db()
        cc = socio.cuenta_corriente
        cargo = Cargo.objects.filter(cuenta=cc).first()
        saldo_original = cargo.saldo_pendiente

        pago = registrar_pago(cc, datetime.date.today(), Decimal('500.00'), 'EFECTIVO')
        aplicacion = aplicar_pago(pago, cargo, Decimal('500.00'))
        revertir_aplicacion(aplicacion)

        cargo.refresh_from_db()
        self.assertEqual(cargo.saldo_pendiente, saldo_original)

    def test_20_recalculo_estado_cargo_luego_de_revertir(self):
        """Revertir una aplicación completa debe dejar el cargo en PENDIENTE."""
        socio = crear_solicitud_socio(titular(Cedula="80000005"))
        aprobar_socio(socio)
        socio.refresh_from_db()
        cc = socio.cuenta_corriente
        cargo = Cargo.objects.filter(cuenta=cc).first()

        pago = registrar_pago(cc, datetime.date.today(), cargo.importe, 'EFECTIVO')
        aplicacion = aplicar_pago(pago, cargo, cargo.importe)
        cargo.refresh_from_db()
        self.assertEqual(cargo.estado, Cargo.Estado.PAGADO)

        revertir_aplicacion(aplicacion)
        cargo.refresh_from_db()
        self.assertEqual(cargo.estado, Cargo.Estado.PENDIENTE)

    def test_21_matricula_doble_dentro_del_anio(self):
        """Reingreso en menos de 1 año debe cobrar matrícula doble."""
        socio = crear_solicitud_socio(titular(Cedula="80000006"))
        aprobar_socio(socio)
        socio.refresh_from_db()
        dar_baja_socio(socio, "Baja temporal")
        socio.refresh_from_db()

        # Simular baja reciente (90 días)
        socio.fechaBaja = datetime.date.today() - datetime.timedelta(days=90)
        socio.activo = 2  # Volver a pendiente para reingreso
        socio.save()

        # Pagar la deuda para poder reafiliarse
        cc = CuentaCorriente.objects.get(socio_titular=socio)
        cargos_pendientes = Cargo.objects.filter(cuenta=cc, estado=Cargo.Estado.PENDIENTE)
        saldo = sum(c.saldo_pendiente for c in cargos_pendientes)
        if saldo > 0:
            pago = registrar_pago(cc, datetime.date.today(), saldo, 'EFECTIVO')
            for c in cargos_pendientes:
                aplicar_pago(pago, c, c.saldo_pendiente)

        socio_reingresado = aprobar_socio(socio)
        cargo_mat = Cargo.objects.filter(
            cuenta=socio_reingresado.cuenta_corriente,
            concepto__codigo="MATRICULA"
        ).order_by('-id').first()
        self.assertEqual(cargo_mat.importe, Decimal('4000.00'))  # importe_por_defecto * 2

    def test_22_aplicacion_pago_clean_saldos(self):
        """clean() de AplicacionPago debe arrojar error si supera saldo de cargo o pago."""
        socio = crear_solicitud_socio(titular(Cedula="80000007"))
        aprobar_socio(socio)
        cc = socio.cuenta_corriente
        cargo = Cargo.objects.filter(cuenta=cc, concepto__codigo="MATRICULA").first()
        
        # Supera el importe del pago
        pago_corto = registrar_pago(cc, datetime.date.today(), Decimal('500.00'), 'EFECTIVO')
        app_corta = AplicacionPago(pago=pago_corto, cargo=cargo, importe_aplicado=Decimal('1000.00'))
        with self.assertRaises(ValidationError) as cm:
            app_corta.clean()
        self.assertIn("supera el saldo disponible del pago", str(cm.exception))

        # Supera el saldo del cargo
        pago_largo = registrar_pago(cc, datetime.date.today(), Decimal('10000.00'), 'EFECTIVO')
        app_larga = AplicacionPago(pago=pago_largo, cargo=cargo, importe_aplicado=Decimal('5000.00'))
        with self.assertRaises(ValidationError) as cm:
            app_larga.clean()
        self.assertIn("supera el saldo pendiente del cargo", str(cm.exception))

    def test_23_aplicacion_pago_clean_cuentas_distintas(self):
        """clean() de AplicacionPago debe arrojar error si pago y cargo son de cuentas distintas."""
        socio1 = crear_solicitud_socio(titular(Cedula="90000001"))
        socio2 = crear_solicitud_socio(titular(Cedula="90000002"))
        aprobar_socio(socio1)
        aprobar_socio(socio2)
        
        cc1 = socio1.cuenta_corriente
        cc2 = socio2.cuenta_corriente
        
        cargo1 = Cargo.objects.filter(cuenta=cc1).first()
        pago2 = registrar_pago(cc2, datetime.date.today(), Decimal('500.00'), 'EFECTIVO')
        
        # Intento pagar cargo de CC1 con un pago de CC2
        app = AplicacionPago(pago=pago2, cargo=cargo1, importe_aplicado=Decimal('500.00'))
        with self.assertRaises(ValidationError) as cm:
            app.clean()
        self.assertIn("misma cuenta", str(cm.exception))


# ---------------------------------------------------------------------------
# Tests: Habilitaciones y Nuevos Tipos de Cuota
# ---------------------------------------------------------------------------
from django.contrib.auth.models import User
from apps.usuarios.models import AprobacionProfesor, AvalComisionDirectiva
from apps.cobranzas.services.cuotas import generar_cuotas_mensuales
from apps.usuarios.services.habilitacion import recalcular_habilitacion_persona

class HabilitacionesYCuotasTest(SetUpConceptosMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.user_cd = User.objects.create_user(username='cd_user', password='123')
        ConceptoCobro.objects.create(codigo="CUOTA_TEMPORADA", nombre="Cuota Temporada", importe_por_defecto=Decimal('1000.00'))

    def _setup_socio_habilitable(self, cedula="10101010"):
        socio = crear_solicitud_socio(titular(
            Cedula=cedula,
            FechaNacimiento=str(datetime.date.today() - datetime.timedelta(days=365 * 25))
        ))
        socio.tipo_cuota = 'ANUAL'
        socio.save()
        socio = aprobar_socio(socio)
        
        # Set antiguedad > 1 year
        socio.fechaAprobacion = datetime.date.today() - datetime.timedelta(days=366)
        socio.save()
        
        persona = Personas.objects.get(Cedula=cedula)
        
        # Aprobacion profe
        AprobacionProfesor.objects.create(
            persona=persona,
            numero_socio_momento=socio.numero,
            nombre_profesor='Profe Test',
            fecha=socio.fechaAprobacion + datetime.timedelta(days=1)
        )
        
        # Aval CD
        AvalComisionDirectiva.objects.create(
            persona=persona,
            usuario_cd=self.user_cd,
            fecha_aval=datetime.date.today()
        )
        
        # Explicit recalculation with fresh db object
        persona = Personas.objects.get(Cedula=cedula)
        recalcular_habilitacion_persona(persona)
        persona.refresh_from_db()
        
        return socio, persona

    def test_24_temporada_no_habilitado(self):
        socio, persona = self._setup_socio_habilitable("10101010")
        self.assertEqual(persona.estado_habilitacion, 'HABILITADO')
        
        socio.tipo_cuota = 'TEMPORADA'
        socio.save()
        recalcular_habilitacion_persona(persona)
        persona.refresh_from_db()
        
        self.assertEqual(persona.estado_habilitacion, 'NO_HABILITADO')

    def test_25_menor_de_edad_no_habilitado(self):
        socio, persona = self._setup_socio_habilitable("10101011")
        persona.FechaNacimiento = datetime.date.today() - datetime.timedelta(days=365 * 17)
        persona.save()
        recalcular_habilitacion_persona(persona)
        persona.refresh_from_db()
        
        self.assertEqual(persona.estado_habilitacion, 'NO_HABILITADO')

    def test_26_antiguedad_menor_365_dias_no_habilitado(self):
        socio, persona = self._setup_socio_habilitable("10101012")
        socio.fechaAprobacion = datetime.date.today() - datetime.timedelta(days=300)
        socio.save()
        recalcular_habilitacion_persona(persona)
        persona.refresh_from_db()
        
        self.assertEqual(persona.estado_habilitacion, 'NO_HABILITADO')

    def test_27_sin_aprobacion_profesor_post_alta(self):
        socio, persona = self._setup_socio_habilitable("10101013")
        persona.aprobaciones_profesor.all().delete()
        recalcular_habilitacion_persona(persona)
        persona.refresh_from_db()
        self.assertEqual(persona.estado_habilitacion, 'NO_HABILITADO')

    def test_28_sin_aval_cd_activo(self):
        socio, persona = self._setup_socio_habilitable("10101014")
        aval = persona.avales_cd.first()
        aval.revocar(self.user_cd, "Test")
        persona.refresh_from_db()
        self.assertEqual(persona.estado_habilitacion, 'NO_HABILITADO')

    def test_29_3_cargos_pendientes_suspendido(self):
        socio, persona = self._setup_socio_habilitable("10101015")
        
        hoy = datetime.date.today()
        d = hoy
        concepto = ConceptoCobro.objects.get(codigo="CUOTA_INDIVIDUAL")
        for _ in range(3):
            crear_cargo(socio.cuenta_corriente, concepto, d.strftime('%Y-%m'), d, d, concepto.importe_por_defecto)
            d = d.replace(day=1) - datetime.timedelta(days=1)
            
        recalcular_habilitacion_persona(persona)
        persona.refresh_from_db()
        self.assertEqual(persona.estado_habilitacion, 'SUSPENDIDO')

    def test_30_suspendido_que_paga_se_rehabilita(self):
        socio, persona = self._setup_socio_habilitable("10101016")
        
        hoy = datetime.date.today()
        d = hoy
        concepto = ConceptoCobro.objects.get(codigo="CUOTA_INDIVIDUAL")
        for _ in range(3):
            crear_cargo(socio.cuenta_corriente, concepto, d.strftime('%Y-%m'), d, d, concepto.importe_por_defecto)
            d = d.replace(day=1) - datetime.timedelta(days=1)
            
        recalcular_habilitacion_persona(persona)
        persona.refresh_from_db()
        self.assertEqual(persona.estado_habilitacion, 'SUSPENDIDO')
        
        cargo = socio.cuenta_corriente.cargos.filter(estado=Cargo.Estado.PENDIENTE).first()
        pago = registrar_pago(socio.cuenta_corriente, hoy, cargo.importe, 'EFECTIVO')
        aplicar_pago(pago, cargo, cargo.importe)
        
        persona.refresh_from_db()
        self.assertEqual(persona.estado_habilitacion, 'HABILITADO')

    def test_31_revocado_no_cambia_sin_nuevo_aval(self):
        socio, persona = self._setup_socio_habilitable("10101017")
        persona.estado_habilitacion = 'REVOCADO'
        persona.save(update_fields=['estado_habilitacion'])
        
        persona.save()
        self.assertEqual(persona.estado_habilitacion, 'REVOCADO')

    def test_32_cuota_beca_aplica_50_por_ciento(self):
        socio, persona = self._setup_socio_habilitable("10101018")
        socio.tipo_cuota = 'BECA'
        socio.tipo_socio = 'INDIVIDUAL'
        socio.save()
        
        periodo = (datetime.date.today() + datetime.timedelta(days=365)).strftime('%Y-%m')
        generar_cuotas_mensuales(periodo)
        
        cargo = Cargo.objects.filter(cuenta=socio.cuenta_corriente, periodo=periodo).first()
        self.assertEqual(cargo.importe, Decimal('750.00'))

    def test_33_exonerado_no_genera_cargo(self):
        socio, persona = self._setup_socio_habilitable("10101019")
        socio.tipo_cuota = 'EXONERADO'
        socio.save()
        
        periodo = (datetime.date.today() + datetime.timedelta(days=365)).strftime('%Y-%m')
        generar_cuotas_mensuales(periodo)
        
        exists = Cargo.objects.filter(cuenta=socio.cuenta_corriente, periodo=periodo).exists()
        self.assertFalse(exists)

