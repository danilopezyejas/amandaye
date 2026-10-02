# Continuidad del proyecto

[Índice](README.md) · [Instrucciones de trabajo](../AGENTS.md) · [ECC](ECC_INTEGRATION.md)

Este registro conserva decisiones y próximos pasos entre sesiones. Comprobar siempre
`git status`, rama y commits: los estados del servidor y las fuentes externas deben
verificarse de nuevo cuando sean relevantes. Mantenerlo breve y sin datos personales,
secretos, volcados de conversaciones ni logs completos.

## Estado de referencia — 2026-10-02

- Rama de trabajo: `codex/gestion-secretaria-tesoreria`.
- Scraping provisional implementado en `4a00982`; documentación reorganizada en
  `f3f91a7`. Ambos commits se publicaron en esa rama.
- ECC y las instrucciones de proyecto se incorporaron en `22d4148`, también publicado.
- La página `/condiciones-del-rio` tiene acceso desde la portada. Combina observaciones
  locales con pronóstico independiente; no evalúa navegación ni muestra altura del río.
- `CONDITIONS_STATION_MODE=auto` usa API cuando hay credenciales completas para la
  estación y página pública cuando faltan. Una API configurada que falla no cambia
  automáticamente a scraping.
- Las lecturas en vivo y pruebas funcionales históricas están en
  [CONDITIONS_HANDOFF.md](CONDITIONS_HANDOFF.md). No interpretar sus fechas ni estados
  de estaciones como resultados actuales.

## Trabajo actual — primera entrega de Gestión

El usuario autorizó implementar la primera entrega del
[plan de Gestión](../plans/gestion-secretaria-tesoreria.md) en esta rama. El panel
está disponible en `/admin/gestion/` y usa Django con los permisos existentes.

Se implementó:

- panel de pendientes para solicitudes, pagos con saldo, deudas vencidas y
  habilitaciones;
- búsqueda de socios y ficha unificada con datos familiares, cuenta corriente,
  embarcaciones e historial administrativo según permisos;
- flujo de cobro en dos pasos, con propuesta por vencimiento/emisión/número,
  revisión de saldo restante, idempotencia, control de versión y comprobante PDF;
- registros aditivos de operación, intención del saldo y comprobante inmutable;
- configuración de `CLUB_NAME`, `CLUB_CURRENCY` y `CLUB_RECEIPT_DETAILS`.

La moneda elegida para esta entrega es `UYU` por defecto y los datos del club del
recibo se pueden cambiar por entorno. No se operó sobre datos reales.

Verificaciones realizadas el 2026-10-02:

- `manage.py check --settings=amandaye_backend.settings_test`;
- `manage.py makemigrations --check --dry-run`;
- 10 pruebas dirigidas de Gestión y cobros, incluyendo revisión/confirmación de la
  pantalla y generación del PDF;
- `git diff --check` (solo informó conversiones de finales de línea de Windows).

La siguiente etapa todavía no está implementada: emisión de cuotas con vista previa,
tarifas con vigencia, seguimiento de cobranzas, conciliación bancaria, portal del
socio y tareas periódicas de habilitación. El plan conserva sus contratos y criterios
para retomarlos sin mezclar datos ni permisos.

La entrega previa de ECC 2.2.2 pasó su diagnóstico de caché, validación de skill y
comprobaciones de documentación el 30 de septiembre. Ver detalles y límites en
[ECC_INTEGRATION.md](ECC_INTEGRATION.md); la continuidad mediante estos archivos no
depende de autorizar hooks del plugin.

## Decisiones que deben conservarse

- Las reglas financieras viven en servicios transaccionales y verifican permisos.
  Las correcciones preservan auditoría; los importes se calculan con `Decimal`.
- El desarrollo, la producción y las pruebas MySQL usan archivos Compose separados.
  Las bases existentes no son entornos desechables para validar cambios.
- La verificación se selecciona por alcance. Las instrucciones genéricas de ECC se
  adaptan a los runners y dependencias existentes.
- Las claves de estaciones se configuran en el backend cuando las aporte el responsable.
  El modo `api` permite desactivar la lectura de páginas públicas.

## Pendientes e ideas

**Integración pendiente:** disponer de credenciales propias de Ecowitt y Weather
Underground y validar observaciones reales de sus API. La disponibilidad de las
estaciones debe comprobarse en ese momento.

**Gestión:** primera entrega implementada en la rama indicada. Portal del socio,
conciliación, perchas, reservas, préstamos y reportes quedan como evolución posterior.
Antes del despliegue se debe ejecutar el procedimiento de migración del proyecto y
configurar los datos reales del club mediante variables de entorno.

## Cómo actualizar este registro

Al cerrar una implementación sustancial o preparar un traspaso, reemplazar el estado
obsoleto y anotar fecha, objetivo, rama o commit conocido, cambios completados,
verificaciones realizadas y limitaciones. Dejar el próximo paso concreto y distinguir
lo autorizado de lo propuesto. No escribir el hash del propio commit antes de que exista.
