# Club Amandayé Ipeguá

Gestión de socios, solicitudes, cuentas corrientes y cobranzas con Django 5.2 LTS, Django REST Framework y Vue 3/TypeScript. El administrador usa sesiones Django y CSRF; la API privada usa JWT con permisos por operación. La inscripción pública acepta solicitudes pendientes y devuelve una confirmación mínima.

## Instalar y ejecutar

Seguir [Despliegue y desarrollo](docs/DEPLOYMENT.md). Incluye creación de secretos, instalación nueva, migración de datos anteriores y comandos de desarrollo.

- Producción: `docker-compose.yml`, Gunicorn y frontend compilado detrás de Caddy con HTTPS; MySQL 8.4 y Redis permanecen en redes internas.
- Desarrollo: `docker-compose.dev.yml` independiente, backend en `127.0.0.1:8000` y frontend en `127.0.0.1:5173`. Docker incluye Python 3.12 y Node 24; también se puede ejecutar Vite de forma nativa según la guía.
- Secretos: `python scripts/bootstrap_secrets.py` con Python 3.12. El generador conserva las credenciales existentes. Las configuraciones inseguras anteriores ya no permiten iniciar el backend.

Los comandos no importan el SQL anterior ni modifican automáticamente una base existente. La migración y la provisión de usuarios se ejecutan expresamente según la guía.

## Pruebas locales aisladas

Desde la raíz, con Python 3.12 y Node compatibles instalados:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r amandaye_backend/requirements.txt
Set-Location amandaye_backend
..\.venv\Scripts\python.exe manage.py test --settings=amandaye_backend.settings_test --noinput
..\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run --settings=amandaye_backend.settings_test
Set-Location ../amandaye_frontend
npm ci --ignore-scripts
npm test
npm run build
npm audit
```

La configuración de pruebas usa credenciales sintéticas y SQLite en memoria: no lee el `.env` ni la base personal. Las pruebas de concurrencia requieren MySQL/InnoDB y se omiten en SQLite; ver la guía para ejecutarlas sobre una base desechable.

## Estructura

- `amandaye_backend/apps/usuarios/`: socios, personas, estados, permisos y solicitudes.
- `amandaye_backend/apps/cobranzas/`: cargos, pagos, aplicaciones, cuotas y auditoría.
- `amandaye_backend/amandaye_backend/security/`: bloqueo de login, respuestas seguras y pruebas de configuración.
- `amandaye_frontend/src/`: interfaz Vue, transporte autenticado y formularios.
- `docker/`, `scripts/`, `docs/`: ejecución y operación.
- `amandaye_backend/apps/conditions/`: observaciones locales, consolidación y pronóstico;
  [configuración, API y pruebas](docs/CONDITIONS.md). Página `/condiciones-del-rio`.

Los movimientos financieros se realizan mediante servicios transaccionales que verifican al operador. Los importes y los vínculos de movimientos existentes no se editan ni se eliminan desde formularios genéricos; las reversiones y anulaciones conservan auditoría. Directiva controla las transiciones de socios y los ajustes de cuota.

Los secretos, datos personales locales y archivos generados quedan excluidos de Git y del contexto Docker. Esta exclusión no borra versiones anteriores del historial compartido.
