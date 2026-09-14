# Despliegue y desarrollo después de las correcciones de seguridad

La configuración principal ejecuta Django con Gunicorn y el frontend compilado detrás de Caddy con HTTPS. MySQL 8.4 y Redis autenticado quedan en una red interna sin puertos publicados. La base anterior, su volumen y sus archivos locales no se migran ni se eliminan automáticamente.

## Preparar una instalación nueva

Se requiere Docker Engine/Desktop con contenedores Linux y Compose v2, un dominio controlado por el club y sus registros DNS apuntando al servidor. Los puertos públicos 80 y 443 deben llegar al gateway para obtener y renovar certificados. Python 3.12 o superior permite ejecutar el generador de secretos. El build usa Python 3.12 y Node 24.

Ejecutar desde la raíz del proyecto. Estos ejemplos usan PowerShell; sustituir `socios.ejemplo.org` por el dominio real, sin esquema, puerto ni ruta:

```powershell
py -3.12 scripts/bootstrap_secrets.py
$env:SITE_ADDRESS = 'socios.ejemplo.org'
$env:DJANGO_ALLOWED_HOSTS = 'socios.ejemplo.org'
docker compose config --quiet
docker compose build --pull
docker compose up -d db redis
docker compose run --rm backend python manage.py migrate --noinput
docker compose run --rm backend python manage.py setup_roles
docker compose run --rm backend python manage.py createsuperuser
docker compose run --rm backend python manage.py check --deploy
docker compose up -d backend gateway
```

En Linux usar `python3 scripts/bootstrap_secrets.py` y `export SITE_ADDRESS=socios.ejemplo.org`, `export DJANGO_ALLOWED_HOSTS=socios.ejemplo.org`. Los valores del dominio deben persistirse en la configuración del servicio que ejecuta Compose. Se pueden guardar en un archivo de configuración fuera de Git; las contraseñas no deben convertirse en variables de entorno ni argumentos de comandos.

`migrate` se ejecuta explícitamente: el arranque normal no modifica el esquema. El entrypoint ejecuta `collectstatic` antes de Gunicorn y WhiteNoise sirve `/static/`. `setup_roles` crea o actualiza los permisos; luego asignar los grupos Secretaría, Tesorería y Directiva a los usuarios que correspondan desde el administrador. La creación de usuarios es interactiva y no trae contraseñas predeterminadas.

El proyecto Compose de producción se llama `socios-amandaye-secure` y su volumen de datos es `mysql_secure_data`, con el prefijo del proyecto. No reutiliza el volumen anterior `mysql_data`. Las imágenes base siguen ramas mantenidas; actualizar con `build --pull`/`pull`, auditar y probar antes de promover cada versión. Para despliegues reproducibles aprobados, registrar también los digest de las imágenes usadas.

## Secretos y límites de confianza

En Windows, ejecutar el generador desde la misma cuenta que ejecuta Docker Desktop. Una cuenta aislada de herramientas puede tener un SID distinto: si crea los secretos, Docker no podrá montarlos hasta que se transfiera su acceso al usuario del despliegue. No resolver un error de acceso concediendo lectura a `Everyone` o `Users`. En este espacio de trabajo los archivos ya se prepararon para Danilo; se puede usar `.\.venv\Scripts\python.exe` como intérprete si `py -3.12` no está registrado.

`scripts/bootstrap_secrets.py` crea cinco valores aleatorios independientes y dos archivos derivados. Es idempotente: conserva los valores existentes y falla si están vacíos, duplicados, tienen formato inválido o no coinciden entre sí. No conecta con MySQL ni cambia credenciales de una base existente. No lee ni modifica el `.env` anterior.

| Archivo en `secrets/` | Consumidor |
|---|---|
| `django_secret_key` | Backend: `SECRET_KEY_FILE` |
| `jwt_signing_key` | Backend: `JWT_SIGNING_KEY_FILE` |
| `db_password` | Backend: `DB_PASSWORD_FILE`; MySQL: `MYSQL_PASSWORD_FILE` |
| `db_root_password` | Solo MySQL: `MYSQL_ROOT_PASSWORD_FILE` |
| `redis_password` | Comprobación local de salud de Redis |
| `redis_config` | Redis: configuración con contraseña y persistencia |
| `redis_url` | Backend: `REDIS_URL_FILE` |

En Windows el generador restringe la ACL del directorio al usuario actual y SYSTEM. En POSIX usa un directorio `0700`; los archivos nuevos son `0444` para que los procesos sin privilegios de los contenedores puedan leer los montajes de secretos. El directorio impide su lectura a otros usuarios del host. Compose monta archivos locales y no aplica `uid/gid/mode` sobre esos montajes: no convertir el directorio en público. Docker Desktop o el daemon necesitan acceso al directorio del usuario que despliega. Estos archivos no se cifran por usar Compose: proteger el disco y conservar una copia cifrada fuera del repositorio. No agregar `secrets/`, `.env`, SQLite, SQL con datos personales ni copias de producción a Git ni al contexto Docker.

