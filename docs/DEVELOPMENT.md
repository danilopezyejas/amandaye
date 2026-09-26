# Desarrollo

[Índice](README.md) · [Arquitectura](ARCHITECTURE.md) · [Contribución](../CONTRIBUTING.md)

## Entorno local con Docker

Para crear un entorno nuevo, seguir el [inicio rápido](../README.md#inicio-rápido).
El archivo `docker-compose.dev.yml` es independiente del de producción: usar siempre
`-f docker-compose.dev.yml`, sin combinarlos.

| Servicio | Ejecución local | Acceso desde el host |
| --- | --- | --- |
| Frontend | Vite con Node 24 | `127.0.0.1:5173` |
| Backend | Django con Python 3.12 y `runserver --noreload` | `127.0.0.1:8000` |
| Base de datos | MySQL 8.4 | Sin puerto publicado |
| Caché | Redis autenticado | Sin puerto publicado |

El proyecto Compose se llama `socios-amandaye-devsecure`. Los datos persisten en
sus volúmenes de desarrollo. Los secretos se toman de `secrets/development/` por
defecto o del directorio indicado en `AMANDAYE_SECRETS_DIR`.

El código se **copia al construir las imágenes**. Para reflejar cambios del host,
reconstruir los servicios afectados. Comandos desde la raíz:

```powershell
docker compose -f docker-compose.dev.yml up -d --build backend frontend
docker compose -f docker-compose.dev.yml ps
docker compose -f docker-compose.dev.yml logs --tail=100 backend frontend
```

Para detener los servicios conservando sus datos:

```powershell
docker compose -f docker-compose.dev.yml stop
```

Vite deriva las rutas del backend al contenedor `backend:8000`; el navegador sigue
usando el mismo origen. El destino se configura con `AMANDAYE_DEV_API_TARGET`, una
variable del servidor Vite. `127.0.0.1` dentro de un contenedor apunta a ese mismo
contenedor.

### Linux y macOS

Clonar la rama y entrar en la carpeta como indica el README, usando `cd amandaye`
en lugar de `Set-Location`. Preparar los secretos con Python 3.12:

```bash
export AMANDAYE_SECRETS_DIR="$PWD/secrets/development"
python3.12 scripts/bootstrap_secrets.py --directory secrets/development
```

Continuar con los mismos comandos `docker compose` del inicio rápido. Si el sistema
dispone de Python 3.12 como `python3`, puede utilizarse ese ejecutable. Para las
pruebas nativas de esta guía, sustituir `Set-Location` por `cd`, `py -3.12` por
`python3.12` y `.venv\Scripts\python.exe` por `.venv/bin/python`.

## Puesta en marcha funcional

Después de las migraciones y de crear la primera cuenta:

1. Entrar en `/admin/` con el superusuario creado durante la instalación.
2. Crear las cuentas del personal y asignar los grupos correspondientes. El acceso
   al administrador también requiere `is_staff`; pertenecer a un grupo no activa
   esa propiedad. Ver [roles y permisos](../SECURITY.md#roles-y-permisos).
3. Si la base es nueva, crear el catálogo inicial de conceptos:

   ```powershell
   docker compose -f docker-compose.dev.yml run --rm backend python manage.py seed_conceptos
   ```

4. Configurar los importes aprobados por el club. `seed_conceptos` crea conceptos
   faltantes por código y conserva los existentes; no define los importes necesarios
   para operar. La generación mensual exige importes positivos para `MATRICULA`,
   `CUOTA_INDIVIDUAL`, `CUOTA_FAMILIAR` y `CUOTA_TEMPORADA`.
5. Verificar una solicitud, su aprobación y un circuito de cobro con personas
   ficticias antes de trabajar con datos reales.

`setup_roles` reemplaza los permisos de los cuatro grupos que administra. Revisar
cualquier personalización antes de volver a ejecutarlo.

## Frontend nativo con recarga de cambios

Esta opción usa el backend de Docker y permite editar Vue sin reconstruir una
imagen. Requiere Node 24 y npm instalados en el host. Desde la raíz:

```powershell
docker compose -f docker-compose.dev.yml stop frontend
Set-Location amandaye_frontend
npm ci --ignore-scripts
npm run dev
```

Vite escucha en `127.0.0.1:5173` y utiliza `http://127.0.0.1:8000` como destino
predeterminado de su proxy. Mantener un solo frontend en el puerto 5173. Para volver
a Docker, detener Vite, regresar a la raíz y arrancar el servicio `frontend`.

## Pruebas locales aisladas

### Backend

Desde la raíz, con Python 3.12:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r amandaye_backend/requirements.txt
Set-Location amandaye_backend
..\.venv\Scripts\python.exe manage.py test --settings=amandaye_backend.settings_test --noinput
..\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run --settings=amandaye_backend.settings_test
```

`settings_test` usa SQLite en memoria, caché local y valores sintéticos; omite la
carga del `.env`. No requiere los secretos ni la base del entorno de desarrollo.
Las pruebas de exclusión mutua con MySQL se omiten en SQLite.

La instalación nativa de `mysqlclient` puede requerir herramientas de compilación
y bibliotecas cliente según el sistema. Como alternativa, con la imagen de backend
ya construida, ejecutar desde la raíz:

```powershell
docker compose -f docker-compose.dev.yml run --rm --no-deps backend python manage.py test --settings=amandaye_backend.settings_test --noinput
```

Para comprobar solo el módulo ambiental, añadir `apps.conditions` después de `test`.
Sus pruebas simulan las respuestas externas y no necesitan consultar estaciones reales.

### Frontend

En una terminal ubicada en `amandaye_frontend`, con Node 24:

```powershell
npm ci --ignore-scripts
npm test
npm exec -- vue-tsc --noEmit
npm run build
```

`npm test` usa el runner de Node. `build` ejecuta TypeScript y genera `dist/` con
Vite; `vue-tsc` comprueba además los componentes `.vue`. No hay un script de lint
configurado. `npm audit` sirve para revisar dependencias y requiere acceso al registro.

### Concurrencia con MySQL

Desde la raíz:

```powershell
docker compose -f docker-compose.test.yml build tests
docker compose -f docker-compose.test.yml run --rm tests
docker compose -f docker-compose.test.yml down
```

Este entorno independiente, `socios-amandaye-security-tests`, usa MySQL 8.4 con
almacenamiento temporal, sin puertos publicados ni volúmenes persistentes. No monta
secretos ni datos personales. Su contraseña sintética se limita a la base de pruebas.

`settings_test_mysql` exige un nombre de base con prefijo `test_amandaye_` y una
cuenta distinta de `root` y `amandaye_app`. Django vacía tablas durante la suite:
las variables `TEST_MYSQL_*` deben apuntar exclusivamente a una base desechable.

## Resolver problemas habituales

| Síntoma | Comprobación y solución |
| --- | --- |
| Los cambios no aparecen en Docker | Reconstruir el servicio afectado; no hay montaje del código del host. |
| El frontend no llega a la API | Usar `backend:8000` desde Vite en Docker y `127.0.0.1:8000` desde Vite nativo. Revisar los logs del backend. |
| Puerto 5173 ocupado | Detener el frontend Docker antes de ejecutar Vite nativo, o cerrar el proceso nativo antes de volver a Docker. |
| Error `Configure SECRET_KEY or SECRET_KEY_FILE` | Revisar el archivo Compose usado y los secretos. Un contenedor antiguo necesita recrearse con la configuración vigente. |
| Docker no puede leer los secretos en Windows | Ejecutar el generador con la cuenta que usa Docker Desktop; revisar las ACL según la guía de despliegue. |
| El sitio abre, pero `/admin/` rechaza al usuario | Comprobar que la cuenta esté activa, tenga `is_staff` y los permisos necesarios. |
| Una estación no entrega datos | Revisar `access_method`, código de error, fecha y modo configurado; ver [diagnóstico ambiental](CONDITIONS.md#endpoints-y-contrato). |

### Recuperar un entorno antiguo

Antes de reemplazar contenedores que contienen datos, identificar el servidor y el
volumen originales y verificar una copia lógica restaurable. Detener solo los
servicios web para liberar sus puertos; conservar la base original.

Preparar secretos e imágenes nuevos, iniciar únicamente `db redis`, restaurar la
copia en la base nueva y revisar `migrate --plan` antes de aplicar migraciones y
`setup_roles`. Validar recuentos, saldos y permisos antes de iniciar backend/frontend.
El [procedimiento de migración](DEPLOYMENT.md#migrar-una-instalación-con-datos-existentes)
detalla la transición entre versiones de MySQL y el tratamiento de credenciales.

Vite y `runserver` son herramientas de desarrollo. Para publicar el servicio,
seguir la [guía de despliegue](DEPLOYMENT.md).
