# Club Amandayé Ipeguá

**Plataforma de gestión del club y consulta de condiciones meteorológicas en Paysandú.**

Reúne la inscripción de socios, la administración de cuentas corrientes y cobranzas,
y una página pública con observaciones de estaciones locales y pronóstico. La web
pública está construida con Vue; la administración interna utiliza Django Admin y
una API con permisos por operación.

[Inicio rápido](#inicio-rápido) · [Documentación](docs/README.md) ·
[Arquitectura](docs/ARCHITECTURE.md) · [Contribuir](CONTRIBUTING.md) ·
[Seguridad](SECURITY.md)

## Funcionalidades

| Área | Qué permite hacer |
| --- | --- |
| Inscripciones y socios | Recibir solicitudes públicas, administrar personas y gestionar aprobación, baja y habilitación. |
| Cuentas y cobranzas | Registrar cargos y pagos, aplicar pagos, consultar saldos y reportes, generar cuotas y conservar auditoría de anulaciones y reversiones. |
| Acceso del personal | Asignar permisos mediante los grupos Administrador, Comision Directiva, Secretaria y Tesoreria. |
| Condiciones del río | Consultar temperatura, viento, presión y lluvia de estaciones locales, su antigüedad y un pronóstico independiente de Open-Meteo. |

### Estado de la integración meteorológica

Esta rama, `codex/condiciones-rio-scraping`, incorpora lectura provisional de las
páginas públicas de Ecowitt y Weather Underground mientras se obtienen las claves
de sus API. El modo `auto` elige la API cuando la estación tiene todas sus
credenciales y, en caso contrario, su página pública. La disponibilidad depende
de cada fuente; la interfaz identifica datos antiguos y estaciones sin conexión.

La página muestra **información meteorológica**: todavía no integra altura del río,
corrientes ni una evaluación de aptitud para navegar. Ver
[fuentes, configuración y límites](docs/CONDITIONS.md).

## Tecnologías

| Componente | Tecnología |
| --- | --- |
| Backend | Python 3.12, Django 5.2 LTS, Django REST Framework |
| Frontend | Vue 3, TypeScript, Vite 7, Tailwind CSS 4; imágenes con Node 24 |
| Datos y caché | MySQL 8.4, Redis |
| Autenticación | Sesiones y CSRF en el administrador; JWT en la API privada |
| Producción | Docker Compose, Gunicorn, WhiteNoise y Caddy con HTTPS |
| Pruebas | Django, runner de Node y MySQL desechable para concurrencia |

Las dependencias resueltas están en
[`requirements.txt`](amandaye_backend/requirements.txt) y
[`package-lock.json`](amandaye_frontend/package-lock.json).

## Inicio rápido

### Requisitos

- Git, Docker con contenedores Linux y Docker Compose v2.
- Python 3.12 para generar secretos; este paso usa solo la biblioteca estándar.
- Acceso a Internet para descargar imágenes y dependencias. Las fuentes
  meteorológicas también requieren conexión desde el backend.

### Primera instalación de desarrollo

Los ejemplos usan **PowerShell** y preparan una base nueva. Si ya hay datos que
conservar, seguir primero [migración de una instalación existente](docs/DEPLOYMENT.md#migrar-una-instalación-con-datos-existentes).

```powershell
git clone --branch codex/condiciones-rio-scraping https://github.com/danilopezyejas/amandaye.git
Set-Location amandaye

$env:AMANDAYE_SECRETS_DIR = (Join-Path (Get-Location) 'secrets/development')
py -3.12 scripts/bootstrap_secrets.py --directory secrets/development

docker compose -f docker-compose.dev.yml config --quiet
docker compose -f docker-compose.dev.yml build --pull
docker compose -f docker-compose.dev.yml up -d db redis
docker compose -f docker-compose.dev.yml run --rm backend python manage.py migrate --noinput
docker compose -f docker-compose.dev.yml run --rm backend python manage.py setup_roles
docker compose -f docker-compose.dev.yml run --rm backend python manage.py createsuperuser
docker compose -f docker-compose.dev.yml up -d
```

Si ya tenés el repositorio, empezar desde su raíz en el paso de configuración de
secretos. Ejecutar el generador con la misma cuenta que utiliza Docker Desktop;
conserva los valores existentes. En Linux/macOS, ver las
[adaptaciones de comandos](docs/DEVELOPMENT.md#linux-y-macos).

### Accesos locales

| Acceso | Dirección |
| --- | --- |
| Página principal e inscripción | [127.0.0.1:5173](http://127.0.0.1:5173/) |
| Condiciones del río | [127.0.0.1:5173/condiciones-del-rio](http://127.0.0.1:5173/condiciones-del-rio) |
| Administración | [127.0.0.1:5173/admin/](http://127.0.0.1:5173/admin/) |
| API ambiental pública | [127.0.0.1:5173/api/conditions/](http://127.0.0.1:5173/api/conditions/) |

La portada incluye un enlace a **Condiciones del río**. MySQL y Redis quedan dentro
de Docker. La primera cuenta administrativa se crea de forma interactiva; no hay
una contraseña predeterminada. Antes de operar cobranzas, configurar conceptos e
importes según la [puesta en marcha funcional](docs/DEVELOPMENT.md#puesta-en-marcha-funcional).

## Organización del repositorio

```text
amandaye_backend/
├── amandaye_backend/     # Configuración Django y controles de seguridad
└── apps/
    ├── usuarios/        # Socios, personas, solicitudes y habilitación
    ├── cobranzas/       # Cuentas, cargos, pagos, cuotas y auditoría
    └── conditions/      # Proveedores, normalización, caché y consolidación
amandaye_frontend/       # Web pública, formularios y página meteorológica
docker/                 # Imágenes, entrypoint y gateway Caddy
scripts/                # Preparación de secretos
docs/                   # Guías técnicas y operativas
```

## Documentación

| Para… | Consultar |
| --- | --- |
| Desarrollar, ejecutar pruebas y resolver problemas locales | [Desarrollo](docs/DEVELOPMENT.md) |
| Entender módulos, flujos y responsabilidades | [Arquitectura](docs/ARCHITECTURE.md) |
| Integrar clientes y revisar permisos de endpoints | [API](docs/API.md) |
| Configurar estaciones y pronóstico | [Condiciones del río](docs/CONDITIONS.md) |
| Publicar, migrar datos y operar el servicio | [Despliegue](docs/DEPLOYMENT.md) |
| Proponer cambios | [Contribución](CONTRIBUTING.md) |
| Administrar accesos, secretos e incidentes | [Seguridad](SECURITY.md) |

El [índice de documentación](docs/README.md) distingue las guías vigentes de las
notas históricas de implementación.
