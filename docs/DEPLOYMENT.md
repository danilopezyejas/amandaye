# Despliegue y operación

[Índice](README.md) · [Desarrollo](DEVELOPMENT.md) · [Seguridad](../SECURITY.md)

La configuración principal ejecuta Django con Gunicorn y el frontend compilado detrás de Caddy con HTTPS. MySQL 8.4 y Redis autenticado quedan en una red interna sin puertos publicados. La base anterior, su volumen y sus archivos locales no se migran ni se eliminan automáticamente.

## Entornos

| Entorno | Archivo Compose | Proyecto | Datos |
| --- | --- | --- | --- |
| Producción | `docker-compose.yml` | `socios-amandaye-secure` | Volúmenes persistentes propios |
| Desarrollo | `docker-compose.dev.yml` | `socios-amandaye-devsecure` | Volúmenes persistentes propios |
| Pruebas MySQL | `docker-compose.test.yml` | `socios-amandaye-security-tests` | Almacenamiento temporal y datos sintéticos |

Los archivos son independientes. Los comandos de esta guía sin `-f` corresponden
a **producción** y se ejecutan desde la raíz. Para desarrollo, seguir el
[inicio rápido](../README.md#inicio-rápido) y la [guía local](DEVELOPMENT.md).

## Preparar una instalación nueva

Se requiere Docker Engine/Desktop con contenedores Linux y Compose v2, un dominio controlado por el club y sus registros DNS apuntando al servidor. Los puertos públicos 80 y 443 deben llegar al gateway para obtener y renovar certificados. Python 3.12 o superior permite ejecutar el generador de secretos. El build usa Python 3.12 y Node 24.

Ejecutar desde la raíz del proyecto. Estos ejemplos usan PowerShell; sustituir `socios.ejemplo.org` por el dominio real, sin esquema, puerto ni ruta:

```powershell
$env:AMANDAYE_SECRETS_DIR = (Join-Path (Get-Location) 'secrets')
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

En Linux usar Python 3.12 y configurar las mismas variables antes de los comandos Docker:

```bash
export AMANDAYE_SECRETS_DIR="$PWD/secrets"
python3.12 scripts/bootstrap_secrets.py
export SITE_ADDRESS=socios.ejemplo.org
export DJANGO_ALLOWED_HOSTS=socios.ejemplo.org
```

Si Python 3.12 está disponible como `python3`, usar ese ejecutable. Persistir el
dominio y el directorio de secretos en la configuración del servicio que ejecuta
Compose, fuera de Git. Las contraseñas de infraestructura se suministran mediante
archivos de secretos. El directorio explícito evita heredar los secretos de
desarrollo de una terminal utilizada para ambos entornos.

`migrate` se ejecuta explícitamente: el arranque normal no modifica el esquema. El entrypoint ejecuta `collectstatic` antes de Gunicorn y WhiteNoise sirve `/static/`. `setup_roles` crea los grupos `Administrador`, `Comision Directiva`, `Secretaria` y `Tesoreria`, y reemplaza sus permisos por los definidos en el código. Revisar personalizaciones antes de volver a ejecutarlo. Asignar los grupos desde el administrador y habilitar `is_staff` en las cuentas que deban acceder allí. La creación de usuarios es interactiva y no trae contraseñas predeterminadas.

En una base nueva, preparar también el catálogo de cobros:

```powershell
docker compose run --rm backend python manage.py seed_conceptos
```

Luego configurar los importes aprobados por el club en el administrador, antes de
aprobar socios que generen cargos o ejecutar cuotas mensuales. El comando crea los
conceptos faltantes y conserva los existentes; no establece tarifas operativas.

El proyecto Compose de producción se llama `socios-amandaye-secure` y su volumen de datos es `mysql_secure_data`, con el prefijo del proyecto. No reutiliza el volumen anterior `mysql_data`. Las imágenes base siguen ramas mantenidas; actualizar con `build --pull`/`pull`, auditar y probar antes de promover cada versión. Para despliegues reproducibles aprobados, registrar también los digest de las imágenes usadas.

## Secretos y límites de confianza

En Windows, ejecutar el generador desde la misma cuenta que ejecuta Docker Desktop. Una cuenta aislada de herramientas puede tener un SID distinto: si crea los secretos, Docker no podrá montarlos hasta que se transfiera su acceso al usuario del despliegue. No resolver un error de acceso concediendo lectura a `Everyone` o `Users`. Si `py -3.12` no está registrado, usar la ruta a un intérprete Python 3.12 instalado.

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

La [guía de desarrollo](DEVELOPMENT.md) reúne instalación, frontend nativo, pruebas
y diagnóstico. El backend y Vite se publican solo en loopback; MySQL y Redis
permanecen internos. El código se copia durante el build y requiere reconstrucción
para reflejar cambios. No publicar Vite, `vite preview` ni `runserver` en Internet.

### Recuperar un entorno antiguo que falla por SECRET_KEY

Reiniciar un contenedor antiguo no actualiza su imagen, variables ni montajes. Ver
[recuperación del entorno](DEVELOPMENT.md#recuperar-un-entorno-antiguo) y el
[procedimiento de migración de datos](#migrar-una-instalación-con-datos-existentes)
antes de recrearlo.

## Comprobaciones antes de abrir tráfico

```powershell
docker compose config --quiet
docker compose run --rm --no-deps gateway caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
docker compose run --rm backend python manage.py check --deploy
docker compose ps
curl.exe -I "https://$env:SITE_ADDRESS/"
curl.exe -i "https://$env:SITE_ADDRESS/api/socios/"
```

Verificar certificado válido, redirección HTTP a HTTPS y denegación de lectura anónima en `/api/socios/` (401/403). Probar registro público de una persona ficticia, aprobación solo con el permiso correspondiente, operaciones financieras según rol y limitación de intentos fallidos. La inscripción pública devuelve una confirmación mínima. Confirmar que MySQL, Redis y el backend de producción no tienen puertos publicados, que los backups pueden restaurarse y que no hay claves ni información personal en los logs.

Comprobar también el acceso directo a `/condiciones-del-rio` y las respuestas de
`/api/conditions/`. Revisar la disponibilidad y antigüedad de cada fuente: recibir
HTTP 200 no garantiza que todas las estaciones estén entregando observaciones.
La [configuración ambiental](CONDITIONS.md#configuración) describe los modos de
acceso, las credenciales opcionales y la conectividad saliente.

La validación de sintaxis `docker compose config --quiet` funciona sin daemon. Construir las imágenes, validar Caddy dentro del contenedor y probar TLS, salud y flujos integrados requieren Docker activo; no interpretar una validación estática como una prueba de despliegue completada.

`check --deploy` puede recomendar `SECURE_HSTS_INCLUDE_SUBDOMAINS` (W005) y `SECURE_HSTS_PRELOAD` (W021). HTTPS y HSTS de un año están habilitados para el sitio. Las dos opciones se mantienen desactivadas hasta confirmar que todos los subdominios soportan HTTPS y decidir la inclusión persistente del dominio en la lista de precarga del navegador.

## Pruebas de seguridad y concurrencia con MySQL

Ejecutar las [pruebas con MySQL desechable](DEVELOPMENT.md#concurrencia-con-mysql)
para validar exclusión mutua entre pagos, cargos, anulaciones y reversiones.
La suite SQLite no sustituye esa verificación. Usar exclusivamente el Compose de
pruebas y bases desechables; Django puede vaciar sus tablas durante la suite.

## Actualizaciones y recuperación

1. Identificar el commit a desplegar, revisar cambios de configuración y migraciones,
   y ejecutar las verificaciones pertinentes en un entorno separado.
2. Registrar las imágenes vigentes y disponer de un respaldo consistente cuya
   restauración se haya ensayado.
3. Construir las imágenes de la versión elegida. Si cambia el esquema, revisar
   `migrate --plan` y aplicar las migraciones durante una ventana controlada.
4. Recrear backend y gateway, y repetir las comprobaciones de acceso y de flujos.
5. Conservar el respaldo y las imágenes anteriores hasta validar el resultado.

Volver a una imagen anterior no revierte migraciones ni escrituras posteriores.
La recuperación debe considerar la compatibilidad del esquema y la conciliación
de movimientos realizados desde el respaldo. No ejecutar `down -v` para actualizar.

## Mantenimiento

| Tarea | Criterio operativo |
| --- | --- |
| Respaldo y restauración | Definir frecuencia, retención y responsables; ensayar restauraciones en un entorno separado. |
| Cuotas mensuales | Configurar conceptos e importes, elegir el periodo y revisar el resumen de creación, omisiones y errores. |
| Tokens caducados | Programar `flushexpiredtokens` según la operación del servidor. |
| Logs | Revisar fallos de autenticación, errores internos y disponibilidad de proveedores. |
| Dependencias e imágenes | Evaluar actualizaciones, probarlas y registrar la versión publicada. |

Los siguientes comandos se ejecutan manualmente desde la raíz y modifican el
estado del sistema; el repositorio no los programa automáticamente:

```powershell
# Sustituir el periodo por el aprobado para la emisión.
docker compose run --rm backend python manage.py generar_cuotas_mensuales --periodo 2026-09
docker compose run --rm backend python manage.py flushexpiredtokens
```

La generación mensual omite cargos ya existentes para la cuenta, concepto y periodo.
Revisar siempre el resumen: puede haber errores en unas cuentas y éxito en otras.

## Historial y registros

La exclusión de archivos sensibles del índice de Git y del contexto Docker conserva sus copias locales. No elimina commits anteriores, clones, backups ni imágenes ya publicadas. Si el repositorio o las imágenes se compartieron, inventariar esas copias y coordinar la purga del historial/artefactos con sus responsables; después verificar un clon limpio. No volver a usar claves históricas. Cambiar archivos de secretos locales tampoco rota una contraseña en una base ya inicializada.

Enviar los eventos `amandaye.security` y de bloqueo de autenticación al recolector de logs del despliegue y configurar alertas ante bloqueos repetidos y errores internos. Limitar acceso y retención de logs. Planificar `flushexpiredtokens` para retirar entradas JWT caducadas; no borrar entradas de tokens aún vigentes. Verificar periódicamente dependencias e imágenes y probar actualizaciones antes de publicarlas.

## Referencias

- [Secretos de Compose](https://docs.docker.com/reference/compose-file/services/#secrets).
- [Cabeceras del proxy Caddy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy#headers).
- [Autenticación de Redis](https://redis.io/docs/latest/operate/oss_and_stack/management/security/).
- [Inicialización oficial de MySQL](https://github.com/docker-library/mysql/blob/master/8.4/docker-entrypoint.sh).
