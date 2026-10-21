# Gestión diaria

La primera entrega para Secretaría y Tesorería agrega un flujo interno sobre el
administrador de Django. No reemplaza los servicios financieros existentes: las
escrituras continúan pasando por sus permisos, transacciones, auditoría y reglas
de bloqueo.

**Versión documentada:** hitos 1–3 publicados en
`codex/gestion-secretaria-tesoreria`; hito 3 en `cdcedd8` (21 de octubre de 2026).
La instalación de desarrollo de esa entrega se verificó el 20 de octubre.

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

## Panel de pendientes

Cada lista tiene páginas independientes de 25 registros. Los conteos incluyen todos
los resultados de los filtros vigentes; los enlaces de paginación conservan los filtros
y las páginas de las otras listas. **Limpiar filtros** vuelve a la consulta inicial.

- **Solicitudes:** pendientes de revisión, con filtros por número de socio y rango
  de fecha de solicitud; accesos a la ficha y al formulario administrativo.
- **Pagos con saldo:** importe disponible después de descontar aplicaciones activas.
  Se puede distinguir **anticipo intencional**, **pendiente de aplicación** y
  **sin clasificar**. Los pagos antiguos sin clasificación pertenecen a esta última
  categoría. **Aplicar saldo** abre el flujo del hito 2 cuando el operador tiene permisos.
- **Deuda vencida:** cargos pendientes o parciales con vencimiento anterior a hoy y
  saldo positivo. Descuenta aplicaciones activas, excluye cargos anulados y permite
  limitar la fecha de vencimiento. No compensa automáticamente anticipos con deuda.
- **Habilitaciones:** por defecto incluye estados registrados **No habilitado** y
  **Suspendido**; permite elegir otro estado o **Todos los estados** y número de socio.

Un filtro inválido muestra el error y deja las listas vacías hasta corregirlo.
Los permisos controlan tanto las listas como sus conteos, filtros y acciones.

### Motivos de habilitación

El panel, la ficha y el administrador de Personas comparten la misma evaluación
que utilizan los servicios de recálculo. Muestran el estado registrado, su última
fecha de cálculo y la evaluación actual con motivos: datos faltantes, estado del
socio, cuota de temporada, edad, antigüedad, aprobación del profesor, aval o deuda.
Se conservan las reglas existentes y la precedencia de revocación y suspensión.
La evaluación utiliza la fecha local del club.

Consultar estas pantallas **no guarda el estado calculado**. Cuando difiere del
registrado se indica expresamente. El filtro usa el estado registrado: para revisar
personas previamente habilitadas, seleccionar **Todos los estados**. El recálculo
periódico sigue pendiente en P09.

Los motivos requieren simultáneamente `usuarios.view_socios`,
`usuarios.view_personas` y `cobranzas.view_cuentacorriente`, porque pueden revelar
situación financiera. Sin ellos solo se muestra la información permitida. Edad y
antigüedad se distinguen de las aprobaciones que puede gestionar un operador; los
accesos a estas últimas respetan sus permisos de edición y alta correspondientes.

El hito 3 no agrega migraciones ni requiere ejecutar `setup_roles`.

## Ficha unificada

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

La versión inicial de Gestión agregó la migración `cobranzas.0009`, con las tablas de
comprobantes, intención del saldo y operaciones de cobro. Seguir el procedimiento
de [actualización y recuperación](DEPLOYMENT.md#actualizaciones-y-recuperación),
incluido el respaldo y la revisión de migraciones, antes de activarla en una base
existente. Arrancar el contenedor no aplica migraciones automáticamente.
Los hitos 2 y 3 no agregan migraciones; una instalación anterior debe revisar
también `usuarios.0010_eventosocio` del hito 1.

## Registrar un cobro

Desde una ficha con cuenta corriente se puede seleccionar **Registrar cobro**.

1. Ingresar fecha, importe, medio y referencia opcional; pulsar **Proponer distribución**.
2. Ajustar el importe de cada cargo. La sugerencia prioriza vencimiento, emisión y
   número; se puede dejar un cargo en cero para pagar otro posterior.
3. Si queda saldo sin aplicar, elegir **anticipo** o **pendiente de aplicación**.
4. Pulsar **Revisar distribución**. El resumen muestra importes definitivos y saldo
   restante. **Volver a ajustar** permite corregirlos sin registrar movimientos.
5. **Confirmar cobro y emitir comprobante** registra el pago y las aplicaciones
   en una transacción, conserva la intención del saldo y abre el PDF interno.

La pantalla muestra hasta los primeros 100 cargos pendientes por operación. Si hay
más, se puede continuar aplicando el saldo restante después. La confirmación tiene
una vigencia de 30 minutos y queda vinculada al operador, cuenta, pago y datos
revisados. Si cambia el saldo de un cargo incluido o del pago, se pide revisar otra
vez. Reenviar la misma confirmación no crea otro pago ni duplica aplicaciones.
Los importes negativos, excesivos o con más de dos decimales se rechazan.

## Aplicar el saldo de un pago existente

Desde **Pagos con saldo** en el panel, o la sección **Pagos** de una ficha, pulsar
**Aplicar saldo**. El recorrido permite ajustar la distribución, revisar y confirmar.
No se registra otro ingreso: se utiliza únicamente el saldo disponible del pago.
Al terminar se vuelve a la ficha, donde figuran las aplicaciones y su auditoría.
Un pago sin saldo muestra un aviso y no permite confirmar una nueva aplicación.

El comprobante ya emitido conserva su contenido original, incluso si se aplica
saldo posteriormente; el historial y la sección Aplicaciones muestran el movimiento
nuevo. Si un pago histórico todavía no tenía comprobante, se crea uno identificado
como **reconstruido**, con la información disponible al momento de la aplicación.

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
- `cobranzas.view_pago` para descargar comprobantes y utilizar ambos flujos;
- aplicar saldo requiere consulta de socio/cuenta/pago y `puede_aplicar_pago`,
  sin exigir `add_pago` porque no crea un ingreso nuevo.

La interfaz no concede permisos ni permite editar importes históricos. Los datos
de ejemplo de las pruebas son sintéticos y no representan socios reales.

## Próximos incrementos

La ficha, el cobro y el panel son la primera entrega vertical del plan de
[Gestión de Secretaría y Tesorería](../plans/gestion-secretaria-tesoreria.md).
Quedan pendientes el piloto y el recálculo periódico fiable de habilitaciones (P09).
Como mejoras posteriores se contemplan la conciliación de transferencias, vista previa de
emisión de cuotas, seguimiento de cobranzas, tarifas con vigencia y reportes.
