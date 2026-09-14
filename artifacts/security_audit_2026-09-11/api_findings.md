# Evidencia de auditoría: API y autorización

Revisión estática y pruebas aisladas del 11 de septiembre de 2026. No se consultaron registros, no se importaron settings ni `.env` reales y no se modificó la aplicación. Las pruebas de `verify_api.py` bloquean todo SQL y simulan la persistencia. La dependencia SimpleJWT no está instalada en el venv: el harness omite autenticación JWT y comprueba los permisos efectivos a partir de la configuración REST_FRAMEWORK extraída con AST. La exposición desde Internet depende del despliegue; los fallos de autorización y de validación están confirmados en el código.

## API-01 — Acceso anónimo a funciones administrativas y datos personales

**Severidad: crítica. OWASP A01:2025 Broken Access Control. Confirmado.**

Ubicaciones (relativas a la raíz):

- `amandaye_backend/amandaye_backend/settings.py:176-180`: solamente se configuran clases de autenticación. Falta una política de permisos; DRF utiliza AllowAny por defecto.
- `amandaye_backend/apps/usuarios/api_views.py:32-42,59-76`: SociosViewSet no exige permisos, consulta todos los socios y permite aprobar y dar bajas. Únicamente MeView tiene IsAuthenticated, en la línea 16.
- `amandaye_backend/apps/cobranzas/views.py:20-26,35-52,76-99`: todos los ViewSets y ambos reportes financieros carecen de permisos. Incluyen creación, edición y eliminación genéricas de conceptos, cargos y pagos, además de anular/aplicar/revertir.
- `amandaye_backend/apps/usuarios/views.py:4-18`: las vistas Django buscar_persona y detalle_persona carecen de login_required/permission_required y no usan DRF. Configurar permisos DRF no las arregla.
- `amandaye_backend/templates/users/detalle_persona.html:11,26,31,36`: expone nombre completo, cédula, número de socio y correo. `Personas.Cedula` es clave primaria (`apps/usuarios/models.py:33`).
- Rutas expuestas por `amandaye_backend/amandaye_backend/urls.py:50-52`, `apps/usuarios/urls.py:5-6`, `apps/usuarios/api_urls.py:6` y `apps/cobranzas/urls.py:10-19`.

Un visitante que pueda acceder al servidor puede consultar `/api/socios/`, `/api/cobranzas/cuentas/` y los reportes, aprobar o dar de baja socios por identificador, crear pagos ficticios o revertir aplicaciones. El flujo de aprobación acepta `generar_cargos_iniciales=false` del cliente (`api_views.py:62`), por lo que puede aprobar sin generar cargos. La búsqueda pública por cédula permite averiguar pertenencia al club y consultar el correo de esa persona. Los permisos declarados en modelos/setup_roles y comprobados en el admin no se aplican automáticamente a estas rutas.

La prueba aislada confirma ocho clases sensibles con AllowAny y que detalle_persona anónimo llega al lookup y render. No se realizó ninguna operación sobre socios reales.

Remediación propuesta: exigir autenticación por defecto y permisos por acción usando los codenames que ya existen en los modelos. Ejemplo reutilizable:

```python
# settings.py (conservar JWTAuthentication)
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

# permissions.py
from rest_framework.permissions import BasePermission

class PermisoDeAccion(BasePermission):
    def has_permission(self, request, view):
        required = getattr(view, "permisos_por_accion", {}).get(
            getattr(view, "action", request.method.lower())
        )
        return bool(
            request.user.is_authenticated
            and required
            and request.user.has_perm(required)
        )

# Dentro de SociosViewSet:
permission_classes = [PermisoDeAccion]
permisos_por_accion = {
    "list": "usuarios.view_socios",
    "retrieve": "usuarios.view_socios",
    "crear_solicitud": "usuarios.add_socios",
    "aprobar": "usuarios.puede_aprobar_socio",
    "dar_baja": "usuarios.puede_dar_baja_socio",
}

# Dentro de PagoViewSet (sin actualización/borrado genérico; API-02):
permission_classes = [PermisoDeAccion]
permisos_por_accion = {
    "list": "cobranzas.view_pago",
    "retrieve": "cobranzas.view_pago",
    "create": "cobranzas.add_pago",
    "aplicar": "cobranzas.puede_aplicar_pago",
}

# Reportes: permission_classes = [PermisoDeAccion]
permisos_por_accion = {
    "get": "cobranzas.puede_ver_resumen_cobranzas",
}
```

