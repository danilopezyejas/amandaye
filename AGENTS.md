# Trabajo en Amandayé

## Orientación y continuidad

- Este repositorio contiene Django/DRF, Vue/TypeScript, MySQL y Redis. El mapa de
  módulos está en [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
- Al retomar trabajo, leer [docs/CONTINUITY.md](docs/CONTINUITY.md) y comprobar rama,
  último commit y cambios locales. Las notas fechadas describen evidencia histórica;
  verificar el estado actual antes de operar servicios.
- Seguir el objetivo y las autorizaciones de la conversación. Las ideas pendientes
  del registro no autorizan su implementación. Conservar cambios ajenos al encargo.
- Resolver decisiones rutinarias dentro del alcance y continuar el trabajo ya
  autorizado. Pedir aclaración solo cuando falte información material; no agregar
  aprobaciones por una plantilla genérica de ECC.
- Al cerrar una implementación sustancial o dejarla pendiente, actualizar el registro
  con resultado, comprobaciones, limitaciones y próximo paso. No hace falta modificar
  archivos por responder una consulta informativa.

## Verificación

Usar [amandaye-verification](.agents/skills/amandaye-verification/SKILL.md) al verificar
cambios de este proyecto. Los comandos de instalación y pruebas se mantienen en
[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

- Backend: `.venv` con Python 3.12 y `amandaye_backend.settings_test`; SQLite en
  memoria para la suite habitual. MySQL desechable para comprobar concurrencia.
- Frontend: Node 24, `npm test`, `npm exec -- vue-tsc --noEmit` y `npm run build`.
  No existe `npm run lint`; no suponer que el proyecto usa pytest, Ruff o Black.
- Solo documentación o instrucciones: verificar enlaces, sintaxis y consistencia
  con el código. No reconstruir servicios ni ejecutar suites ajenas al cambio.
- Distinguir pruebas ejecutadas, omitidas y bloqueadas. No repetir verificaciones
  satisfactorias sin cambios o evidencia que justifique hacerlo.

## Reglas del dominio

- Las escrituras de socios y cobranzas pasan por los servicios de
  `apps/usuarios/services/` y `apps/cobranzas/services/`. Mantener permisos del
  operador, transacciones y auditoría; la interfaz no reemplaza estas comprobaciones.
- Usar `Decimal` para importes. Preservar las invariantes de saldo y las anulaciones
  y reversiones explícitas; no editar importes históricos mediante CRUD genérico.
- Conservar el orden de bloqueos de los servicios: los escritores financieros usan
  Cuenta → Pago → Cargo → Aplicación; transiciones y cuotas bloquean Socio antes
  de Cuenta. Revisar el servicio concreto antes de cambiar una transacción.
- `setup_roles` reemplaza los permisos de sus grupos. Generar cuotas, aprobar socios,
  recalcular habilitaciones y migrar son operaciones con efectos sobre datos reales;
  no utilizarlas como comprobaciones sobre la instalación del usuario.
- En condiciones meteorológicas, preservar fuente, unidades, fechas y antigüedad;
  separar observaciones y pronóstico. Datos ausentes son `null`. El scraping es
  provisional y no obtiene claves de páginas externas. Ver [CONDITIONS.md](docs/CONDITIONS.md).

## Entornos y datos

- Desarrollo: `docker compose -f docker-compose.dev.yml`. Pruebas MySQL:
  `docker compose -f docker-compose.test.yml`. El Compose sin `-f` es producción.
- El código de desarrollo se copia durante el build; una edición del host no
  actualiza por sí sola los contenedores. Recrear servicios solo si la tarea lo requiere.
- Conservar los volúmenes y bases existentes. Las migraciones son explícitas y
  requieren el procedimiento de [despliegue](docs/DEPLOYMENT.md).
- No cargar ni imprimir secretos para verificar su presencia. Excluir datos de
  socios, `.env`, SQL, respuestas externas con claves y respaldos de commits,
  memorias de agentes y reportes. Usar fixtures sintéticos.
- Evitar búsquedas recursivas sobre `venv/`, `.venv/`, `node_modules/`, `.local/`
  y `secrets/`. El `venv/` histórico no debe limpiarse como tarea secundaria.

## Uso de ECC

ECC aporta procedimientos de referencia; adaptar herramientas, rutas y pruebas al
proyecto. Cargar solo la skill pertinente y respetar las instrucciones de la sesión.
La selección para Amandayé y el estado de instalación están en
[docs/ECC_INTEGRATION.md](docs/ECC_INTEGRATION.md). Una revisión de código no implica
rotar secretos, aplicar migraciones, publicar ni cambiar políticas de permisos.
