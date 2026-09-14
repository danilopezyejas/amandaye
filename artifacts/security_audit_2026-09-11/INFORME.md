**Auditoría de seguridad de socios_amandaye — 11/09/2026**

> Este documento conserva el diagnóstico y las ubicaciones del código anterior a los cambios. Las correcciones implementadas y su validación se registran en [REMEDIACION.md](REMEDIACION.md).

La prioridad es cerrar el acceso anónimo a socios y cobranzas. La aplicación tiene autenticación JWT configurada, pero ocho clases de API heredan permisos que permiten el acceso sin autenticación. Además, existen rutas alternativas que eluden las reglas de aprobación y de integridad de pagos.

Se revisaron backend Django/DRF, administración, servicios, plantillas, frontend Vue, dependencias y Docker. Clasificación: [OWASP Top 10:2025](https://top10.owasp.org/2025/0x00_2025-Introduction/). Las severidades expresan prioridad contextual, no puntuaciones CVSS calculadas. Se indican las condiciones de despliegue cuando afectan al riesgo.

El código de aplicación no se modificó. Los fragmentos siguientes son propuestas de sustitución o inserción; se deben integrar conjuntamente y validar antes de desplegar. Los ejemplos de permisos conservan un modelo de acceso interno por roles: tener una cuenta de usuario no concede acceso automático a todos los socios. Si se desea autoservicio para socios, hace falta modelar también la relación entre usuario y persona y filtrar por propietario.

| ID | Prioridad | Hallazgo | OWASP 2025 |
|---|---|---|---|
| H01 | Crítica | API y consultas de personas sin autorización | A01 |
| H02 | Alta | Edición y borrado genéricos alteran la contabilidad | A06 |
| H03 | Alta | Secretaría puede cambiar estados reservados a Directiva | A01 |
| H04 | Crítica si se usa el valor por defecto | Clave de firma JWT incluida en código | A04 |
| H05 | Crítica si se inicializa y expone así | MySQL con root sin contraseña y puerto publicado | A02 |
| H06 | Alta si se publica esta configuración | DEBUG y servidores de desarrollo expuestos | A02; A04 para transporte |
| H07 | Alta si Vite es alcanzable | Vite vulnerable permite lectura de archivos | A03 |
| H08 | Media; actualización prioritaria | Backend fijado a componentes vulnerables o sin soporte | A03 |
| H09 | Alta | Aplicaciones de pagos concurrentes exceden el saldo | A06 |
| H10 | Media; depende de controles externos | Login sin limitación de intentos | A07 |
| H11 | Media; exposición condicional | Datos de personas y configuración versionados | A01 |
| H12 | Baja | Redirección a destinos externos tomados de Referer | A01 |
| H13 | Media | Excepciones reveladas o ignoradas en operaciones financieras | A10 |

**H01. API y consultas de personas sin autorización**

**1. Vulnerabilidad y categoría.** A01:2025 — Broken Access Control. Confirmada en código y mediante pruebas aisladas. Prioridad crítica por combinar lectura de información personal con modificaciones financieras y de socios.

**2. Ubicación exacta.**

- [settings.py:176](C:/Users/Danilo/socios_amandaye/amandaye_backend/amandaye_backend/settings.py:176), líneas 176–180: sólo configura autenticación; omite `DEFAULT_PERMISSION_CLASSES`.
- [usuarios/api_views.py:32](C:/Users/Danilo/socios_amandaye/amandaye_backend/apps/usuarios/api_views.py:32), líneas 32–79: listado, solicitudes, aprobación y baja sin permisos.
- [cobranzas/views.py:20](C:/Users/Danilo/socios_amandaye/amandaye_backend/apps/cobranzas/views.py:20), clases en líneas 20, 24, 35, 50, 76, 89 y 98: conceptos, cuentas, cargos, pagos, aplicaciones y reportes sin permisos.
- [usuarios/views.py:4](C:/Users/Danilo/socios_amandaye/amandaye_backend/apps/usuarios/views.py:4), líneas 4–18: búsqueda y detalle de personas sin protección. Rutas en [usuarios/urls.py:5](C:/Users/Danilo/socios_amandaye/amandaye_backend/apps/usuarios/urls.py:5).

**3. Riesgo y escenario.** Una persona que alcance el backend puede consultar `/api/socios/`, `/api/cobranzas/cuentas/` y reportes; también puede invocar aprobación, baja, creación de pagos y modificación de cargos. Con una cédula puede consultar `/api/usuarios/detalle/<cedula>/`, que muestra nombre, correo y número de socio. Los servicios realizan validaciones de negocio, pero no verifican quién los llama. DRF usa `AllowAny` cuando no se establece otra política. `/api/me/` sí está protegido; eso no protege las demás rutas. [Documentación de permisos de DRF](https://www.django-rest-framework.org/api-guide/permissions/).

**4. Código corregido.** Crear `apps/usuarios/permissions.py` con una política que deniegue operaciones desconocidas y compruebe los permisos existentes:

```python
from rest_framework.permissions import BasePermission


class ClubPermissions(BasePermission):
    custom = {
        "aprobar": "usuarios.puede_aprobar_socio",
        "dar_baja": "usuarios.puede_dar_baja_socio",
        "crear_solicitud": "usuarios.add_socios",
        "estado_cuenta": "cobranzas.view_cuentacorriente",
        "anular": "cobranzas.puede_anular_cargo",
        "aplicar": "cobranzas.puede_aplicar_pago",
        "revertir": "cobranzas.puede_revertir_aplicacion_pago",
    }
    operations = {
        "list": "view", "retrieve": "view", "create": "add",
        "update": "change", "partial_update": "change", "destroy": "delete",
    }

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or not user.is_active:
            return False
        action = getattr(view, "action", None)
        required = self.custom.get(action)
        if required is None and action in self.operations:
            model = getattr(getattr(view, "queryset", None), "model", None)
            if model is not None:
                meta = model._meta
                required = (
                    f"{meta.app_label}."
                    f"{self.operations[action]}_{meta.model_name}"
                )
        if required is None and action is None and request.method == "GET":
            required = getattr(view, "required_permission", None)
        return bool(required and user.has_perm(required))
```

Insertar en la configuración y en las dos clases de reportes:

```python
# settings.py: conservar DEFAULT_AUTHENTICATION_CLASSES existente.
REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] = (
    "apps.usuarios.permissions.ClubPermissions",
)

# Dentro de ReporteCuentasConDeudaView y ReporteRecaudacionView:
required_permission = "cobranzas.puede_ver_resumen_cobranzas"
```

Las vistas Django requieren su propia protección. Sustituir `apps/usuarios/urls.py` por:

```python
from django.contrib.auth.decorators import permission_required
from django.urls import path
from . import views

protect = permission_required("usuarios.view_personas", raise_exception=True)
urlpatterns = [
    path("buscar/", protect(views.buscar_persona), name="buscar_persona"),
    path("detalle/<int:pk>/", protect(views.detalle_persona), name="detalle_persona"),
]
```

Una inscripción pública, si forma parte del producto, debe ser una excepción explícita limitada a crear solicitudes pendientes, con respuesta mínima y controles antiabuso. No debe habilitar lectura, aprobación ni elección libre de cargos iniciales. Comprobar anónimo, Secretaría, Tesorería y Directiva en todas las rutas, incluidas las acciones personalizadas.

**H02. Edición y borrado genéricos alteran la contabilidad**

**1. Vulnerabilidad y categoría.** A06:2025 — Insecure Design: las rutas de escritura genéricas evitan el flujo de validación y conservación del historial, CWE-841. Alta. Es independiente de H01: agregar un permiso general de edición no aplica las reglas de anulación ni preserva el historial. La atribución del actor y el permiso específico de anular requieren también los controles de A01 descritos en H01.

**2. Ubicación exacta.** [cobranzas/serializers.py:14](C:/Users/Danilo/socios_amandaye/amandaye_backend/apps/cobranzas/serializers.py:14), líneas 14–29; [cobranzas/views.py:35](C:/Users/Danilo/socios_amandaye/amandaye_backend/apps/cobranzas/views.py:35), líneas 35–52; [cobranzas/models.py:143](C:/Users/Danilo/socios_amandaye/amandaye_backend/apps/cobranzas/models.py:143). La validación omitida está en [services/cargos.py:22](C:/Users/Danilo/socios_amandaye/amandaye_backend/apps/cobranzas/services/cargos.py:22).

**3. Riesgo y escenario.** Un `PATCH` que envíe `{"estado":"ANULADO"}` a un cargo evita `anular_cargo()`, incluso si tiene aplicaciones. El saldo pendiente pasa a cero por la propiedad del modelo. También son editables cuenta, importes y `registrado_por`; puede atribuirse un pago a otro usuario. El borrado genérico de un pago elimina sus aplicaciones mediante `CASCADE`, evitando el procedimiento de reversión y su historial. La aceptación del estado y la llegada a `save()` se reprodujeron con persistencia simulada.

**4. Código corregido.** Eliminar `update`, `partial_update` y `destroy` genéricos de los recursos financieros. Mantener creación controlada de pagos y acciones explícitas:

```python
from decimal import Decimal
from rest_framework import mixins, serializers, viewsets
from .models import Cargo, Pago
from .services.pagos import registrar_pago


class PagoSerializer(serializers.ModelSerializer):
    importe_total = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )

    class Meta:
        model = Pago
        fields = (
            "id", "cuenta", "fecha_pago", "importe_total", "medio_pago",
            "referencia", "observaciones", "registrado_por", "created_at",
        )
        read_only_fields = ("id", "registrado_por", "created_at")

    def create(self, validated_data):
        return registrar_pago(
            **validated_data, usuario=self.context["request"].user
        )


class CargoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cargo
        fields = (
            "id", "cuenta", "concepto", "periodo", "importe", "estado",
            "fecha_emision", "fecha_vencimiento", "observaciones",
        )
        read_only_fields = fields


class PagoViewSet(mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Pago.objects.all()
    serializer_class = PagoSerializer
    # Conservar aquí la acción aplicar, protegida por H01 y corregida en H09/H13.


class CargoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Cargo.objects.all()
    serializer_class = CargoSerializer
    # Conservar aquí la acción anular, protegida por H01 y el bloqueo de H09.
```

En `AplicacionPago.pago`, cambiar `on_delete=models.CASCADE` por `models.PROTECT` y crear la migración correspondiente. Las correcciones de movimientos deben conservar el registro original y generar una reversión autorizada. Pasar `usuario=request.user` al servicio de aplicación; no aceptar el actor desde JSON. La creación manual de cargos, si se requiere, debe tener una acción que use `crear_cargo()` y su permiso, sin reabrir el CRUD completo.

**H03. Secretaría puede cambiar estados reservados a Directiva**

**1. Vulnerabilidad y categoría.** A01:2025 — Broken Access Control. Alta; requiere una cuenta de personal con permiso de alta o edición de socios.

**2. Ubicación exacta.** [usuarios/admin.py:387](C:/Users/Danilo/socios_amandaye/amandaye_backend/apps/usuarios/admin.py:387), líneas 387–394: `activo` es editable. [usuarios/admin.py:488](C:/Users/Danilo/socios_amandaye/amandaye_backend/apps/usuarios/admin.py:488), líneas 488–542: `save_model()` ejecuta transiciones sin verificar permisos especiales. [setup_roles.py:33](C:/Users/Danilo/socios_amandaye/amandaye_backend/apps/usuarios/management/commands/setup_roles.py:33), líneas 33–44: Secretaría tiene alta/edición, pero no aprobar, rechazar o dar de baja.

**3. Riesgo y escenario.** Secretaría puede abrir el formulario de un socio pendiente, elegir ALTA y guardar. El servicio de aprobación se ejecuta aunque no posea `puede_aprobar_socio`. También puede crear un socio directamente activo. Ocultar opciones del menú de acciones mediante `get_actions()` no controla este formulario.

**4. Código corregido.** Hacer el estado de sólo lectura, forzar nuevas solicitudes pendientes y canalizar cada transición por una acción con permiso explícito. Sustituir el `save_model()` actual; no dejar sus ramas antiguas debajo de este código:

```python
from django.core.exceptions import PermissionDenied
from django.db import transaction

# Dentro de SociosAdmin:
readonly_fields = (
    "enlace_a_persona", "activo", "fechaSolicitud", "fechaAprobacion",
    "fechaAlta", "fechaBaja",
)

def get_readonly_fields(self, request, obj=None):
    fields = tuple(super().get_readonly_fields(request, obj))
    return fields + (("numero",) if obj is not None else ())

@transaction.atomic
def save_model(self, request, obj, form, change):
    if change:
        previous = Socios.objects.select_for_update().get(pk=obj.pk)
        if obj.activo != previous.activo:
            raise PermissionDenied("Use una acción autorizada para cambiar el estado.")
    else:
        obj.activo = 2
        obj.fechaAlta = None
        obj.fechaAprobacion = None
        obj.fechaBaja = None
    super().save_model(request, obj, form, change)
```

Registrar explícitamente las acciones y asociar el permiso correcto, por ejemplo:

```python
# Dentro de SociosAdmin; adaptar igualmente rechazo y baja.
actions = ["aprobar_socios_seleccionados"]

def has_aprobar_permission(self, request):
    return request.user.has_perm("usuarios.puede_aprobar_socio")

@admin.action(description="Aprobar socios pendientes", permissions=["aprobar"])
def aprobar_socios_seleccionados(self, request, queryset):
    if not self.has_aprobar_permission(request):
        raise PermissionDenied
    from apps.usuarios.services.socios import aprobar_socio
    for socio in queryset:
        aprobar_socio(socio)
```

La misma autorización debe comprobarse en un servicio de transición que reciba el actor, compartido por admin/API. El detalle completo para registrar aprobación, rechazo, baja y reactivación está en [admin_findings.md](C:/Users/Danilo/socios_amandaye/artifacts/security_audit_2026-09-11/admin_findings.md). No otorgar `change_socios` a Directiva como atajo para resolver la interfaz.

**H04. Clave de firma JWT incluida en código**

**1. Vulnerabilidad y categoría.** A04:2025 — Cryptographic Failures, CWE-321. Crítica cuando no se proporciona una clave secreta distinta mediante el entorno.

**2. Ubicación exacta.** [settings.py:28](C:/Users/Danilo/socios_amandaye/amandaye_backend/amandaye_backend/settings.py:28): valor literal de respaldo de `SECRET_KEY`. [settings.py:191](C:/Users/Danilo/socios_amandaye/amandaye_backend/amandaye_backend/settings.py:191), líneas 191–192: HS256 y `SIGNING_KEY = SECRET_KEY`. El `.env` del proyecto no define `SECRET_KEY`; no se reprodujo el valor de la clave en este informe.

**3. Riesgo y escenario.** Si se utiliza el respaldo, quien conozca el código puede firmar tokens de acceso con el identificador de un usuario activo y suplantarlo en rutas JWT. Corregir los permisos de H01 no resuelve esa falsificación. No se generaron ni utilizaron tokens contra usuarios reales. El riesgo depende de la clave efectiva del despliegue, que no se inspeccionó.

**4. Código corregido.** Exigir secretos independientes, generados aleatoriamente y almacenados fuera del repositorio:

```python
import os
from django.core.exceptions import ImproperlyConfigured

def required_secret(name):
    value = os.environ.get(name, "")
    if len(value) < 50 or value.startswith("django-insecure-"):
        raise ImproperlyConfigured(f"Configure un secreto seguro para {name}.")
    return value

SECRET_KEY = required_secret("SECRET_KEY")
# Aplicar después de definir SIMPLE_JWT:
SIMPLE_JWT["SIGNING_KEY"] = required_secret("JWT_SIGNING_KEY")
if SIMPLE_JWT["SIGNING_KEY"] == SECRET_KEY:
    raise ImproperlyConfigured("Use claves independientes para Django y JWT.")
```

La longitud por sí sola no garantiza aleatoriedad: aprovisionar valores generados con un CSPRNG. Si el respaldo se utilizó, rotar ambas claves e invalidar sesiones/tokens afectados; no conservar la clave comprometida como alternativa de verificación. [Gestión de la firma en SimpleJWT](https://django-rest-framework-simplejwt.readthedocs.io/en/latest/settings.html#signing-key).

**H05. MySQL con root sin contraseña y puerto publicado**

**1. Vulnerabilidad y categoría.** A02:2025 — Security Misconfiguration. Crítica para una instancia inicializada con esta configuración y alcanzable por un atacante.

**2. Ubicación exacta.** [docker-compose.yml:21](C:/Users/Danilo/socios_amandaye/docker-compose.yml:21), líneas 21–22: aplicación conectada como root con contraseña vacía. [docker-compose.yml:40](C:/Users/Danilo/socios_amandaye/docker-compose.yml:40), líneas 40–44: puerto `3307:3306` y `MYSQL_ALLOW_EMPTY_PASSWORD: "yes"`. [settings.py:100](C:/Users/Danilo/socios_amandaye/amandaye_backend/amandaye_backend/settings.py:100): usuario root por defecto.

**3. Riesgo y escenario.** Una conexión admitida por MySQL puede acceder con privilegios excesivos y sin contraseña. La publicación del puerto amplía la superficie fuera de la red interna de contenedores. La configuración real de usuarios/hosts de un volumen existente y el firewall pueden limitar ese acceso; no se intentó conectar. Las variables de inicialización no cambian las credenciales de un volumen ya creado. [Imagen oficial de MySQL](https://hub.docker.com/_/mysql).

**4. Código corregido.** Reemplazar los campos correspondientes del Compose; eliminar el puerto publicado de `db` y `MYSQL_ALLOW_EMPTY_PASSWORD`:

```yaml
services:
  backend:
    environment:
      DB_HOST: db
      DB_PORT: "3306"
      DB_NAME: amandaye
      DB_USER: amandaye_app
      DB_PASSWORD: ${AMANDAYE_DB_PASSWORD:?Configure la credencial de aplicación}
  db:
    image: mysql:8.0
    environment:
      MYSQL_DATABASE: amandaye
      MYSQL_USER: amandaye_app
      MYSQL_PASSWORD: ${AMANDAYE_DB_PASSWORD:?Configure la credencial de aplicación}
      MYSQL_ROOT_PASSWORD: ${AMANDAYE_ROOT_PASSWORD:?Configure la credencial administrativa}
```

Conservar volúmenes y los demás campos necesarios. Para la base existente, cambiar usuarios/contraseñas mediante una migración operativa controlada, con respaldo; no borrar el volumen. Limitar al usuario de ejecución a los permisos necesarios y reservar DDL/migraciones a una identidad separada. El usuario creado automáticamente por la imagen tiene permisos amplios sobre su base: reducirlos después de inicializar.

**H06. Configuración de desarrollo publicada y transporte sin protección exigida**

**1. Vulnerabilidad y categoría.** A02:2025 — Security Misconfiguration. A04:2025 — Cryptographic Failures para credenciales/datos que atraviesen una red sin TLS. Alta si esta configuración se utiliza fuera de desarrollo local.

**2. Ubicación exacta.** [settings.py:31](C:/Users/Danilo/socios_amandaye/amandaye_backend/amandaye_backend/settings.py:31), líneas 31–33: `DEBUG=True` y hosts comodín; líneas 96–106: conexión MySQL con SSL deshabilitado. [Dockerfile:14](C:/Users/Danilo/socios_amandaye/Dockerfile:14), [docker-compose.yml:8](C:/Users/Danilo/socios_amandaye/docker-compose.yml:8): `runserver` escuchando en todas las interfaces. No se configuran redirección HTTPS ni cookies `Secure` en el archivo de settings.

**3. Riesgo y escenario.** Un error no capturado puede mostrar trazas y detalles internos; el comodín elimina la validación de nombres de host. Acceder al admin por HTTP en una red no confiable expone credenciales y sesiones a interceptación. No se afirmó que todas las variables secretas aparezcan en la página de depuración: Django oculta algunas. Tampoco se verificó un proxy HTTPS externo que pudiera mitigar el transporte.

**4. Código corregido.** Configuración de producción separada y obligatoria:

```python
from django.core.exceptions import ImproperlyConfigured

DEBUG = False
ALLOWED_HOSTS = [
    value.strip() for value in os.environ["DJANGO_ALLOWED_HOSTS"].split(",")
    if value.strip()
]
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("Configure nombres de host explícitos.")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SECURE_HSTS_SECONDS = 31536000
```

Configurar un proxy con certificado válido y publicar únicamente su puerto HTTPS. Cambiar `runserver` por un servidor WSGI de producción, instalado y fijado en dependencias, por ejemplo:

```dockerfile
CMD ["gunicorn", "amandaye_backend.wsgi:application", "--bind", "0.0.0.0:8000"]
```

Sustituir también `command` en Compose, que sobrescribe el CMD. Quitar la publicación directa de 8000 cuando el proxy esté en la red interna. Si termina TLS en el proxy, configurar `SECURE_PROXY_SSL_HEADER` únicamente cuando ese proxy elimine y establezca de forma confiable el encabezado correspondiente. Activar HSTS después de verificar HTTPS. Si MySQL cruza una red no confiable, reemplazar `ssl_disabled` por TLS con CA e identidad verificadas. [Guía de despliegue de Django](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/).

**H07. Vite vulnerable permite leer archivos del proceso de desarrollo**

**1. Vulnerabilidad y categoría.** A03:2025 — Software Supply Chain Failures. Alta, condicionada a que el servidor de desarrollo sea alcanzable.

**2. Ubicación exacta.** [package-lock.json:3524](C:/Users/Danilo/socios_amandaye/amandaye_frontend/package-lock.json:3524): Vite 7.0.6; también presente en `node_modules`. [vite.config.js:15](C:/Users/Danilo/socios_amandaye/amandaye_frontend/vite.config.js:15): `host: true`. [docker-compose.yml:29](C:/Users/Danilo/socios_amandaye/docker-compose.yml:29), líneas 29–31: publicación en todas las interfaces.

**3. Riesgo y escenario.** CVE-2026-39363 permite solicitar archivos mediante el WebSocket de Vite eludiendo las restricciones de la ruta HTTP. La versión y configuración coinciden con el aviso; no se ejecutó el ataque. El alcance son los archivos legibles por el proceso: en Docker, el sistema de archivos y montajes del contenedor frontend, no automáticamente toda la máquina. [Aviso oficial de Vite](https://github.com/vitejs/vite/security/advisories/GHSA-p9ff-h696-f583).

**4. Código corregido.** Actualizar Vite y regenerar el lockfile antes de usar `npm ci`. El mínimo propuesto incorpora también la corrección de rutas de Windows publicada en junio de 2026:

```json
{
  "devDependencies": {
    "vite": "^7.3.5"
  }
}
```

```powershell
# Dentro de amandaye_frontend, al implementar la remediación:
npm install --save-dev "vite@^7.3.5"
npm ls vite
npm audit
npm run build
```

En desarrollo nativo usar `server.host: '127.0.0.1'`. En Docker reemplazar `5173:5173` por `127.0.0.1:5173:5173`. Para producción compilar y servir `dist` con HTTPS, sin el servidor de desarrollo. [Corrección de Windows](https://github.com/vitejs/vite/security/advisories/GHSA-fx2h-pf6j-xcff). Más detalle en [frontend_findings.md](C:/Users/Danilo/socios_amandaye/artifacts/security_audit_2026-09-11/frontend_findings.md).

**H08. Backend fijado a componentes vulnerables o sin soporte**

**1. Vulnerabilidad y categoría.** A03:2025 — Software Supply Chain Failures. Media en esta revisión; se confirmó el problema de versiones, no la explotación remota de todos sus avisos.

**2. Ubicación exacta.** [requirements.txt:1](C:/Users/Danilo/socios_amandaye/amandaye_backend/requirements.txt:1): Django 4.2.21; línea 7: PyMySQL 1.1.0. [Dockerfile:1](C:/Users/Danilo/socios_amandaye/Dockerfile:1): Python 3.9. [amandaye_backend/__init__.py:1](C:/Users/Danilo/socios_amandaye/amandaye_backend/amandaye_backend/__init__.py:1): PyMySQL sustituye al driver MySQLdb.

**3. Riesgo y escenario.** Las instalaciones reproducibles vuelven a introducir versiones antiguas. Django 4.2 terminó soporte en abril de 2026 y Python 3.9 en octubre de 2025. Django 4.2.21 precede a la corrección CVE-2025-48432 de inyección de registros. PyMySQL 1.1.0 tiene CVE-2024-36039, que requiere valores de tipo diccionario no confiables como parámetros SQL; no se encontró esa ruta en la aplicación. El venv local contiene PyMySQL 1.1.1, por lo que no debe confundirse su versión con la fijada para reconstruir. [Soporte Django](https://www.djangoproject.com/download/), [soporte Python 3.9](https://peps.python.org/pep-0596/), [aviso Django](https://www.djangoproject.com/weblog/2025/jun/04/security-releases/), [corrección PyMySQL](https://github.com/PyMySQL/PyMySQL/releases/tag/v1.1.1).

**4. Código corregido.** Migrar a Python mantenido y una rama soportada de Django; resolver conjuntamente DRF, SimpleJWT y los drivers:

```dockerfile
FROM python:3.12-slim
```

```text
# Entradas para resolver un nuevo lock; no sustituyen todas las dependencias.
Django>=5.2.17,<5.3
PyMySQL>=1.1.1,<2
```

La página de descargas consultada publica Django 5.2.17 como parche de la rama LTS. Generar un archivo de dependencias bloqueado con hashes, revisar avisos del árbol completo y usar `pip install --require-hashes -r requirements.lock`. Validar migraciones y compatibilidad antes del cambio; no basta con editar dos números. La imagen slim requerirá bibliotecas de compilación si se conserva `mysqlclient`, o unificar el driver usado y quitar la dependencia redundante tras probarlo.

**H09. Carrera al aplicar o revertir pagos**

**1. Vulnerabilidad y categoría.** A06:2025 — Insecure Design, CWE-362. Alta. Confirmada la ausencia de serialización; no se ejecutó una carrera contra MySQL.

**2. Ubicación exacta.** [services/pagos.py:23](C:/Users/Danilo/socios_amandaye/amandaye_backend/apps/cobranzas/services/pagos.py:23), líneas 23–50: verificar saldo y crear aplicación sin bloquear filas. Líneas 63–85: reversión sin bloqueo compartido. [services/cargos.py:22](C:/Users/Danilo/socios_amandaye/amandaye_backend/apps/cobranzas/services/cargos.py:22): anulación separada del mismo conjunto de operaciones.

**3. Riesgo y escenario.** Dos solicitudes simultáneas pueden leer el mismo saldo disponible de $100 y aplicar $80 cada una. Ambas validan antes de que la otra confirme, contabilizando $160 contra un pago de $100. `transaction.atomic` garantiza rollback de una transacción, pero no impide que dos transacciones tomen la misma decisión con lecturas concurrentes. Las restricciones actuales sólo exigen importes positivos. [Mapeo de condiciones de carrera en A06](https://top10.owasp.org/2025/A06_2025-Insecure_Design/).

**4. Código corregido.** Adoptar un bloqueo común antes de leer saldos. Insertar al comienzo de `aplicar_pago()`, después de entrar en la transacción, y ejecutar el cuerpo de validación/cálculo existente sobre las instancias recargadas:

```python
from decimal import Decimal
from django.core.exceptions import ValidationError

# Dentro de aplicar_pago(), bajo @transaction.atomic:
if not isinstance(importe_aplicar, Decimal) or not importe_aplicar.is_finite():
    raise ValidationError("Importe inválido.")
cuenta_id = pago.cuenta_id
CuentaCorriente.objects.select_for_update().get(pk=cuenta_id)
pago = Pago.objects.select_for_update().get(pk=pago.pk)
cargo = Cargo.objects.select_for_update().get(pk=cargo.pk)
if pago.cuenta_id != cuenta_id or cargo.cuenta_id != cuenta_id:
    raise ValidationError("Los movimientos deben pertenecer a la misma cuenta.")
# A continuación: validaciones de saldo, creación y recálculo existentes.
```

Aplicar el mismo protocolo a reversión y anulación: **cuenta → pago → cargo → aplicación**, omitiendo filas que no intervienen y usando IDs ordenados cuando haya varias del mismo tipo. Revalidar después de obtener los bloqueos. Prohibir cambios directos de la cuenta de un movimiento tanto en API como en admin según H02. Esta inserción aislada no resuelve la carrera si otras rutas siguen escribiendo sin el protocolo; el parche completo debe cubrirlas. Si se usa REPEATABLE READ, sumar también las aplicaciones mediante lecturas bloqueantes para evitar snapshots anteriores: el detalle enlazado incluye esa implementación. Añadir pruebas con conexiones independientes en MySQL/InnoDB y una clave de idempotencia para reintentos de la misma operación. [Detalle de implementación](C:/Users/Danilo/socios_amandaye/artifacts/security_audit_2026-09-11/admin_findings.md).

**H10. Login sin limitación de intentos**

**1. Vulnerabilidad y categoría.** A07:2025 — Authentication Failures. Media; no se hallaron límites en el proyecto y no se inspeccionó infraestructura externa.

**2. Ubicación exacta.** [urls.py:40](C:/Users/Danilo/socios_amandaye/amandaye_backend/amandaye_backend/urls.py:40), líneas 40–45: login del admin y emisión/renovación de tokens estándar. [settings.py:176](C:/Users/Danilo/socios_amandaye/amandaye_backend/amandaye_backend/settings.py:176), líneas 176–190: sin throttles ni backend de bloqueo; `UPDATE_LAST_LOGIN=True`.

**3. Riesgo y escenario.** Un atacante puede automatizar intentos de contraseña en `/api/token/`, `/login/` o `/admin/login/`. La emisión repetida con credenciales válidas también produce escrituras de `last_login`. Las validaciones de complejidad de contraseñas no limitan intentos. SimpleJWT advierte sobre este coste; DRF aclara que sus throttles básicos no constituyen por sí solos una defensa contra fuerza bruta. [SimpleJWT](https://django-rest-framework-simplejwt.readthedocs.io/en/latest/settings.html#update-last-login), [límites del throttling de DRF](https://www.django-rest-framework.org/api-guide/throttling/).

**4. Código corregido.** Añadir control persistente de intentos por cuenta/IP, con una dependencia compatible y fijada. Ejemplo de integración con `django-axes[ipware]` después de instalarlo y aplicar sus migraciones:

```python
from datetime import timedelta

INSTALLED_APPS += ["axes"]
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
MIDDLEWARE += ["axes.middleware.AxesMiddleware"]
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_PARAMETERS = ["username", "ip_address"]
SIMPLE_JWT["UPDATE_LAST_LOGIN"] = False
```

Verificar que el serializer JWT pasa `request` a `authenticate`, adaptar la respuesta de bloqueo a JSON y probar que ninguno de los tres accesos omita el límite. Configurar la IP real sólo desde un proxy confiable; acompañar con limitación de tráfico en ese proxy y MFA para personal. El límite y la recuperación deben ajustarse para evitar bloqueos prolongados provocados por terceros. Esta integración requiere validación; no se instaló durante la auditoría. [Uso de Axes](https://django-axes.readthedocs.io/en/latest/3_usage.html), [instalación](https://django-axes.readthedocs.io/en/latest/2_installation.html), [integración con DRF](https://django-axes.readthedocs.io/en/latest/6_integration.html).

**H11. Datos de personas y configuración versionados**

**1. Vulnerabilidad y categoría.** A01:2025 — Broken Access Control, por inclusión potencial de información sensible en código/archivos compartidos. Media y condicional: se confirmó el versionado y la existencia de registros, no que el repositorio sea público ni que los datos sean reales.

**2. Ubicación exacta.** [.gitignore:1](C:/Users/Danilo/socios_amandaye/.gitignore:1) sólo excluye `venv/`. Git rastrea [amandaye_backend/.env](C:/Users/Danilo/socios_amandaye/amandaye_backend/.env), [db.sqlite3](C:/Users/Danilo/socios_amandaye/db.sqlite3) y [docker/mysql/init/amandaye.sql:209](C:/Users/Danilo/socios_amandaye/docker/mysql/init/amandaye.sql:209). El SQL contiene inserciones de personas en líneas 209, 537 y 850, y de socios en 1198 y 1759. [Dockerfile:10](C:/Users/Danilo/socios_amandaye/Dockerfile:10) copia también el `.env` del backend al construir la imagen, al no existir `.dockerignore`.

**3. Riesgo y escenario.** Compartir el repositorio o la imagen puede entregar información que no debería estar disponible a quien sólo necesita el código. No se volcaron datos individuales ni se abrió SQLite. Si los registros son enteramente sintéticos y no hay credenciales privadas, disminuye el impacto actual; aun así, la configuración permite incorporar secretos en futuros commits. Un `.gitignore` nuevo no elimina lo ya rastreado ni el historial.

**4. Código corregido.** Ampliar `.gitignore` y excluir estos archivos de los contextos de construcción:

```gitignore
venv/
**/__pycache__/
**/node_modules/
**/.env
**/.env.*
!**/.env.example
**/*.sqlite3
/docker/mysql/init/amandaye.sql
```

```dockerignore
.git
venv
**/node_modules
**/__pycache__
**/.env
**/.env.*
**/*.sqlite3
docker/mysql/init/amandaye.sql
```

Reemplazar el dump de inicialización por esquema y fixtures sintéticos. Retirar del índice los archivos sensibles preservando las copias operativas; verificar exposición e historial antes de decidir su saneamiento. Rotar cualquier credencial real que haya sido distribuida. No se borraron archivos ni se reescribió Git como parte de esta revisión.

**H12. Redirecciones abiertas a partir de Referer**

**1. Vulnerabilidad y categoría.** A01:2025 — Broken Access Control, CWE-601. Baja; confirmada mediante ejecución aislada.

**2. Ubicación exacta.** [urls.py:29](C:/Users/Danilo/socios_amandaye/amandaye_backend/amandaye_backend/urls.py:29), líneas 29–32 y 56–59; [middleware.py:17](C:/Users/Danilo/socios_amandaye/amandaye_backend/amandaye_backend/middleware.py:17), líneas 17–22. La ruta raíz y el comodín final hacen alcanzable `fallback_redirect`.

**3. Riesgo y escenario.** Las tres funciones responden con `302 Location: https://attacker.invalid/` si reciben ese Referer. Una navegación desde un sitio controlado por un atacante puede utilizar al dominio del club como salto hacia otro destino. La severidad es limitada porque un enlace común no permite fijar arbitrariamente ese encabezado; no se demostró robo de tokens ni XSS.

**4. Código corregido.** Preferir destinos internos constantes y conservar el estado 404 real para rutas inexistentes:

```python
from django.http import HttpResponseNotFound
from django.shortcuts import redirect

def fallback_redirect(request):
    return redirect("/login/")

def custom_404(request, exception=None):
    return HttpResponseNotFound("Página no encontrada.")

class Redirect404Middleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)
```

Retirar el comodín `re_path(r'^.*$', fallback_redirect)` para que las URLs desconocidas produzcan 404. Se puede eliminar por completo el middleware pasante. Si se conserva el retorno a una página previa, validarlo con `url_has_allowed_host_and_scheme` contra nombres explícitos; no confiar en Referer ni en un Host arbitrario. [CWE-601 en A01](https://top10.owasp.org/2025/A01_2025-Broken_Access_Control/).

**H13. Excepciones reveladas o ignoradas en operaciones financieras**

**1. Vulnerabilidad y categoría.** A10:2025 — Mishandling of Exceptional Conditions. Media. Se confirmó la devolución literal de una excepción sintética; el estado parcial de una baja depende de que falle el cierre de cuenta.

**2. Ubicación exacta.** [cobranzas/views.py:73](C:/Users/Danilo/socios_amandaye/amandaye_backend/apps/cobranzas/views.py:73), líneas 73–74 y 86–87: `str(e)` enviado al cliente. [services/socios.py:320](C:/Users/Danilo/socios_amandaye/amandaye_backend/apps/usuarios/services/socios.py:320), líneas 320–329: cualquier fallo al cerrar una cuenta es ignorado.

**3. Riesgo y escenario.** Una excepción del driver o del servicio puede revelar nombres internos y detalles operativos incluso con DEBUG desactivado. Por otra parte, si una cuenta no puede cerrarse durante una baja, el código confirma la baja y deja la cuenta activa. El generador de cuotas selecciona cuentas activas y puede seguir emitiendo cargos al socio dado de baja. No se demostró que un atacante remoto pueda forzar ese fallo específico de base de datos; se trata de una condición excepcional que el código maneja de forma insegura.

**4. Código corregido.** Validar los parámetros con serializers y devolver errores de negocio controlados. Para fallos inesperados, registrar un evento sin incluir credenciales/cuerpo de solicitud y devolver un mensaje genérico con identificador:

```python
import logging
import uuid
from decimal import Decimal
from rest_framework import serializers, status
from rest_framework.response import Response

logger = logging.getLogger("amandaye.security")

class AplicarPagoInput(serializers.Serializer):
    cargo_id = serializers.IntegerField(min_value=1)
    importe = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )

def unexpected_payment_error():
    event_id = uuid.uuid4().hex
    logger.error("payment_operation_failed event_id=%s", event_id)
    return Response(
        {"error": "No se pudo completar la operación.", "id": event_id},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
```

En `aplicar`, llamar `is_valid(raise_exception=True)` y usar `validated_data`; dentro del `except Exception`, devolver `unexpected_payment_error()` en lugar de `str(e)`. Aplicar lo mismo a la reversión. Configurar la salida de `amandaye.security` y alertas para errores repetidos; los diagnósticos internos detallados deben ir a un canal restringido con eliminación de datos sensibles.

En `dar_baja_socio`, reemplazar únicamente el bloque de cierre de cuenta por este código, conservando la transacción exterior de la función:

```python
try:
    cc = socio.cuenta_corriente
except CuentaCorriente.DoesNotExist:
    cc = None

if cc is not None:
    cc.estado = CuentaCorriente.Estado.CERRADA
    cc.fecha_cierre = datetime.date.today()
    cc.save(update_fields=["estado", "fecha_cierre"])
```

Una cuenta ausente se trata expresamente; cualquier otro error se propaga y revierte la baja entera. Coordinar además el bloqueo de socios/cuentas con los demás servicios para evitar carreras. [Tratamiento de condiciones excepcionales en OWASP](https://top10.owasp.org/2025/A10_2025-Mishandling_of_Exceptional_Conditions/).

**Evidencia y límites de verificación**

- [verify_api.py](C:/Users/Danilo/socios_amandaye/artifacts/security_audit_2026-09-11/verify_api.py): cinco grupos de comprobaciones satisfactorias: permisos de ocho clases; escritura directa de ANULADO; campos financieros editables y borrado; consulta de persona sin login; excepción expuesta. Toda persistencia está simulada y todo SQL bloqueado.
- [verify_config.py](C:/Users/Danilo/socios_amandaye/artifacts/security_audit_2026-09-11/verify_config.py): ejecuta las tres funciones de redirección del código fuente en aislamiento, verifica valores de configuración sin imprimir claves y localiza inserciones del dump sin mostrar registros.
- [verify_report.py](C:/Users/Danilo/socios_amandaye/artifacts/security_audit_2026-09-11/verify_report.py): verifica la estructura de los 13 hallazgos, la sintaxis de 13 fragmentos Python, las referencias locales y 10 escenarios de la política de permisos propuesta. Estos escenarios comprueban denegación anónima, separación entre edición/aprobación, usuarios inactivos y acceso a reportes; no sustituyen pruebas de integración de todos los parches.
- El intérprete original del venv no existe en esta máquina. Se usó Python 3.12 del runtime disponible con Django/DRF presentes en `venv/Lib/site-packages`. SimpleJWT no está instalado en ese venv: el harness desactiva sólo su autenticación y conserva la política de permisos extraída del código. No es una prueba HTTP integral del despliegue ni de verificación criptográfica JWT.
- No se conectó a MySQL ni se modificó SQLite; no se inició Docker, se ejecutaron ataques de red, se instalaron paquetes, se rotaron secretos ni se alteraron archivos de aplicación.
- Las carreras requieren pruebas de integración con MySQL/InnoDB; las versiones vulnerables se contrastaron con fuentes de los mantenedores. No se ejecutó un escáner exhaustivo de todas las dependencias.
- No se encontraron rutas de explotación confirmables de SQL injection propia, ejecución de comandos, SSRF o XSS en el código revisado. Los `mark_safe`/`json|safe` observados se alimentan de constantes, fechas o números. Esto no constituye garantía de ausencia de vulnerabilidades.
- Los tokens en `localStorage` amplifican una eventual XSS; no se demostró esa cadena y no se contó como hallazgo independiente. Tampoco se inventaron hallazgos para completar todas las categorías OWASP.

**Orden propuesto de corrección:** H01 y H02; H04/H05 si esos valores se usan; H03/H09; retirar servidores de desarrollo y actualizar dependencias; completar límites de autenticación, protección de artefactos y manejo de errores. Antes de publicar, verificar rechazo anónimo, separación de roles y consistencia de saldos con pruebas sobre una base desechable.
