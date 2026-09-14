# Notas de auditoría: administración y servicios

Revisión estática de código; no se consultó la base de datos real ni se modificó la aplicación. Rutas comprobadas en `amandaye_backend/amandaye_backend/urls.py:41,52`: admin y API de cobranzas están publicadas. Se verificó la clasificación actual contra [OWASP A06:2025](https://top10.owasp.org/2025/A06_2025-Insecure_Design/), que incluye expresamente CWE-362 y CWE-841.

## 1. Secretaría puede aprobar, rechazar o dar de baja socios desde el formulario

- **Categoría:** A01:2025 Broken Access Control; alta, con acceso de personal de Secretaría.
- **Ubicación:** `amandaye_backend/apps/usuarios/admin.py:394` expone `activo`; `:488-542` realiza transiciones sin comprobar permisos específicos. Los permisos se revisan únicamente en `get_actions`, líneas 404-412. `amandaye_backend/apps/usuarios/management/commands/setup_roles.py:32-43` concede a Secretaría `add_socios` y `change_socios`, pero no los permisos de aprobación, rechazo ni baja.
- **Escenario:** una sesión staff del grupo Secretaría entra a `/admin/usuarios/socios/<numero>/change/`, cambia PENDIENTE a ALTA y envía el formulario. `save_model` ejecuta `aprobar_socio` en la línea 506. La misma vía permite rechazar o dar de baja. En `/add/`, enviar `activo=1` elude incluso el servicio de aprobación porque `change=False` llega directamente a `super().save_model`, línea 542: se guarda ALTA sin cuenta/cargos/fechas de aprobación. Esto se deduce del flujo; no se ejecutaron operaciones contra datos reales.
- **Remediación:** reservar cambios de estado para acciones específicas, imponer estado PENDIENTE al crear, preservar el estado al editar y comprobar el permiso en cada acción. Reemplazar el `save_model` actual y añadir las siguientes partes a `SociosAdmin`. Conservar las demás configuraciones de presentación. Registrar explícitamente `actions`: actualmente los tres métodos decorados de Socios no están incluidos en una lista de acciones.

```python
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from apps.usuarios.models import Socios
from apps.usuarios.services.socios import (
    aprobar_socio, rechazar_socio, dar_baja_socio, reactivar_socio,
)

# Dentro de SociosAdmin:
actions = (
    'aprobar_socios_seleccionados', 'rechazar_socios_seleccionados',
    'dar_baja_socios_seleccionados', 'reactivar_socios_seleccionados',
)

def get_readonly_fields(self, request, obj=None):
    fields = list(super().get_readonly_fields(request, obj))
    fields.append('activo')
    if obj is not None:
        fields.append('numero')  # No cambiar la identidad de un registro existente.
    return tuple(dict.fromkeys(fields))

@transaction.atomic
def save_model(self, request, obj, form, change):
    if change:
        actual = Socios.objects.select_for_update().get(pk=obj.pk)
        obj.activo = actual.activo
    else:
        obj.activo = 2
        obj.fechaSolicitud = timezone.localdate()
        obj.fechaAprobacion = obj.fechaAlta = obj.fechaBaja = None
    super().save_model(request, obj, form, change)

def has_aprobar_socio_permission(self, request):
    return request.user.has_perm('usuarios.puede_aprobar_socio')

def has_rechazar_socio_permission(self, request):
    return request.user.has_perm('usuarios.puede_rechazar_socio')

def has_dar_baja_socio_permission(self, request):
    return request.user.has_perm('usuarios.puede_dar_baja_socio')

def _transicionar(self, request, queryset, permiso, servicio, descripcion):
    if not request.user.has_perm(permiso):
        raise PermissionDenied
    for socio_id in queryset.values_list('pk', flat=True):
        try:
            with transaction.atomic():
                socio = Socios.objects.select_for_update().get(pk=socio_id)
                servicio(socio)
                self.log_change(request, socio, descripcion)
        except ValidationError as exc:
            self.message_user(request, '; '.join(exc.messages), messages.ERROR)

@admin.action(description='Aprobar socios', permissions=['aprobar_socio'])
def aprobar_socios_seleccionados(self, request, queryset):
    self._transicionar(request, queryset, 'usuarios.puede_aprobar_socio',
                       aprobar_socio, 'Aprobación de socio')

@admin.action(description='Rechazar solicitudes', permissions=['rechazar_socio'])
def rechazar_socios_seleccionados(self, request, queryset):
    self._transicionar(request, queryset, 'usuarios.puede_rechazar_socio',
                       rechazar_socio, 'Rechazo de solicitud')

@admin.action(description='Dar de baja', permissions=['dar_baja_socio'])
def dar_baja_socios_seleccionados(self, request, queryset):
    self._transicionar(request, queryset, 'usuarios.puede_dar_baja_socio',
                       dar_baja_socio, 'Baja de socio')

# Política propuesta: reactivar exige el mismo permiso que aprobar.
@admin.action(description='Reactivar socios', permissions=['aprobar_socio'])
def reactivar_socios_seleccionados(self, request, queryset):
    self._transicionar(request, queryset, 'usuarios.puede_aprobar_socio',
                       reactivar_socio, 'Reactivación de socio')
```

El permiso de `change_socios` controla editar datos. Las acciones usan permisos propios, permitiendo a Comisión Directiva actuar con sus permisos específicos y `view_socios`. Los endpoints de API deben imponer las mismas reglas; corregir exclusivamente el admin no protege la API. Pruebas recomendadas con cuentas sintéticas: Secretaría no puede transicionar por POST ni crear directamente ALTA; Comisión Directiva puede aprobar mediante la acción y obtiene cuenta/cargos; editar el nombre o comentarios conserva el estado.

## 2. Doble gasto del saldo de un pago mediante solicitudes concurrentes

- **Categoría:** A06:2025 Insecure Design; alta si el endpoint es accesible al atacante. CWE-362.
- **Ubicación:** `amandaye_backend/apps/cobranzas/services/pagos.py:23-43`, comprobaciones de saldo y alta de aplicación sin bloqueo. Propiedades de saldo: `apps/cobranzas/models.py:83-90,131-136`. Alcanzable por `apps/cobranzas/views.py:54-69` y por `apps/cobranzas/admin.py:231-250`. La reversión usa objetos sin recargar/bloquear en `services/pagos.py:63-85`; anulación tampoco coordina bloqueos en `services/cargos.py:22-29`.
- **Escenario:** dos POST concurrentes aplican los mismos $100 disponibles del pago a dos cargos distintos de $100. Ambas transacciones leen $100 antes de crear su aplicación; se guardan $200 aplicados contra un ingreso real de $100. Que cada llamada use `transaction.atomic` no serializa esas lecturas. Se puede producir también exceso sobre el mismo cargo o un estado final incoherente cuando aplicar/revertir/anular compiten. No se reprodujo contra el motor real.
- **Remediación:** todos los escritores financieros deben bloquear en orden **CuentaCorriente → Pago → Cargo → AplicacionPago**, recargar los objetos dentro del bloqueo y validar los totales allí. La cuenta actúa como exclusión común para distintos pagos y cargos de la misma cuenta. No basta bloquear solo el pago: dos pagos distintos podrían sobrepagar un mismo cargo. Debe hacerse inmutable `cuenta`/relaciones de movimientos ya creados en API y admin, y eliminar modificaciones/eliminaciones CRUD que eludan estos servicios. El siguiente ejemplo sustituye aplicar/revertir e incorpora anular con la misma disciplina. Los imports y auxiliares se pueden ubicar en un módulo común de movimientos.

```python
from decimal import Decimal, DecimalException
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from apps.cobranzas.models import CuentaCorriente, Pago, Cargo, AplicacionPago
from apps.usuarios.services.habilitacion import recalcular_habilitados

def _importe(valor):
    try:
        importe = Decimal(str(valor))
        if (not importe.is_finite() or importe <= 0 or
                importe > Decimal('99999999.99') or
                importe != importe.quantize(Decimal('0.01'))):
            raise ValidationError('Importe inválido: máximo dos decimales.')
        return importe
    except (DecimalException, ValueError, TypeError):
        raise ValidationError('Importe inválido.')

def _bloquear(cuenta_id, pago_id, cargo_id):
    cuenta = CuentaCorriente.objects.select_for_update().get(pk=cuenta_id)
    pago = Pago.objects.select_for_update().get(pk=pago_id)
    cargo = Cargo.objects.select_for_update().get(pk=cargo_id)
    if pago.cuenta_id != cuenta.pk or cargo.cuenta_id != cuenta.pk:
        raise ValidationError('Pago y cargo deben pertenecer a la misma cuenta.')
    return cuenta, pago, cargo

def _totales_actuales(pago, cargo):
    # Lectura bloqueante: evita usar un snapshot anterior de REPEATABLE READ.
    aplicaciones = list(
        AplicacionPago.objects.select_for_update()
        .filter(Q(pago_id=pago.pk) | Q(cargo_id=cargo.pk), estado='ACTIVA')
        .order_by('pk')
    )
    total_pago = sum((a.importe_aplicado for a in aplicaciones
                      if a.pago_id == pago.pk), Decimal('0.00'))
    total_cargo = sum((a.importe_aplicado for a in aplicaciones
                       if a.cargo_id == cargo.pk), Decimal('0.00'))
    return total_pago, total_cargo

def _guardar_estado(cargo, total):
    if total < 0 or total > cargo.importe:
        raise ValidationError('El cargo presenta un saldo inconsistente.')
    cargo.estado = (Cargo.Estado.PAGADO if total == cargo.importe else
                    Cargo.Estado.PARCIAL if total else Cargo.Estado.PENDIENTE)
    cargo.save(update_fields=['estado', 'updated_at'])

@transaction.atomic
def aplicar_pago(pago, cargo, importe_aplicar, usuario=None):
    importe = _importe(importe_aplicar)
    cuenta, pago, cargo = _bloquear(pago.cuenta_id, pago.pk, cargo.pk)
    if cargo.estado == Cargo.Estado.ANULADO:
        raise ValidationError('No se puede aplicar a un cargo anulado.')
    aplicado_pago, aplicado_cargo = _totales_actuales(pago, cargo)
    if importe > pago.importe_total - aplicado_pago:
        raise ValidationError('Saldo del pago insuficiente.')
    if importe > cargo.importe - aplicado_cargo:
        raise ValidationError('El importe supera el saldo del cargo.')
    aplicacion = AplicacionPago.objects.create(
        pago=pago, cargo=cargo, importe_aplicado=importe,
        registrado_por=usuario,
    )
    _guardar_estado(cargo, aplicado_cargo + importe)
    recalcular_habilitados(socio_id=cuenta.socio_titular_id)
    return aplicacion

@transaction.atomic
def revertir_aplicacion(aplicacion, motivo=None):
    # Estos identificadores son pistas; se vuelven a comprobar bajo bloqueo.
    origen = AplicacionPago.objects.only('pago_id', 'cargo_id').get(pk=aplicacion.pk)
    cuenta_id = Pago.objects.values_list('cuenta_id', flat=True).get(pk=origen.pago_id)
    cuenta, pago, cargo = _bloquear(cuenta_id, origen.pago_id, origen.cargo_id)
    aplicacion = AplicacionPago.objects.select_for_update().get(pk=origen.pk)
    if aplicacion.pago_id != pago.pk or aplicacion.cargo_id != cargo.pk:
        raise ValidationError('El movimiento cambió; vuelva a cargarlo.')
    if aplicacion.estado != AplicacionPago.Estado.ACTIVA:
        raise ValidationError('Esta aplicación ya fue revertida.')
    if cargo.estado == Cargo.Estado.ANULADO:
        raise ValidationError('El cargo requiere conciliación antes de revertir.')
    _, total_cargo = _totales_actuales(pago, cargo)
    aplicacion.estado = AplicacionPago.Estado.REVERTIDA
    aplicacion.fecha_reversion = timezone.now()
    aplicacion.motivo_reversion = motivo or 'Reversión manual'
    aplicacion.save(update_fields=[
        'estado', 'fecha_reversion', 'motivo_reversion', 'updated_at',
    ])
    _guardar_estado(cargo, total_cargo - aplicacion.importe_aplicado)
    recalcular_habilitados(socio_id=cuenta.socio_titular_id)

@transaction.atomic
def anular_cargo(cargo, observaciones=None):
    cuenta = CuentaCorriente.objects.select_for_update().get(pk=cargo.cuenta_id)
    cargo = Cargo.objects.select_for_update().get(pk=cargo.pk)
    if cargo.cuenta_id != cuenta.pk:
        raise ValidationError('El cargo cambió de cuenta; vuelva a cargarlo.')
    activas = list(AplicacionPago.objects.select_for_update()
                   .filter(cargo_id=cargo.pk, estado='ACTIVA').order_by('pk'))
    if activas:
        raise ValidationError('Revierta las aplicaciones activas primero.')
    cargo.estado = Cargo.Estado.ANULADO
    if observaciones:
        cargo.observaciones = (cargo.observaciones or '') + '\nANULADO: ' + observaciones
    cargo.save(update_fields=['estado', 'observaciones', 'updated_at'])
    recalcular_habilitados(socio_id=cuenta.socio_titular_id)
    return cargo
```

Precondiciones de esta remediación: motor con bloqueo de filas (MySQL/InnoDB del proyecto o PostgreSQL); todos los caminos de escritura respetan la misma cuenta/bloqueos; relaciones de movimientos inmutables. `select_for_update` no ofrece protección equivalente en SQLite. Probar con `TransactionTestCase`, conexiones separadas y barrera de concurrencia usando una BD de prueba del mismo motor: dos cargos y un pago, dos pagos y un cargo, aplicar frente a revertir/anular. Verificar que los totales nunca excedan pago/cargo y que un intento reciba error de saldo.

## 3. Baja confirmada aunque falle el cierre de la cuenta

- **Categoría:** A10:2025 Mishandling of Exceptional Conditions; media, condicionada a un fallo operativo al cerrar la cuenta. No se identificó un mecanismo remoto independiente para provocar ese fallo.
- **Ubicación:** `amandaye_backend/apps/usuarios/services/socios.py:316-329`. Se guarda BAJA, se intenta cerrar CC en un savepoint y cualquier `Exception` se descarta. `amandaye_backend/apps/cobranzas/services/cuotas.py:26` selecciona cuentas ACTIVA sin comprobar `socio_titular.activo`; el bucle de generación tampoco lo verifica.
- **Riesgo y escenario:** un error al guardar el cierre de CC revierte solo ese savepoint; `dar_baja_socio` continúa, registra baja y devuelve éxito. La cuenta permanece ACTIVA. Una ejecución posterior del generador emite cargos al socio dado de baja y aumenta su deuda. Es un fallo de integridad bajo una condición excepcional demostrable en código, no una explotación remota comprobada.
- **Remediación:** dentro del `@transaction.atomic` ya existente, reemplazar el bloque de cierre de las líneas 320-329 por lo siguiente. Solo la inexistencia prevista se maneja localmente; un error operativo de guardado se propaga y revierte también el cambio de estado del socio.

```python
try:
    cc = socio.cuenta_corriente
except CuentaCorriente.DoesNotExist:
    cc = None  # Se admite dar de baja una solicitud sin cuenta todavía.

if cc is not None:
    cc.estado = CuentaCorriente.Estado.CERRADA
    cc.fecha_cierre = datetime.date.today()
    cc.save(update_fields=['estado', 'fecha_cierre', 'updated_at'])
```

Como segunda comprobación de integridad, sustituir el queryset del generador:

```python
cuentas = CuentaCorriente.objects.filter(
    estado=CuentaCorriente.Estado.ACTIVA,
    socio_titular__activo=1,
).select_related('socio_titular')
```

Verificación recomendada: inyectar un fallo sintético en `CuentaCorriente.save` en una BD de prueba y comprobar rollback de `Socios.activo`, ausencia de log de baja exitosa y ausencia de cuotas para socios no activos. Auditar/conciliar cuentas existentes que tengan `estado='ACTIVA'` con titular no activo después de aplicar la corrección.

## Observaciones no elevadas a hallazgo principal

- Los usos `mark_safe`/`|safe` revisados en diagnósticos y gráficos interpolan constantes, fechas o números. No se encontró un flujo confirmado de entrada textual controlada por el atacante a esos sinks.
- Los endpoints personalizados del admin están envueltos en `admin_site.admin_view`; aplicar saldo y resumen mensual comprueban explícitamente sus permisos. Los formularios sensibles revisados incluyen CSRF. No se reporta ausencia general de CSRF.
- `services/pagos.py:64-85` no recalcula habilitación después de revertir, y `services/socios.py` no recalcula después de baja. Se podría conservar un `estado_habilitacion=HABILITADO` obsoleto. El código contiene consultas y presentación del estado; no se encontró en el alcance revisado un control físico o autorización digital que lo use para conceder acceso. Tratar impacto de acceso como condicional; corregir recalculando dentro de las transacciones sobre todas las personas de la cuenta.
- `services/habilitacion.py:30-44` captura cualquier error al comprobar deuda y continúa a decidir HABILITADO. A10 potencial de fail-open: con un error de consulta y condiciones personales favorables, se devuelve habilitado. No se identificó un modo independiente de inducir ese error desde entradas sin aprovechar problemas ya reportados. Recomendable propagar errores operativos y evitar guardar estados nuevos cuando no se puede consultar la deuda.