`AMANDAYE_SECRETS_DIR` permite elegir otro directorio preparado con `--directory`, limitado a `secrets/` y sus subdirectorios excluidos de Git. Usar secretos distintos entre producción y desarrollo. La rotación es una operación coordinada: reemplazar claves de firma invalida sesiones/tokens; cambiar un archivo de contraseña no actualiza el usuario existente en MySQL. Para Redis deben actualizarse juntos `redis_password`, `redis_config` y `redis_url`, y reiniciarse los consumidores.

Solo el gateway publica puertos. El backend confía en los encabezados del proxy porque Caddy sustituye `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto` y `X-Forwarded-Host`, elimina `Forwarded` y usa la dirección de su conexión directa. No publicar el puerto del backend de producción ni conectar otros servicios a su red. Si se agrega una CDN o un segundo proxy, revisar la obtención de la IP real y limitar los proxies confiables antes de habilitarlo; no aceptar directamente encabezados enviados por clientes.

`DB_PRIVATE_NETWORK=1` corresponde a la red Docker interna de este Compose. Si MySQL se mueve a otra máquina, configurar `DB_SSL_CA`, verificar identidad/certificado y retirar esa excepción. Redis también necesita TLS (`rediss://`) si deja la red privada. La API usa el mismo origen HTTPS que la página; no requiere CORS abierto. Redis conserva los contadores compartidos entre workers y reinicios; su política evita expulsarlos silenciosamente por presión de memoria.

## Migrar una instalación con datos existentes

No ejecutar `docker compose down -v`, no borrar volúmenes y no montar un directorio MySQL 8.0 directamente en un contenedor 8.4 como atajo. Identificar primero el volumen/servidor original y guardar una copia consistente, cifrada y con restauración comprobada. Conservar una ruta de vuelta al servidor anterior hasta validar la migración. El archivo SQL personal anterior se excluye del build y no se ejecuta como seed.

La ruta recomendada es una restauración lógica ensayada en el volumen nuevo. Exportar únicamente el esquema de aplicación y sus datos desde el servidor anterior; no importar las tablas de sistema `mysql.*`, usuarios root antiguos ni concesiones globales. Verificar compatibilidad con MySQL 8.4, el juego de caracteres y las restricciones nuevas antes del cambio. El usuario nuevo `amandaye_app` y su contraseña se crean en la inicialización del volumen vacío.

Para conservar un servidor MySQL ya inicializado, un administrador debe provisionar explícitamente un usuario de aplicación, sin privilegios globales ni `GRANT OPTION`, con acceso solo al esquema `amandaye`. Utilizar una sesión administrativa local y un canal seguro para introducir la contraseña de `secrets/db_password`; no ponerla en la línea de comandos, en scripts versionados ni en el historial SQL. La aplicación requiere permisos de lectura/escritura y las migraciones requieren DDL; puede separarse una cuenta migradora de la cuenta de ejecución si la operación lo permite. Configurar host/red/certificados del servidor real y no arrancar otro MySQL sobre su volumen. La variable `MYSQL_PASSWORD_FILE` solo inicializa usuarios en bases vacías; no cambia usuarios de una instalación existente.

Después de restaurar una copia: ejecutar `migrate --plan`, revisar el plan y luego `migrate --noinput`, `setup_roles` y `check --deploy`. Las tablas de auditoría/limitación de login y blacklist JWT requieren migraciones. Revisar pagos, aplicaciones, cargos, estados de socios y permisos antes de abrir tráfico. Si las nuevas restricciones detectan registros históricos inválidos, conservarlos para conciliación y corregirlos de manera trazable; no borrar ni ajustar importes automáticamente. Al cambiar las claves de firma exigir un nuevo login y no mantener claves antiguas como alternativa.

## Desarrollo local

`docker-compose.dev.yml` es independiente: usarlo solo con `-f`, sin combinarlo con el archivo de producción. Crea otra base vacía y publica únicamente el backend en `127.0.0.1:8000`. `DJANGO_ENV=development` y DEBUG se habilitan explícitamente. No hay dump ni bind mount del directorio con datos locales.

```powershell
py -3.12 scripts/bootstrap_secrets.py --directory secrets/development
docker compose -f docker-compose.dev.yml config --quiet
docker compose -f docker-compose.dev.yml build --pull
docker compose -f docker-compose.dev.yml up -d db redis
docker compose -f docker-compose.dev.yml run --rm backend python manage.py migrate --noinput
docker compose -f docker-compose.dev.yml run --rm backend python manage.py setup_roles
docker compose -f docker-compose.dev.yml run --rm backend python manage.py createsuperuser
docker compose -f docker-compose.dev.yml up -d backend
Set-Location amandaye_frontend
npm ci --ignore-scripts
npm run dev
```