Completar el mapa en cada ViewSet: cuentas/view_cuentacorriente; cargos/view_cargo/add_cargo/puede_anular_cargo; aplicaciones/view_aplicacionpago/puede_revertir_aplicacion_pago; conceptos/view_conceptocobro/add_conceptocobro/change_conceptocobro/delete_conceptocobro según las operaciones realmente permitidas. Una acción sin mapa se deniega. Si en el futuro los socios finales acceden a estas APIs, vincular User con socio y filtrar get_queryset por titular además de los permisos administrativos; actualmente no existe ese vínculo.

Para las dos vistas HTML existentes, aplicar a cada función:

```python
from django.contrib.auth.decorators import login_required, permission_required

@login_required
@permission_required("usuarios.view_personas", raise_exception=True)
def detalle_persona(request, pk):
    persona = get_object_or_404(Personas, pk=pk)
    return render(request, "users/detalle_persona.html", {"persona": persona})

# Los mismos dos decoradores en buscar_persona.
```

Si no existe una operación autorizada de exoneración al aprobar, eliminar el parámetro de cliente y llamar `aprobar_socio(socio, generar_cargos_iniciales=True)`. Si sí existe, tratarla como acción separada con permiso y motivo obligatorios.

## API-02 — Cambios directos de contabilidad evitan las reglas del servicio

**Severidad: alta. OWASP A06:2025 Insecure Design. Confirmado.**

Ubicaciones:

- `amandaye_backend/apps/cobranzas/serializers.py:14-29`: Cargo y Pago usan fields='__all__'; estado, cuenta, importe/importe_total y registrado_por son escribibles.
- `amandaye_backend/apps/cobranzas/views.py:35-37,50-52`: ModelViewSet hereda update, partial_update y destroy sin restricciones de negocio.
- `amandaye_backend/apps/cobranzas/services/cargos.py:22-24`: el servicio prohíbe anular cargos con aplicaciones, pero PATCH evita este servicio.
- `amandaye_backend/apps/cobranzas/models.py:87-90,112,143`: estado ANULADO produce saldo 0, el actor del pago es un FK editable, y borrar Pago elimina sus AplicacionPago por cascada.
- `amandaye_backend/apps/cobranzas/views.py:68` y `services/pagos.py:24,42`: aplicar por API no pasa usuario, por lo que la aplicación queda sin actor.

Ejemplo: PATCH `/api/cobranzas/cargos/{id}/` con `{"estado":"ANULADO"}` pone a cero el saldo mostrado incluso si el cargo tiene pagos aplicados. Cambiar un pago ya aplicado a otra cuenta o reducir su importe por debajo de lo aplicado rompe invariantes que aplicar_pago sólo revisó al crear la aplicación. El cliente puede atribuir un pago a otro usuario mediante registrado_por. DELETE de pago elimina las aplicaciones sin pasar por la reversión, que conserva historia y recalcula estados. Estos problemas persisten para usuarios con permisos genéricos de modificación aunque se corrija API-01.

La prueba aislada verificó que CargoSerializer acepta ANULADO y alcanza save() directamente, sin servicio de anulación, y que los campos sensibles son escribibles. No se guardó nada.

Remediación propuesta: operaciones transaccionales explícitas; eliminar update/destroy de movimientos contables y fijar el actor en servidor. Mantener los permisos por acción de API-01 y conservar los métodos de acción existentes tras corregir sus servicios:

