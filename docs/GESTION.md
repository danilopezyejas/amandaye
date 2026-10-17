# Gestión diaria

La primera entrega para Secretaría y Tesorería agrega un flujo interno sobre el
administrador de Django. No reemplaza los servicios financieros existentes: las
escrituras continúan pasando por sus permisos, transacciones, auditoría y reglas
de bloqueo.

## Acceso

En desarrollo, el acceso directo es
[Gestión diaria](http://localhost:8000/admin/gestion/). La portada pública de Vue
está en el puerto `5173`; las pantallas de Secretaría y Tesorería están dentro del
administrador de Django.

Con una cuenta administrativa autorizada, entrar a `/admin/` y pulsar **Abrir
Gestión diaria** en la tarjeta situada antes de la lista de módulos. También se
puede usar **Gestión diaria** desde la barra del administrador o abrir directamente
`/admin/gestion/`. La tarjeta y el enlace aparecen según los permisos existentes.
Si todavía no hay una sesión iniciada, el enlace abre el formulario de acceso y,
al ingresar, vuelve a la pantalla solicitada. Desde la portada pública se puede
entrar por **Acceder** y luego **Abrir Gestión diaria**. El panel muestra:

- solicitudes de socios pendientes;
- pagos que conservan saldo sin aplicar;
- cargos vencidos;
- habilitaciones que requieren revisión.

### Ficha unificada

En **Buscar socio o familiar** se puede ingresar número de socio, cédula o nombres
completos (incluidos familiares). Los homónimos conservan sus números de socio y
cada grupo aparece una sola vez. Buscar por datos de personas requiere también
`usuarios.view_personas`; sin ese permiso se permite número o cédula del titular.

Cada ficha reúne, según permisos:

- titular, familia, contacto y estado de habilitación con fecha del último cálculo;
- cuenta, deuda total, deuda vencida y pagos sin aplicar, sin compensarlos entre sí;
- todos los cargos, pagos, aplicaciones y reversiones, en páginas de 25 registros;
- embarcaciones y valor de percha registrado (no es gestión de ocupación);
- historial cronológico con fecha, operador, fuente, acción y referencia.

La paginación de cada sección conserva las otras páginas; los totales abarcan toda
la cuenta. La ficha ofrece accesos al administrador para editar datos con los
permisos existentes. Un titular vinculado a otro grupo se señala como inconsistente
y no se muestran sus datos personales como pertenecientes a esta familia.
Consultar la ficha no crea cuentas, aplica pagos ni recalcula habilitaciones.

El historial combina eventos administrativos del socio, transiciones registradas
en `EventoSocio` y movimientos atribuibles a su cuenta (cargos/anulaciones,
pagos, aplicaciones/reversiones, operaciones y comprobantes). Las fuentes mantienen
sus referencias; no se presenta una aplicación como otro ingreso de dinero.
Los comprobantes solo se muestran con `cobranzas.view_pago`.

**Cobertura histórica:** las nuevas transiciones guardan socio, actor y fecha en
su misma transacción. El legado `socios_cambios` se conserva intacto, pero no se
atribuye a un socio leyendo números en comentarios. No se infieren operadores
faltantes ni se incluyen notas libres, salud o llaves. El historial puede ser
incompleto antes de activar el registro vinculado; los cambios de personas no se
reasignan retrospectivamente a su grupo familiar actual.

### Activación del historial vinculado

El hito 1 agrega `usuarios.0010_eventosocio`, que crea una tabla e índice sin
reescribir registros existentes. Antes de instalar esta versión sobre una base
existente, respaldar y comprobar restauración, revisar `migrate --plan` y aplicar
la migración según [Despliegue](DEPLOYMENT.md#actualizaciones-y-recuperación).
No ejecutar `setup_roles`: la ficha conserva los permisos existentes.

Desde esta versión los servicios de solicitud, aprobación, rechazo, baja,
reactivación y cambio de cuota escriben en `EventoSocio`; `socios_cambios` queda
como legado conservado. No hay un editor genérico para los nuevos eventos.
Para retirar esta versión, conservar la tabla y la auditoría; volver a una imagen
anterior no permite seguir completando el nuevo historial vinculado.

### Si los cambios no aparecen en Docker

Iniciar o reiniciar `socios-amandaye-devsecure` reutiliza la imagen que ya existe.
Como el código se copia durante el build, una imagen anterior a Gestión no incluye
sus rutas ni el enlace del administrador. La actualización requiere reconstruir
el backend y recrear su contenedor.

Esta entrega también agrega la migración `cobranzas.0009`, con las tablas de
comprobantes, intención del saldo y operaciones de cobro. Seguir el procedimiento
de [actualización y recuperación](DEPLOYMENT.md#actualizaciones-y-recuperación),
incluido el respaldo y la revisión de migraciones, antes de activarla en una base
existente. Arrancar el contenedor no aplica migraciones automáticamente.

## Registrar un cobro

Desde una ficha con cuenta corriente se puede seleccionar **Registrar cobro**.

1. Ingresar fecha, importe, medio y referencia opcional.
2. Revisar la propuesta, que distribuye el importe entre cargos pendientes por
   vencimiento, emisión y número.
3. Si queda saldo sin aplicar, elegir **anticipo** o **pendiente de aplicación**.
4. Confirmar. El backend registra el pago, aplica los cargos seleccionados en una
   transacción, guarda la intención del saldo y emite un comprobante interno PDF.

La pantalla conserva una clave de idempotencia y una versión de la propuesta. Si
otra operación cambia la cuenta antes de confirmar, el backend rechaza la versión
vieja para que el operador revise nuevamente. Repetir la misma solicitud no crea
otro pago.

Los comprobantes son instantáneas inmutables del pago y sus aplicaciones. El club
y la moneda se configuran con `CLUB_NAME`, `CLUB_CURRENCY` y
`CLUB_RECEIPT_DETAILS`; por defecto la moneda es `UYU`.

## Permisos

El panel utiliza permisos existentes:

- `usuarios.view_socios` obligatorio para buscar y abrir fichas;
- `usuarios.view_personas` para familiares, contacto y embarcaciones;
- `cobranzas.view_cuentacorriente` para saldos, cargos y propuestas;
- `cobranzas.add_pago` y `cobranzas.puede_aplicar_pago` para usar el flujo de
  cobro (registrar y aplicar dentro de la misma operación);
- `cobranzas.view_pago` para descargar comprobantes.

La interfaz no concede permisos ni permite editar importes históricos. Los datos
de ejemplo de las pruebas son sintéticos y no representan socios reales.

## Próximos incrementos

La ficha, el cobro y el panel son la primera entrega vertical del plan de
[Gestión de Secretaría y Tesorería](../plans/gestion-secretaria-tesoreria.md).
Quedan como trabajo posterior la conciliación de transferencias, vista previa de
emisión de cuotas, seguimiento de cobranzas, tarifas con vigencia y reportes.
