# Continuidad del proyecto

[Índice](README.md) · [Instrucciones de trabajo](../AGENTS.md) · [ECC](ECC_INTEGRATION.md)

Este registro conserva decisiones y próximos pasos entre sesiones. Comprobar siempre
`git status`, rama y commits: los estados del servidor y las fuentes externas deben
verificarse de nuevo cuando sean relevantes. Mantenerlo breve y sin datos personales,
secretos, volcados de conversaciones ni logs completos.

## Estado de referencia — 2026-09-30

- Rama de trabajo: `codex/condiciones-rio-scraping`.
- Scraping provisional implementado en `4a00982`; documentación reorganizada en
  `f3f91a7`. Ambos commits se publicaron en esa rama.
- La página `/condiciones-del-rio` tiene acceso desde la portada. Combina observaciones
  locales con pronóstico independiente; no evalúa navegación ni muestra altura del río.
- `CONDITIONS_STATION_MODE=auto` usa API cuando hay credenciales completas para la
  estación y página pública cuando faltan. Una API configurada que falla no cambia
  automáticamente a scraping.
- Las lecturas en vivo y pruebas funcionales históricas están en
  [CONDITIONS_HANDOFF.md](CONDITIONS_HANDOFF.md). No interpretar sus fechas ni estados
  de estaciones como resultados actuales.

## Trabajo de esta entrega

ECC 2.2.2 está instalado y habilitado en el perfil local de Codex. Se incorporaron
`AGENTS.md`, la skill `amandaye-verification`, la guía de integración y este registro.
Ver la revisión instalada y sus límites en [ECC_INTEGRATION.md](ECC_INTEGRATION.md).

Comprobaciones del 30 de septiembre de 2026:

- Diagnóstico de caché de ECC satisfactorio; las skills aparecen en el catálogo de
  la sesión. El manifiesto de hooks existe y contiene JSON válido.
- Skill local aprobada por el validador oficial; metadatos de interfaz válidos.
- 131 enlaces y anclas locales revisados en 16 documentos, sin errores.
- Seis bloques PowerShell de los archivos de integración analizados, sin errores
  de sintaxis; comandos contrastados con las fuentes del proyecto y la CLI.

El alcance es documentación e instrucciones: no se ejecutaron suites funcionales
del backend o frontend ni se modificaron datos o servicios del club. La continuidad
queda disponible mediante los archivos versionados; no depende de autorizar hooks
de ECC. Para retomar, consultar el historial de la rama y elegir el próximo cambio
con el usuario; las ideas de abajo siguen pendientes de solicitud.

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

**Ideas conversadas, sin implementación solicitada:** ficha unificada del socio,
cobro simplificado y panel de tareas pendientes; después, portal del socio,
conciliación de transferencias, tarifas por vigencia y gestión de perchas o reservas.
Retomar solo la funcionalidad que el usuario elija.

## Cómo actualizar este registro

Al cerrar una implementación sustancial o preparar un traspaso, reemplazar el estado
obsoleto y anotar fecha, objetivo, rama o commit conocido, cambios completados,
verificaciones realizadas y limitaciones. Dejar el próximo paso concreto y distinguir
lo autorizado de lo propuesto. No escribir el hash del propio commit antes de que exista.
