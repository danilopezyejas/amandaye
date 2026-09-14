"""Regression coverage using a disposable database; never load production data."""
import datetime
import io
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase
from rest_framework.test import APITestCase

from apps.cobranzas.models import AplicacionPago, Cargo, ConceptoCobro, CuentaCorriente, Pago
from apps.usuarios.models import Personas, Socios
from apps.usuarios.permissions import ClubPermissions


class PermissionPolicyTests(SimpleTestCase):
    def test_unknown_action_denied_even_to_superuser(self):
        user = SimpleNamespace(is_authenticated=True, is_active=True, has_perm=lambda perm: True)
        request = SimpleNamespace(user=user, method="POST")
        view = SimpleNamespace(action="new_operation", permission_map={"list": "usuarios.view_socios"})
        self.assertFalse(ClubPermissions().has_permission(request, view))

    def test_view_without_permission_map_is_denied(self):
        user = SimpleNamespace(is_authenticated=True, is_active=True, has_perm=lambda perm: True)
        self.assertFalse(ClubPermissions().has_permission(
            SimpleNamespace(user=user, method="GET"), SimpleNamespace(),
        ))


class APISecurityTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("setup_roles", stdout=io.StringIO())
        cls.roles = {}
        for name in ("Secretaria", "Tesoreria", "Comision Directiva", "Administrador"):
            user = User.objects.create_user(username=name, password="test-only-password", is_staff=True)
            user.groups.add(Group.objects.get(name=name))
            cls.roles[name] = user
        cls.outsider = User.objects.create_user(username="sin_rol", password="test-only-password")
        cls.socio = Socios.objects.create(numero=9100, activo=1, cedulaTitular="91000001")
        cls.persona = Personas.objects.create(
            Cedula="91000001", numeroSocio=cls.socio.pk, PrimerNombre="Persona",
            PrimerApellido="Sintética", FechaNacimiento=datetime.date(1990, 1, 1),
        )
        cls.cuenta = CuentaCorriente.objects.create(socio_titular=cls.socio, tipo_cuenta="INDIVIDUAL")
        cls.concepto = ConceptoCobro.objects.create(codigo="MATRICULA", nombre="Matrícula", importe_por_defecto=100)
        ConceptoCobro.objects.create(codigo="CUOTA_INDIVIDUAL", nombre="Cuota", importe_por_defecto=100)
        cls.cargo = Cargo.objects.create(
            cuenta=cls.cuenta, concepto=cls.concepto, periodo="2026-09", importe=Decimal("100.00"),
            fecha_emision=datetime.date.today(), fecha_vencimiento=datetime.date.today(),
        )
        cls.pago = Pago.objects.create(
            cuenta=cls.cuenta, fecha_pago=datetime.date.today(), importe_total=Decimal("100.00"),
            medio_pago="EFECTIVO", registrado_por=cls.roles["Secretaria"],
        )

    def setUp(self):
        cache.clear()

    def authenticate(self, role):
        self.client.force_authenticate(user=self.roles[role])

    def valid_payment(self, **extra):
        return {
            "cuenta": self.cuenta.pk, "fecha_pago": "2026-09-11",
            "importe_total": "50.00", "medio_pago": "EFECTIVO", **extra,
        }

    def valid_registration(self, cedula="92000001"):
        return {"datos_titular": {
            "Cedula": cedula, "PrimerNombre": "Nombre", "PrimerApellido": "Sintético",
            "FechaNacimiento": "1990-01-01", "Celular": "099000000", "Direccion": "Dirección de prueba",
        }}

    def test_every_internal_api_rejects_anonymous_and_account_without_role(self):
        routes = (
            "/api/socios/", f"/api/socios/{self.socio.pk}/",
            "/api/cobranzas/conceptos-cobro/", "/api/cobranzas/cuentas/",
            f"/api/cobranzas/cuentas/{self.cuenta.pk}/estado-cuenta/",
            "/api/cobranzas/cargos/", "/api/cobranzas/pagos/", "/api/cobranzas/aplicaciones/",
            "/api/cobranzas/reportes/cuentas-con-deuda/", "/api/cobranzas/reportes/recaudacion/",
        )
        for user in (None, self.outsider):
            self.client.force_authenticate(user=user)
            for route in routes:
                with self.subTest(user=bool(user), route=route):
                    self.assertIn(self.client.get(route).status_code, (401, 403))

    def test_role_matrix_for_reads_and_reports(self):
        routes = {
            "/api/socios/": {"Secretaria", "Tesoreria", "Comision Directiva", "Administrador"},
            "/api/cobranzas/cuentas/": {"Secretaria", "Tesoreria", "Comision Directiva", "Administrador"},
            "/api/cobranzas/cargos/": {"Secretaria", "Tesoreria", "Comision Directiva", "Administrador"},
            "/api/cobranzas/pagos/": {"Secretaria", "Tesoreria", "Comision Directiva", "Administrador"},
            "/api/cobranzas/aplicaciones/": {"Secretaria", "Tesoreria", "Comision Directiva", "Administrador"},
            "/api/cobranzas/conceptos-cobro/": {"Tesoreria", "Comision Directiva", "Administrador"},
            "/api/cobranzas/reportes/cuentas-con-deuda/": {"Tesoreria", "Comision Directiva", "Administrador"},
            "/api/cobranzas/reportes/recaudacion/": {"Tesoreria", "Comision Directiva", "Administrador"},
        }
        for role in self.roles:
            self.authenticate(role)
            for route, allowed in routes.items():
                with self.subTest(role=role, route=route):
                    self.assertEqual(self.client.get(route).status_code, 200 if role in allowed else 403)

    def test_inactive_operator_denied(self):
        user = self.roles["Administrador"]
        user.is_active = False
        user.save(update_fields=["is_active"])
        self.client.force_authenticate(user=user)
        self.assertEqual(self.client.get("/api/cobranzas/cuentas/").status_code, 403)

    def test_unauthorized_custom_actions_do_not_mutate_data(self):
        routes = {
            f"/api/socios/{self.socio.pk}/aprobar/": {},
            f"/api/socios/{self.socio.pk}/dar-baja/": {"motivo": "Prueba"},
            f"/api/cobranzas/cargos/{self.cargo.pk}/anular/": {"observaciones": "Prueba"},
            f"/api/cobranzas/pagos/{self.pago.pk}/aplicar/": {"cargo_id": self.cargo.pk, "importe": "10.00"},
            "/api/cobranzas/aplicaciones/9999/revertir/": {"motivo": "Prueba"},
        }
        for user in (None, self.outsider):
            self.client.force_authenticate(user=user)
            for route, data in routes.items():
                with self.subTest(user=bool(user), route=route):
                    self.assertIn(self.client.post(route, data, format="json").status_code, (401, 403))
        self.cargo.refresh_from_db()
        self.socio.refresh_from_db()
        self.assertEqual(self.cargo.estado, "PENDIENTE")
        self.assertEqual(self.socio.activo, 1)
        self.assertEqual(AplicacionPago.objects.count(), 0)

    def test_secretaria_cannot_approve_cancel_or_revert(self):
        self.authenticate("Secretaria")
        for route in (
            f"/api/socios/{self.socio.pk}/aprobar/",
            f"/api/socios/{self.socio.pk}/dar-baja/",
            f"/api/cobranzas/cargos/{self.cargo.pk}/anular/",
            "/api/cobranzas/aplicaciones/9999/revertir/",
        ):
            with self.subTest(route=route):
                self.assertEqual(self.client.post(route, {}, format="json").status_code, 403)

    def test_generic_financial_edits_and_deletes_are_removed_for_admin(self):
        self.authenticate("Administrador")
        for resource, pk in (("cargos", self.cargo.pk), ("pagos", self.pago.pk)):
            for method in (self.client.put, self.client.patch, self.client.delete):
                with self.subTest(resource=resource, method=method.__name__):
                    response = method(f"/api/cobranzas/{resource}/{pk}/", {
                        "estado": "ANULADO", "importe": "0.01", "importe_total": "0.01",
                    }, format="json")
                    self.assertIn(response.status_code, (403, 405))
        self.cargo.refresh_from_db()
        self.pago.refresh_from_db()
        self.assertEqual(self.cargo.estado, "PENDIENTE")
        self.assertEqual(self.cargo.importe, Decimal("100.00"))
        self.assertEqual(self.pago.importe_total, Decimal("100.00"))

    def test_payment_actor_comes_from_authenticated_operator(self):
        self.authenticate("Secretaria")
        response = self.client.post("/api/cobranzas/pagos/", self.valid_payment(
            registrado_por=self.roles["Administrador"].pk,
        ), format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Pago.objects.get(pk=response.data["id"]).registrado_por, self.roles["Secretaria"])

    def test_role_matrix_for_manual_creation(self):
        for index, role in enumerate(self.roles):
            self.authenticate(role)
            response = self.client.post("/api/cobranzas/pagos/", self.valid_payment(), format="json")
            with self.subTest(role=role, resource="pagos"):
                self.assertEqual(response.status_code, 403 if role == "Comision Directiva" else 201, response.data)
            response = self.client.post("/api/cobranzas/conceptos-cobro/", {
                "codigo": f"TEST-{index}", "nombre": "Concepto sintético", "importe_por_defecto": "20.00",
            }, format="json")
            with self.subTest(role=role, resource="conceptos"):
                self.assertEqual(response.status_code, 201 if role in {"Tesoreria", "Administrador"} else 403, response.data)
            response = self.client.post("/api/cobranzas/cargos/", {
                "cuenta": self.cuenta.pk, "concepto": self.concepto.pk, "periodo": "2026-10",
                "fecha_emision": "2026-10-01", "fecha_vencimiento": "2026-10-10", "importe": "10.00",
            }, format="json")
            with self.subTest(role=role, resource="cargos"):
                self.assertEqual(response.status_code, 201 if role == "Administrador" else 403, response.data)

    def test_invalid_amounts_rejected_before_persistence(self):
        self.authenticate("Secretaria")
        for amount in ("0", "-1", "NaN", "Infinity", "1.001", "1000000000"):
            with self.subTest(amount=amount):
                self.assertEqual(self.client.post("/api/cobranzas/pagos/", self.valid_payment(
                    importe_total=amount,
                ), format="json").status_code, 400)
                self.assertEqual(self.client.post(f"/api/cobranzas/pagos/{self.pago.pk}/aplicar/", {
                    "cargo_id": self.cargo.pk, "importe": amount,
                }, format="json").status_code, 400)
        self.assertEqual(Pago.objects.count(), 1)
        self.assertEqual(AplicacionPago.objects.count(), 0)

    def test_cargo_creation_forces_pending_state_and_actor(self):
        self.authenticate("Administrador")
        response = self.client.post("/api/cobranzas/cargos/", {
            "cuenta": self.cuenta.pk, "concepto": self.concepto.pk, "periodo": "2026-10",
            "fecha_emision": "2026-10-01", "fecha_vencimiento": "2026-10-10",
            "importe": "10.00", "estado": "ANULADO", "registrado_por": self.outsider.pk,
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        cargo = Cargo.objects.get(pk=response.data["id"])
        self.assertEqual(cargo.estado, "PENDIENTE")
        self.assertEqual(cargo.registrado_por, self.roles["Administrador"])

    def test_apply_and_reverse_preserve_history_and_attribute_actors(self):
        self.authenticate("Secretaria")
        response = self.client.post(f"/api/cobranzas/pagos/{self.pago.pk}/aplicar/", {
            "cargo_id": self.cargo.pk, "importe": "40.00",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        aplicacion = AplicacionPago.objects.get(pk=response.data["id"])
        self.assertEqual(aplicacion.registrado_por, self.roles["Secretaria"])
        self.authenticate("Tesoreria")
        response = self.client.post(f"/api/cobranzas/aplicaciones/{aplicacion.pk}/revertir/", {
            "motivo": "Corrección documentada de prueba",
        }, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        aplicacion.refresh_from_db()
        self.assertEqual(aplicacion.estado, "REVERTIDA")
        self.assertEqual(aplicacion.revertido_por, self.roles["Tesoreria"])
        self.assertEqual(AplicacionPago.objects.count(), 1)
        self.cargo.refresh_from_db()
        self.assertEqual(self.cargo.saldo_pendiente, Decimal("100.00"))

    def test_annulment_requires_reversing_active_applications(self):
        self.authenticate("Tesoreria")
        response = self.client.post(f"/api/cobranzas/pagos/{self.pago.pk}/aplicar/", {
            "cargo_id": self.cargo.pk, "importe": "40.00",
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        application_id = response.data["id"]
        route = f"/api/cobranzas/cargos/{self.cargo.pk}/anular/"
        response = self.client.post(route, {"observaciones": "Corrección documentada"}, format="json")
        self.assertEqual(response.status_code, 400, response.data)
        self.cargo.refresh_from_db()
        self.assertEqual(self.cargo.estado, "PARCIAL")
        self.client.post(f"/api/cobranzas/aplicaciones/{application_id}/revertir/", {
            "motivo": "Corrección documentada",
        }, format="json")
        response = self.client.post(route, {"observaciones": "Corrección documentada"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.cargo.refresh_from_db()
        self.assertEqual(self.cargo.estado, "ANULADO")
        self.assertEqual(self.cargo.anulado_por, self.roles["Tesoreria"])

    def test_approval_always_generates_initial_charges(self):
        socio = Socios.objects.create(numero=9101, activo=2, cedulaTitular="91000002")
        self.authenticate("Comision Directiva")
        response = self.client.post(f"/api/socios/{socio.pk}/aprobar/", {
            "generar_cargos_iniciales": False,
        }, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        socio.refresh_from_db()
        self.assertEqual(socio.activo, 1)
        self.assertEqual(Cargo.objects.filter(cuenta__socio_titular=socio).count(), 2)

    def test_public_registration_is_minimal_pending_and_duplicate_safe(self):
        data = self.valid_registration()
        created = self.client.post("/api/socios/solicitudes/", data, format="json")
        repeated = self.client.post("/api/socios/solicitudes/", data, format="json")
        self.assertEqual(created.status_code, 202, created.data)
        self.assertEqual((repeated.status_code, repeated.data), (created.status_code, created.data))
        self.assertEqual(set(created.data), {"mensaje"})
        socio = Socios.objects.get(cedulaTitular=data["datos_titular"]["Cedula"])
        self.assertEqual(socio.activo, 2)
        self.assertIsNone(socio.fechaAlta)
        self.assertEqual(socio.tipo_cuota, "ANUAL")
        self.assertFalse(CuentaCorriente.objects.filter(socio_titular=socio).exists())

    def test_public_registration_rejects_state_and_oversized_family(self):
        for field in ("activo", "numero", "tipo_cuota", "generar_cargos_iniciales"):
            with self.subTest(field=field):
                payload = self.valid_registration()
                payload[field] = "forged"
                self.assertEqual(self.client.post("/api/socios/solicitudes/", payload, format="json").status_code, 400)
        payload = self.valid_registration()
        payload["datos_familiares"] = [payload["datos_titular"]] * 4
        self.assertEqual(self.client.post("/api/socios/solicitudes/", payload, format="json").status_code, 400)
        self.assertEqual(Socios.objects.count(), 1)

    def test_public_registration_throttles_after_five_requests(self):
        for _ in range(5):
            response = self.client.post("/api/socios/solicitudes/", self.valid_registration(), format="json")
            self.assertEqual(response.status_code, 202, response.data)
        response = self.client.post("/api/socios/solicitudes/", self.valid_registration(), format="json")
        self.assertEqual(response.status_code, 429)

    def test_public_throttle_cannot_be_bypassed_with_forged_forwarded_header(self):
        for index in range(5):
            response = self.client.post(
                "/api/socios/solicitudes/", self.valid_registration(), format="json",
                HTTP_X_FORWARDED_FOR=f"198.51.100.{index + 1}",
            )
            self.assertEqual(response.status_code, 202, response.data)
        response = self.client.post(
            "/api/socios/solicitudes/", self.valid_registration(), format="json",
            HTTP_X_FORWARDED_FOR="198.51.100.99",
        )
        self.assertEqual(response.status_code, 429)

    def test_invalid_family_does_not_reveal_whether_titular_exists(self):
        responses = []
        for cedula in (self.persona.pk, "92000003"):
            payload = self.valid_registration(cedula)
            payload["datos_familiares"] = [{
                "Cedula": "92000004", "PrimerNombre": "Familiar", "PrimerApellido": "Sintético",
                "FechaNacimiento": "1990-01-01", "relacionTitular": "HIJO",
            }]
            response = self.client.post("/api/socios/solicitudes/", payload, format="json")
            responses.append((response.status_code, response.data))
        self.assertEqual(responses[0], responses[1])
        self.assertEqual(responses[0][0], 400)

    def test_person_html_views_require_permissions(self):
        for route in ("/api/usuarios/buscar/?cedula=91000001", "/api/usuarios/detalle/91000001/"):
            self.client.logout()
            self.assertEqual(self.client.get(route).status_code, 302)
            self.client.force_login(self.outsider, backend="django.contrib.auth.backends.ModelBackend")
            self.assertEqual(self.client.get(route).status_code, 403)
            self.client.force_login(self.roles["Secretaria"], backend="django.contrib.auth.backends.ModelBackend")
            self.assertIn(self.client.get(route).status_code, (200, 302))

    def test_unexpected_failure_returns_only_public_message_and_logs_safe_event(self):
        self.authenticate("Secretaria")
        secret = "SYNTHETIC_PRIVATE_SQL_PASSWORD"
        with patch("apps.cobranzas.views.aplicar_pago", side_effect=RuntimeError(secret)):
            with self.assertLogs("amandaye.security", level="ERROR") as logs:
                response = self.client.post(f"/api/cobranzas/pagos/{self.pago.pk}/aplicar/", {
                    "cargo_id": self.cargo.pk, "importe": "10.00",
                }, format="json")
        self.assertEqual(response.status_code, 500)
        self.assertEqual(set(response.data), {"error", "id"})
        self.assertNotIn(secret, str(response.data))
        self.assertNotIn(secret, " ".join(logs.output))
        self.assertIn(response.data["id"], " ".join(logs.output))

    def test_unexpected_reversal_failure_is_not_disclosed(self):
        application = AplicacionPago.objects.create(pago=self.pago, cargo=self.cargo, importe_aplicado="10.00")
        self.authenticate("Tesoreria")
        secret = "SYNTHETIC_DATABASE_DETAILS"
        with patch("apps.cobranzas.views.revertir_aplicacion", side_effect=RuntimeError(secret)):
            with self.assertLogs("amandaye.security", level="ERROR") as logs:
                response = self.client.post(f"/api/cobranzas/aplicaciones/{application.pk}/revertir/", {
                    "motivo": "Corrección de prueba",
                }, format="json")
        self.assertEqual(response.status_code, 500)
        self.assertNotIn(secret, str(response.data))
        self.assertNotIn(secret, " ".join(logs.output))
        application.refresh_from_db()
        self.assertEqual(application.estado, "ACTIVA")

    def test_malformed_report_dates_are_validation_errors(self):
        self.authenticate("Tesoreria")
        for query in ("desde=not-a-date", "desde=2026-10-01&hasta=2026-09-01"):
            self.assertEqual(self.client.get(f"/api/cobranzas/reportes/recaudacion/?{query}").status_code, 400)
