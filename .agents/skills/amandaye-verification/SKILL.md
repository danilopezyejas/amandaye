---
name: amandaye-verification
description: Verificar cambios del proyecto Club Amandayé Ipeguá antes de entregarlos, revisarlos o publicarlos, seleccionando pruebas de Django, Vue y MySQL aislado según el alcance. Usar también para validar cambios de documentación del repositorio.
metadata:
  project: socios_amandaye
---

# Verificación de Amandayé

Trabajar desde la raíz del repositorio. La preparación del entorno y las variantes
de comandos están en [Desarrollo](../../../docs/DEVELOPMENT.md); consultar solo
la sección necesaria. Esta ruta corresponde a la ubicación instalada de la skill
en `.agents/skills/amandaye-verification/`.

## Seleccionar las comprobaciones

Revisar el diff y el objetivo del usuario. Si hay cambios sin commit, incluirlos;
si se revisa un commit o una rama, usar la referencia solicitada. Identificar cambios
ajenos para no adjudicarlos a esta tarea ni modificarlos.

| Alcance | Comprobar |
| --- | --- |
| Documentación, AGENTS o skills de instrucciones | Enlaces locales y anclas, comandos contra su fuente, YAML cuando exista, `git diff --check`. |
| Backend | Pruebas del módulo afectado; suite completa si cambian reglas compartidas, permisos o contratos; migraciones pendientes si cambian modelos. |
| Cobranzas o concurrencia | Añadir MySQL desechable para verificar bloqueos, reversiones y saldos. SQLite no valida exclusión mutua. |
| Frontend | Pruebas de Node, tipos Vue, build y comprobación visual si cambia un flujo visible. |
| Condiciones del río | Fechas por sensor, unidades, datos ausentes, antigüedad, errores y modo API/página pública con fixtures. |
| Compose o despliegue | Sintaxis de los archivos afectados y comprobación del entorno dentro del alcance autorizado. |

## Comandos del proyecto

Backend, desde `amandaye_backend`, con `.venv` ya preparado:

```powershell
..\.venv\Scripts\python.exe manage.py test --settings=amandaye_backend.settings_test --noinput
..\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run --settings=amandaye_backend.settings_test
```

Para una suite enfocada, insertar el módulo después de `test`, por ejemplo
`apps.conditions`. En POSIX utilizar `../.venv/bin/python`. No ejecutar tests con
los settings de producción ni crear usuarios o aplicar migraciones en la base del
usuario para completar una verificación. Las migraciones durante una suite se
limitan a su base sintética.

Frontend, desde `amandaye_frontend`, con dependencias ya instaladas:

```powershell
npm test
npm exec -- vue-tsc --noEmit
npm run build
```

Si faltan dependencias, seguir la instalación reproducible de Desarrollo. No agregar
pytest, lint, cobertura o cambios automáticos de dependencias para satisfacer una
plantilla de ECC. Usar `npm ci --ignore-scripts` cuando sea necesaria la instalación.

Concurrencia, desde la raíz y con Docker disponible:

```powershell
docker compose -f docker-compose.test.yml build tests
docker compose -f docker-compose.test.yml run --rm tests
docker compose -f docker-compose.test.yml down
```

Este archivo configura exclusivamente un MySQL temporal. Revisarlo antes de usarlo
si fue modificado; no sustituirlo por el Compose de desarrollo o producción.
Si se inicia este entorno para la prueba, detenerlo al terminar, también ante fallo.
Conservar la salida y el código de error de la prueba aunque la limpieza tenga éxito.

Para validar Compose usar `config --quiet`; la variante de producción requiere
`SITE_ADDRESS` y `DJANGO_ALLOWED_HOSTS`. Para una comprobación estática pueden usarse
valores sintéticos como `club.example` solo en ese proceso. No imprimir configuración
resuelta con secretos ni iniciar producción para validar la sintaxis.

## Interpretar y cerrar

- Conservar el código de salida original. En PowerShell, comprobar `$LASTEXITCODE`
  después de cada comando nativo; un comando posterior exitoso no valida el anterior.
- Tratar fallos de entorno por separado de fallos de la aplicación. Si una prueba
  relevante no puede ejecutarse, registrar el motivo y completar las independientes.
- Revisar el diff final y comunicar qué se comprobó, resultado y límites. No convertir
  una validación de comandos en una prueba funcional, ni datos históricos en evidencia actual.
- Actualizar [CONTINUITY.md](../../../docs/CONTINUITY.md) cuando corresponda al cierre
  o traspaso de una implementación sustancial. No hay obligación de commit, push o
  despliegue por invocar esta skill; seguir el alcance autorizado en la conversación.
