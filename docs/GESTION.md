# Gestión diaria

La primera entrega para Secretaría y Tesorería agrega un flujo interno sobre el
administrador de Django. No reemplaza los servicios financieros existentes: las
escrituras continúan pasando por sus permisos, transacciones, auditoría y reglas
de bloqueo.

## Acceso

Con una cuenta administrativa autorizada, abrir `/admin/gestion/` o usar **Gestión
diaria** desde la barra del administrador. El panel muestra:

- solicitudes de socios pendientes;
- pagos que conservan saldo sin aplicar;
- cargos vencidos;
- habilitaciones que requieren revisión.

La búsqueda está en `/admin/gestion/socios/`. Cada ficha unifica, según los
permisos de la persona operadora, datos del socio, grupo familiar, contacto,
cuenta corriente, cargos, pagos, embarcaciones e historial administrativo.

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

- `usuarios.view_socios` para buscar y abrir fichas;
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