Abrir `http://127.0.0.1:5173`. Vite escucha solo en loopback y deriva `/api/`, `/login/`, `/admin/`, `/apps/` y `/static/` al backend local. Usa Node 24 o una versión compatible indicada en `package.json`. Reconstruir el servicio backend después de cambiar código con `docker compose -f docker-compose.dev.yml up -d --build backend`. No usar Vite, `vite preview` ni `runserver` para publicar el servicio en Internet. Si `AMANDAYE_SECRETS_DIR` quedó definido para producción en la terminal, retirarlo antes de iniciar desarrollo para usar `secrets/development`.

## Comprobaciones antes de abrir tráfico

```powershell
docker compose config --quiet
docker compose run --rm --no-deps gateway caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
docker compose run --rm backend python manage.py check --deploy
docker compose ps
curl.exe -I "https://$env:SITE_ADDRESS/"
curl.exe -i "https://$env:SITE_ADDRESS/api/socios/"
```

Verificar certificado válido, redirección HTTP a HTTPS y denegación de lectura anónima en `/api/socios/` (401/403). Probar registro público de una persona ficticia, aprobación solo por Directiva, operaciones financieras según rol y limitación de intentos fallidos. La inscripción pública devuelve una confirmación mínima. Confirmar que MySQL, Redis y el backend de producción no tienen puertos publicados, que los backups pueden restaurarse y que no hay claves ni información personal en los logs.

La validación de sintaxis `docker compose config --quiet` funciona sin daemon. Construir las imágenes, validar Caddy dentro del contenedor y probar TLS, salud y flujos integrados requieren Docker activo; no interpretar una validación estática como una prueba de despliegue completada.

`check --deploy` puede recomendar `SECURE_HSTS_INCLUDE_SUBDOMAINS` (W005) y `SECURE_HSTS_PRELOAD` (W021). HTTPS y HSTS de un año están habilitados para el sitio. Las dos opciones se mantienen desactivadas hasta confirmar que todos los subdominios soportan HTTPS y decidir la inclusión persistente del dominio en la lista de precarga del navegador.

## Pruebas de seguridad y concurrencia con MySQL

La suite local de [README](../README.md) usa SQLite en memoria. Para probar también la exclusión mutua entre pagos, cargos, anulaciones y reversiones, ejecutar desde la raíz:

```powershell
docker compose -f docker-compose.test.yml build tests
docker compose -f docker-compose.test.yml run --rm tests
docker compose -f docker-compose.test.yml down
```

Este Compose es independiente de producción y desarrollo: su proyecto es `socios-amandaye-security-tests`, usa MySQL 8.4 con almacenamiento temporal en memoria, sin puertos publicados ni volúmenes persistentes. La contraseña escrita en ese archivo corresponde exclusivamente a una cuenta sintética de pruebas, limitada al esquema `test_amandaye_security`. No monta ni lee los secretos, `.env`, SQLite o SQL personales. `down` elimina únicamente sus contenedores y su red; no usar ese comando con otro archivo para limpiar pruebas.

`settings_test_mysql` exige una cuenta de pruebas distinta de `root` y `amandaye_app`, y nombres de base que empiecen con `test_amandaye_`. Django puede vaciar esas tablas durante la suite. No apuntar las variables `TEST_MYSQL_*` a una base con datos que se deban conservar.

## Historial y operación después del cambio

La exclusión de archivos sensibles del índice de Git y del contexto Docker conserva sus copias locales. No elimina commits anteriores, clones, backups ni imágenes ya publicadas. Si el repositorio o las imágenes se compartieron, inventariar esas copias y coordinar la purga del historial/artefactos con sus responsables; después verificar un clon limpio. No volver a usar claves históricas. Cambiar archivos de secretos locales tampoco rota una contraseña en una base ya inicializada.

Enviar los eventos `amandaye.security` y de bloqueo de autenticación al recolector de logs del despliegue y configurar alertas ante bloqueos repetidos y errores internos. Limitar acceso y retención de logs. Planificar `flushexpiredtokens` para retirar entradas JWT caducadas; no borrar entradas de tokens aún vigentes. Verificar periódicamente dependencias e imágenes y probar actualizaciones antes de publicarlas.

Referencias: [secretos de Compose](https://docs.docker.com/reference/compose-file/services/#secrets), [cabeceras del proxy Caddy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy#headers), [autenticación de Redis](https://redis.io/docs/latest/operate/oss_and_stack/management/security/), [inicialización oficial de MySQL](https://github.com/docker-library/mysql/blob/master/8.4/docker-entrypoint.sh).
