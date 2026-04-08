import datetime
from django.test import TestCase
from django.core.exceptions import ValidationError
from apps.usuarios.models import Socios, Personas
from apps.cobranzas.models import ConceptoCobro, CuentaCorriente, Cargo
from apps.usuarios.services.socios import crear_solicitud_socio, aprobar_socio, dar_baja_socio

class SocioLifecycleTestCase(TestCase):
    def setUp(self):
        # Crear concepto base para probar reingresos
        ConceptoCobro.objects.create(codigo="MATRICULA", nombre="Matricula Base", importe_por_defecto=2000.00)
        ConceptoCobro.objects.create(codigo="CUOTA_INDIVIDUAL", nombre="Cuota Mes Ind", importe_por_defecto=1500.00)
        ConceptoCobro.objects.create(codigo="CUOTA_FAMILIAR", nombre="Cuota Mes Fam", importe_por_defecto=2500.00)

    def test_crear_solicitud_socio_pendiente(self):
        datos_titular = {
            "Cedula": "12345678",
            "PrimerNombre": "Juan",
            "PrimerApellido": "Perez"
        }
        socio = crear_solicitud_socio(datos_titular)
        
        self.assertEqual(socio.activo, 2)
        self.assertTrue(socio.esta_pendiente)
        self.assertFalse(hasattr(socio, 'cuenta_corriente'))

    def test_aprobar_socio_crea_cuenta(self):
        datos_titular = {"Cedula": "87654321", "PrimerNombre": "Ana", "PrimerApellido": "Gomez"}
        socio = crear_solicitud_socio(datos_titular)
        
        socio_aprobado = aprobar_socio(socio)
        self.assertEqual(socio_aprobado.activo, 1)
        self.assertTrue(hasattr(socio_aprobado, 'cuenta_corriente'))
        self.assertEqual(socio_aprobado.cuenta_corriente.socio_titular, socio_aprobado)

        # Chequear que se genero matrícula y cuota
        cargos = Cargo.objects.filter(cuenta=socio_aprobado.cuenta_corriente)
        self.assertEqual(cargos.count(), 2)

    def test_reingreso_antes_de_un_ano_matricula_doble(self):
        datos_titular = {"Cedula": "11111111", "PrimerNombre": "Carlos"}
        socio = crear_solicitud_socio(datos_titular)
        
        # Simulamos alta y baja con fechas específicas
        socio.activo = 0
        socio.fechaBaja = datetime.date.today() - datetime.timedelta(days=100) # menos de 1 ano
        socio.save()

        # Lo marcamos de nuevo pendiente para re-aprobar
        socio.activo = 2
        socio.save()

        # Re-aprobar deberia chequear fechaBaja
        socio_aprobado = aprobar_socio(socio)
        cargo_mat = Cargo.objects.filter(cuenta=socio_aprobado.cuenta_corriente).order_by('-id').first()
        
        # Segun la logica el monto doble es 4000.00
        from decimal import Decimal
        cargo_mat = Cargo.objects.filter(cuenta=socio_aprobado.cuenta_corriente, concepto__codigo="MATRICULA").first()
        self.assertEqual(cargo_mat.importe, Decimal('4000.00'))

    def test_aprobar_socio_con_deuda_arroja_error(self):
        datos_titular = {"Cedula": "33333333", "PrimerNombre": "Marta"}
        socio = crear_solicitud_socio(datos_titular)
        socio_aprobado = aprobar_socio(socio)
        
        # Simulamos que le dimos baja manteniendo cuenta abierta con deuda (los cargos no se borraron)
        socio_aprobado.activo = 0
        socio_aprobado.save()
        
        # Intentamos re-alta sin pagar (la cuenta sigue ahi, los cargos siguen PENDIENTE)
        socio_aprobado.activo = 2
        socio_aprobado.save()
        
        with self.assertRaisesMessage(ValidationError, "arrastra una deuda pendiente"):
            aprobar_socio(socio_aprobado)

    def test_dar_baja_socio(self):
        datos_titular = {"Cedula": "22222222", "PrimerNombre": "Luis"}
        socio = crear_solicitud_socio(datos_titular)
        socio = aprobar_socio(socio)

        # Validamos baja
        socio_baja = dar_baja_socio(socio, "Baja de prueba")
        self.assertEqual(socio_baja.activo, 0)
        self.assertTrue(socio_baja.esta_de_baja)
