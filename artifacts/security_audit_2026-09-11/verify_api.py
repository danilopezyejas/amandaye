"""Isolated security checks: no project settings/.env or real database.

Uses Django/DRF from the existing venv and an available Python interpreter.
The project's JWT package is absent locally; authentication is disabled in
this harness only. Permission defaults are copied from the settings AST.
All attempted SQL is blocked, and model persistence/view dependencies are
mocked. The checks demonstrate code behavior, not a deployed-server exploit.
"""
import ast
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "venv" / "Lib" / "site-packages"))
sys.path.insert(0, str(ROOT / "amandaye_backend"))

tree = ast.parse((ROOT / "amandaye_backend/amandaye_backend/settings.py").read_text(encoding="utf-8"))
drf_config = next(
    ast.literal_eval(node.value)
    for node in tree.body
    if isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Name) and target.id == "REST_FRAMEWORK" for target in node.targets)
)
assert "DEFAULT_PERMISSION_CLASSES" not in drf_config
drf_config["DEFAULT_AUTHENTICATION_CLASSES"] = []

from django.conf import settings
settings.configure(
    SECRET_KEY="synthetic-audit-key-not-used-for-tokens",
    INSTALLED_APPS=["django.contrib.auth", "django.contrib.contenttypes", "apps.usuarios", "apps.cobranzas"],
    DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
    REST_FRAMEWORK=drf_config,
    USE_TZ=True,
    DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
)
import django
django.setup()

from django.db import connection
from django.http import HttpResponse
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from apps.usuarios.api_views import SociosViewSet, MeView
from apps.usuarios import views as person_views
from apps.cobranzas import views as financial_views
from apps.cobranzas.models import Cargo
from apps.cobranzas.serializers import CargoSerializer, PagoSerializer


def reject_sql(execute, sql, params, many, context):
    raise AssertionError("This isolated audit must never execute SQL")


with connection.execute_wrapper(reject_sql):
    request = SimpleNamespace(user=AnonymousUser(), method="GET")
    affected_views = [
        SociosViewSet, financial_views.ConceptoCobroViewSet,
        financial_views.CuentaCorrienteViewSet, financial_views.CargoViewSet,
        financial_views.PagoViewSet, financial_views.AplicacionPagoViewSet,
        financial_views.ReporteCuentasConDeudaView,
        financial_views.ReporteRecaudacionView,
    ]
    for view_class in affected_views:
        view = view_class()
        permissions = view.get_permissions()
        assert all(permission.has_permission(request, view) for permission in permissions)
        assert [type(permission).__name__ for permission in permissions] == ["AllowAny"]
    assert not all(permission.has_permission(request, MeView()) for permission in MeView().get_permissions())
    print("PASS: 8 sensitive API view classes inherit AllowAny; /api/me uses IsAuthenticated")

    cargo = Cargo(id=1, estado=Cargo.Estado.PENDIENTE)
    serializer = CargoSerializer(cargo, data={"estado": "ANULADO"}, partial=True)
    assert serializer.is_valid(), serializer.errors
    with patch.object(Cargo, "save", autospec=True) as persistence:
        serializer.save()
    assert cargo.estado == Cargo.Estado.ANULADO
    persistence.assert_called_once()
    print("PASS: generic serializer update accepts ANULADO and reaches model save without cancellation service")

    cargo_fields = CargoSerializer().fields
    payment_fields = PagoSerializer().fields
    assert all(not cargo_fields[name].read_only for name in ("cuenta", "importe", "estado"))
    assert all(not payment_fields[name].read_only for name in ("cuenta", "importe_total", "registrado_por"))
    assert callable(financial_views.PagoViewSet.destroy)
    print("PASS: financial relation/amount/state/actor fields are writable; payments expose generic destroy")

    anonymous_get = RequestFactory().get("/api/usuarios/detalle/11111111/")
    anonymous_get.user = AnonymousUser()
    with patch.object(person_views, "get_object_or_404", return_value=SimpleNamespace()) as lookup, patch.object(person_views, "render", return_value=HttpResponse("synthetic")):
        response = person_views.detalle_persona(anonymous_get, 11111111)
    assert response.status_code == 200
    lookup.assert_called_once()
    print("PASS: anonymous Django person-detail view reaches lookup and template rendering")

    view = financial_views.PagoViewSet()
    with patch.object(view, "get_object", return_value=SimpleNamespace()), patch.object(financial_views, "get_object_or_404", return_value=SimpleNamespace()), patch.object(financial_views, "aplicar_pago", side_effect=RuntimeError("AUDIT_SYNTHETIC_INTERNAL_DETAIL")):
        response = view.aplicar(SimpleNamespace(data={"cargo_id": 1, "importe": "1.00"}))
    assert response.data == {"error": "AUDIT_SYNTHETIC_INTERNAL_DETAIL"}
    print("PASS: unexpected exception detail is copied verbatim to the API response")

print("Completed without SQL, project settings imports, .env reads, or actual model persistence.")
