import datetime
from types import SimpleNamespace
from unittest.mock import Mock
from django.test import SimpleTestCase
from apps.usuarios.services.habilitacion import evaluar_condiciones, evaluar_habilitacion


class MotivosHabilitacionTests(SimpleTestCase):
    def facts(self, **overrides):
        return dict(revocado=False, socio_existe=True, activo=True, temporada=False,
            nacimiento=datetime.date(2000, 1, 1), fecha_base=datetime.date(2025, 1, 1),
            aprobacion=True, aval=True, cargos=(), hoy=datetime.date(2026, 10, 20)) | overrides

    def test_eligible_has_no_reasons(self):
        self.assertEqual(evaluar_condiciones(**self.facts()), {'estado': 'HABILITADO', 'motivos': []})

    def test_revocation_precedes_missing_member_and_debt(self):
        result = evaluar_condiciones(**self.facts(revocado=True, socio_existe=False))
        self.assertEqual(result['estado'], 'REVOCADO')
        self.assertEqual([r[0] for r in result['motivos']], ['REVOCADO'])

    def test_missing_member_has_one_data_reason(self):
        self.assertEqual(evaluar_condiciones(**self.facts(socio_existe=False))['motivos'][0][0], 'SIN_SOCIO')

    def test_suspension_requires_all_charges_in_all_three_periods(self):
        cargos = [('2026-10', 'PENDIENTE'), ('2026-09', 'PARCIAL'), ('2026-08', 'PENDIENTE')]
        self.assertEqual(evaluar_condiciones(**self.facts(cargos=cargos, activo=False))['estado'], 'SUSPENDIDO')
        for altered in (cargos[:2], cargos + [('2026-09', 'PAGADO')], cargos + [('2026-08', 'ANULADO')]):
            self.assertEqual(evaluar_condiciones(**self.facts(cargos=altered))['estado'], 'HABILITADO')
        self.assertEqual(evaluar_condiciones(**self.facts(cargos=cargos, hoy=datetime.date(2026, 11, 1)))['estado'], 'HABILITADO')

    def test_age_and_seniority_boundaries(self):
        self.assertEqual(evaluar_condiciones(**self.facts(nacimiento=datetime.date(2008, 10, 20), fecha_base=datetime.date(2025, 10, 20)))['estado'], 'HABILITADO')
        result = evaluar_condiciones(**self.facts(nacimiento=datetime.date(2008, 10, 21), fecha_base=datetime.date(2025, 10, 21)))
        self.assertEqual([r[0] for r in result['motivos']], ['EDAD', 'ANTIGUEDAD'])
        self.assertTrue(all(r[2].startswith('Espera') for r in result['motivos']))

    def test_missing_data_and_approvals_are_distinct(self):
        result = evaluar_condiciones(**self.facts(activo=False, temporada=True, nacimiento=None, fecha_base=None, aprobacion=False, aval=False))
        self.assertEqual([r[0] for r in result['motivos']], ['SOCIO_INACTIVO', 'TEMPORADA', 'SIN_NACIMIENTO', 'SIN_ALTA', 'PROFESOR', 'AVAL'])

    def test_approval_must_match_current_group_and_membership_period(self):
        socio = SimpleNamespace(numero=1, activo=1, tipo_cuota='ANUAL', fechaAlta=datetime.date(2025, 1, 1), fechaAprobacion=None, cuenta_corriente=None)
        persona = SimpleNamespace(estado_habilitacion='NO_HABILITADO', FechaNacimiento=datetime.date(2000, 1, 1),
            aprobaciones_profesor=Mock(), avales_cd=Mock())
        persona.avales_cd.all.return_value = [SimpleNamespace(activo=True)]
        for numero, fecha in ((2, datetime.date(2025, 2, 1)), (1, datetime.date(2024, 1, 1))):
            persona.aprobaciones_profesor.all.return_value = [SimpleNamespace(numero_socio_momento=numero, fecha=fecha)]
            self.assertEqual(evaluar_habilitacion(persona, socio, datetime.date(2026, 10, 20))['motivos'][0][0], 'PROFESOR')