```python
from decimal import Decimal
from rest_framework import mixins, serializers, viewsets
from .services.cargos import crear_cargo
from .services.pagos import registrar_pago

class CargoSerializer(serializers.ModelSerializer):
    importe = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )

    class Meta:
        model = Cargo
        fields = (
            "id", "cuenta", "concepto", "periodo", "fecha_emision",
            "fecha_vencimiento", "importe", "estado", "observaciones",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "estado", "created_at", "updated_at")

    def create(self, validated_data):
        return crear_cargo(**validated_data)

class PagoSerializer(serializers.ModelSerializer):
    importe_total = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )

    class Meta:
        model = Pago
        fields = (
            "id", "cuenta", "fecha_pago", "importe_total", "medio_pago",
            "referencia", "observaciones", "registrado_por",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "registrado_por", "created_at", "updated_at")

    def create(self, validated_data):
        actor = validated_data.pop("registrado_por")
        return registrar_pago(**validated_data, usuario=actor)

class PagoViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                  mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Pago.objects.all()
    serializer_class = PagoSerializer
    permission_classes = [PermisoDeAccion]
    permisos_por_accion = {
        "list": "cobranzas.view_pago",
        "retrieve": "cobranzas.view_pago",
        "create": "cobranzas.add_pago",
        "aplicar": "cobranzas.puede_aplicar_pago",
    }

    def perform_create(self, serializer):
        serializer.save(registrado_por=self.request.user)

    # Conservar la acción aplicar, cambiando la llamada al servicio:
    # aplicar_pago(pago, cargo, importe_dec, usuario=request.user)

# CargoViewSet: las mismas bases Create/List/Retrieve/GenericViewSet,
# su queryset/serializer y mapa de permisos; conservar la acción anular.
# Sin UpdateModelMixin ni DestroyModelMixin en movimientos contables.
```

Los fragmentos son una propuesta de remediación y necesitan integrarse con los campos derivados usados en la UI. Para corregir movimientos históricos, diseñar una operación de reversión/ajuste con permiso, motivo, identidad del operador y conservación de historia; no reinstalar PUT/PATCH/DELETE genéricos. El endurecimiento de concurrencia de los servicios es un hallazgo separado.

## API-03 — Detalles internos de excepciones devueltos al cliente

**Severidad: media, impacto dependiente del error producido. OWASP A10:2025 Mishandling of Exceptional Conditions. Confirmado el mecanismo; contenido sensible no demostrado.**

Ubicaciones: `amandaye_backend/apps/cobranzas/views.py:65-74,80-87`.

Las acciones aplicar y revertir capturan cualquier Exception y devuelven str(e) con estado 400. Errores inesperados del ORM, almacenamiento o código interno pueden revelar tablas, consultas, nombres de campos o detalles técnicos. También quedan confundidos con errores de entrada y no se registran explícitamente para investigación. No se afirma que todas las excepciones contengan secretos. La prueba aislada inyectó una RuntimeError sintética y confirmó que su texto aparece íntegro en la respuesta.

Remediación propuesta: validar la entrada antes del servicio y distinguir errores esperados de fallas internas, manteniendo el detalle inesperado en logs restringidos:

```python
import logging
from decimal import Decimal
from rest_framework import serializers, status
from rest_framework.response import Response
from django.core.exceptions import ValidationError as DomainValidationError

logger = logging.getLogger(__name__)

class AplicarPagoInput(serializers.Serializer):
    cargo_id = serializers.IntegerField(min_value=1)
    importe = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )

# Dentro de la acción aplicar, después de los permisos:
entrada = AplicarPagoInput(data=request.data)
entrada.is_valid(raise_exception=True)
pago = self.get_object()
cargo = get_object_or_404(Cargo, pk=entrada.validated_data["cargo_id"])
try:
    aplicacion = aplicar_pago(
        pago, cargo, entrada.validated_data["importe"], usuario=request.user
    )
except DomainValidationError as exc:
    return Response({"error": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
except Exception:
    logger.exception("Fallo al aplicar pago", extra={"pago_id": pago.pk})
    return Response(
        {"error": "No se pudo completar la operación."},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
return Response(AplicacionPagoSerializer(aplicacion).data, status=status.HTTP_201_CREATED)
```

Aplicar el mismo patrón a revertir. Configurar un destino de logs restringido y no registrar tokens, payloads completos ni datos personales. Los fallos esperados de dominio sólo deben contener mensajes pensados para el usuario.

## Notas de descarte

- No se observó SQL concatenado en las vistas revisadas: búsquedas y filtros usan ORM. No etiquetar como Injection por recibir una cédula o filtros desde/hasta.
- PersonasSerializer fields='__all__' no demuestra por sí solo asignación masiva: no tiene un endpoint de escritura conectado. SociosViewSet es ReadOnlyModelViewSet y la solicitud usa un serializer de lista explícita; los hallazgos de campos escribibles corresponden a Cargo/Pago.
- Alerta meteorológica devuelve constantes y no demuestra filtración sensible. Brevet/horarios no tienen endpoints activos de negocio en urls raíz.
- Hay controles de permisos en admin, pero el acceso a sus pantallas no protege las rutas API ni las vistas HTML paralelas.
