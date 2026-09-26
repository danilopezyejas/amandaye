# Condiciones del río

[Índice](README.md) · [Arquitectura](ARCHITECTURE.md) · [Fuentes](CONDITIONS_SOURCES.md)

Página pública: `/condiciones-del-rio`. Presenta observaciones locales consolidadas,
pronóstico independiente y un desplegable con cada estación. No evalúa navegación
ni guarda histórico en MySQL.

## Arquitectura

El módulo utiliza Django/DRF, Vue/TypeScript y la configuración compartida del proyecto.
La app `apps.conditions` no contiene modelos ni requiere migraciones propias.

```text
Ecowitt / Weather Underground → services.weather → normalization
                                                   ↓
                                            caché por fuente
                                                   ↓
                                             aggregation
                                                   ↓
Open-Meteo → services.forecast → caché propia → API Django → Vue
```

El frontend usa exclusivamente `publicApi` del proyecto, bajo `/api/` y mismo origen.
Los enlaces a dashboards son enlaces voluntarios, no consultas de datos desde Vue.
La portada en `App.vue` incluye un enlace a la página; `main.ts` monta `RouterView`.

## Fuentes y credenciales pendientes

Los contratos externos y sus fechas de verificación están en
[fuentes y referencias primarias](CONDITIONS_SOURCES.md). La siguiente tabla
describe las API; la lectura provisional de páginas públicas se detalla después.

| Fuente | Acceso implementado | Datos que debe aportar el responsable |
|---|---|---|
| Club de Pescadores / Ecowitt | `GET https://api.ecowitt.net/api/v3/device/real_time` | `ECOWITT_APPLICATION_KEY`, `ECOWITT_API_KEY`, `ECOWITT_MAC` reales de esa estación |
| Yacht Club / Weather Underground | `GET https://api.weather.com/v2/pws/observations/current`, `stationId=IPAYSA15`, `units=m` | `WUNDERGROUND_API_KEY` válida para PWS observations |
| Pronóstico / Open-Meteo | `GET https://api.open-meteo.com/v1/forecast`, hourly + daily, métricas, Unix, `America/Montevideo` | Ninguna clave para su servicio público de uso no comercial |

`PHC0G3` corresponde al enlace compartido Ecowitt: no es una MAC, API key ni device ID.
No se pudo validar una lectura autenticada de las estaciones sin sus credenciales.

### Rama provisional de scraping

La rama `codex/condiciones-rio-scraping` agrega lectura de las páginas públicas,
solicitada mientras se consiguen las credenciales. `CONDITIONS_STATION_MODE` admite:

- `auto` (predeterminado en esta rama): usa la API de cada estación cuando tiene
  todas sus credenciales; de lo contrario usa su página pública.
- `api`: conserva el comportamiento original; sin claves devuelve `not_configured`.
- `public_page`: fuerza la lectura pública para ambas estaciones.

Una API configurada que falla no cambia silenciosamente a scraping. Las cachés de
API y página pública son independientes. La conmutación de configuración requiere
reiniciar el backend; con Compose, recrearlo para actualizar su entorno.

**Ecowitt:** consulta por POST los endpoints públicos de lectura
`https://www.ecowitt.net/index/get_device_list` (`authorize=PHC0G3`) y
`https://www.ecowitt.net/index/home` (`authorize` y `device_id` descubierto en la
respuesta anterior). Son las consultas del dashboard compartido. No se fija un MAC
ni se inventa un identificador. Si el enlace comparte más de una estación, se rechaza
la selección ambigua. Se normalizan los campos de exterior, viento, presión relativa
y lluvia; los máximos diarios y la temperatura interior no son mediciones actuales.

Las horas `Today HH:MM` de Ecowitt se resuelven con `Date` de la respuesta HTTP y
`UTC_offset` de la estación. Se conserva la precisión de minuto y la hora de cada
sensor. Una hora sin fecha interpretable se descarta; nunca se reemplaza por la hora
de consulta. Se contemplan coma decimal y separadores de miles del dashboard.

**Weather Underground:** descarga el HTML de
`https://www.wunderground.com/dashboard/pws/IPAYSA15` y lee los atributos del estado
de la estación y de sus widgets meteorológicos. También reconoce la variante Angular:
lee el JSON `app-root-state` y acepta únicamente las observaciones embebidas del
endpoint de condiciones actuales de `IPAYSA15`; nunca hace consultas a las URLs
contenidas en ese bloque. El registro `pwsidentity` permite reconocer una estación
inactiva cuando el HTML no incluye observaciones. Verifica identidad, unidades y fecha
explícita, incluyendo el formato `Date.toString()` del servidor. Reconoce `offline`
como `station_offline`; no toma valores de tablas históricas. El acumulado diario
no se transforma en lluvia horaria. No extrae ni reutiliza API keys del sitio.

Ambos adaptadores usan solo la biblioteca estándar Python, con límite de respuesta
de 2 MiB, timeout y sin seguir redirecciones ni ejecutar JavaScript. Reutilizan caché,
consolidación, antigüedad y manejo de fallos. Las fuentes agregan `access_method`
(`api` o `public_page`) y Ecowitt público agrega `timestamp_precision=minute`.
El frontend indica la procedencia pública en el detalle de las estaciones.

Limitación: estos contratos públicos no son API estable; cambios de HTML, idioma,
unidades, restricciones o revocación del enlace pueden dejar una fuente sin datos.
El pronóstico permanece independiente. Las API oficiales siguen siendo el destino
para la integración definitiva.

## Configuración

Valores centralizados en `apps/conditions/config.py`, cargados como `settings.CONDITIONS`.
La plantilla [`.env.example`](../amandaye_backend/.env.example) complementa la
configuración existente de Django; no sustituye sus secretos ni la configuración de DB.

| Variable | Predeterminado |
|---|---|
| `ECOWITT_APPLICATION_KEY`, `ECOWITT_API_KEY`, `ECOWITT_MAC`, `WUNDERGROUND_API_KEY` | Vacías |
| `CONDITIONS_STATION_MODE` | `auto` en la rama provisional; `api` deshabilita scraping |
| `CONDITIONS_STALE_MINUTES` | 20 |
| `CONDITIONS_OBSERVATION_CACHE_SECONDS` | 300 |
| `CONDITIONS_FORECAST_CACHE_SECONDS` | 900 |
| `CONDITIONS_FALLBACK_CACHE_SECONDS` | 3600 |
| `CONDITIONS_EXTERNAL_TIMEOUT_SECONDS` | 5 (máximo configurable 15) |
| `CONDITIONS_LATITUDE`, `CONDITIONS_LONGITUDE` | −32.3027, −58.0904, mapa del club existente |
| `CONDITIONS_WIND_DIFFERENCE_KMH` | 10 |
| `CONDITIONS_GUST_DIFFERENCE_KMH` | 15 |
| `CONDITIONS_TEMPERATURE_DIFFERENCE_C` | 3 |
| `CONDITIONS_PRESSURE_DIFFERENCE_HPA` | 5 |

Las tres claves admiten alternativamente `NOMBRE_DE_VARIABLE_FILE`, usando un archivo
de secreto montado en el backend. El soporte `_FILE` de Django no monta el archivo:
quien despliega debe declarar ese montaje y esa variable en su configuración Compose.
No agregar claves como variables `VITE_*`, al repositorio ni a comandos compartidos.

En desarrollo nativo, Django puede leer las variables del `.env` del backend.
Compose usa `AMANDAYE_SKIP_DOTENV=1`: los parámetros opcionales se declaran en
`environment` del backend de ambos archivos Compose.
Pueden suministrarse mediante un archivo local protegido y excluido de Git:
`docker compose --env-file amandaye_backend/.env.conditions ...` o, para desarrollo,
`docker compose --env-file amandaye_backend/.env.conditions -f docker-compose.dev.yml ...`.
Crear ese archivo a partir de la plantilla y completar solo valores reales.
Evitar `docker compose config` sin `--quiet` cuando haya secretos en variables.

Producción agrega `conditions_egress` para HTTPS saliente del backend. No publica
puertos nuevos: MySQL y Redis conservan su red interna. Si hay firewall externo,
permitir DNS y HTTPS hacia los tres hosts oficiales anteriores y, para el modo
público, `www.ecowitt.net` y `www.wunderground.com`.

## Endpoints y contrato

- `GET /api/conditions/`: `weather`, `forecast`, `meta`.
- `GET /api/conditions/stations/`: `stations`, `meta`; reutiliza caché de estaciones,
  sin consultar pronóstico.

Son GET públicos de información ambiental, con límite DRF de 60 peticiones/minuto
por cliente según la configuración de IP del proyecto. No cambian permisos de socios.
No aceptan URLs, claves ni identificadores de proveedor del navegador.

```text
weather.current: métricas, available, station_ids, stations_available,
                 timestamp, age_minutes, stale, fallback, last_known
weather.sources: estaciones normalizadas, incluso cuando están caídas
weather.comparison: diferencias, significant, differing_fields
forecast: provider, source_url, available, fetched_at, age_minutes, stale,
          hourly (hasta 12 próximas horas), daily (hoy o null)
meta: generated_at, stale_after_minutes, forecast_stale_after_seconds,
      refresh_interval_seconds
```

Métricas observadas: `temperature_c`, `humidity_pct`, `pressure_hpa`, `wind_speed_kmh`,
`wind_gust_kmh`, `wind_direction_deg`, `wind_direction_cardinal`, `rain_1h_mm`,
`rain_rate_mmh`, `rain_detected`. Valores ausentes/invalidables son `null`, nunca cero
inventado. Direcciones meteorológicas indican **de dónde viene** el viento.

`fetched_at` es la hora de consulta del pronóstico, no la emisión del modelo.
`generated_at` corresponde a la respuesta de nuestra API y no reemplaza horas de
observación. Horas de pronóstico se interpretan en Paysandú incluso desde otro país.
Los errores son códigos acotados (`not_configured`, `timeout`, `http_error`,
`connection_error`, `invalid_response`, `station_unavailable`, etc.). Los logs registran
proveedor, estación, categoría y status HTTP; no incluyen URLs con claves ni traceback.

## Consolidación y antigüedad

- Preferir exclusivamente estaciones frescas cuando exista alguna. Si solo hay antiguas,
  mostrar fallback explícito `stale_observations`; sin estaciones válidas, current unavailable.
- Temperatura, humedad y presión: promedio de valores presentes. Ecowitt usa presión
  relativa; no mezcla presión absoluta de estación con presión reducida.
- Viento sostenido: promedio en función separada `consolidate_wind_speed`.
- Ráfaga: máximo. Lluvia horaria e intensidad: máximo de cada magnitud por separado.
- `rain_detected` indica lluvia registrada por intensidad o acumulado horario positivo;
  no demuestra lluvia en este instante. Falso requiere lecturas conocidas cero de
  todas las estaciones usadas; con información incompleta y sin positivos queda null.
- WU no entrega acumulado de la última hora: `rain_1h_mm=null`. `precipRate` solo
  llena `rain_rate_mmh`; `precipTotal` diario no se usa como acumulado horario.
- Dirección: media de vectores unitarios. 350° y 10° dan norte. Resultante ≤0,1
  de longitud media devuelve null y `wind_direction_ambiguous=true`.
- Comparación usa fuentes frescas. Advierte diferencias por encima de los umbrales
  configurados, sin atribuir fallos a una estación.
- Ecowitt conserva timestamps de cada sensor en `field_timestamps`; timestamp de
  estación es el más antiguo de los valores aceptados. Current usa el más antiguo
  de las estaciones utilizadas. La edad se recalcula en cada respuesta, incluido cache hit.

## Caché, errores y concurrencia

Se utiliza `django.core.cache`: Redis compartido en ambos entornos Compose y
LocMem en las pruebas SQLite o en desarrollo nativo cuando no se configura Redis.
Observaciones se cachean 5 minutos por estación; pronóstico 15 minutos por coordenadas.
Errores también se cachean para evitar llamadas repetidas contra una fuente caída.
El último éxito se conserva por una hora por defecto. Ante fallo se puede devolver
con `last_known=true`, error y timestamp originales; no extiende la hora del último éxito.
Una respuesta de caché todavía vigente puede sobrevivir hasta su TTL tras expirar la
copia de último éxito. La interfaz siempre muestra la antigüedad.

`cache.add` obtiene una concesión temporal por fuente. Quienes encuentran una consulta
en curso reciben el último éxito o `refresh_in_progress` en arranque frío. No esperan
ni disparan una segunda solicitud idéntica. La concesión expira sola para evitar que
un proceso demorado borre el bloqueo de otro; LocMem coordina solo dentro de un proceso.
Los tres proveedores se consultan concurrentemente y sus fallos se aíslan.
El timeout limita las operaciones de socket; no es una garantía de plazo total ante
problemas del resolvedor DNS o respuestas que lleguen muy lentamente por fragmentos.
Las respuestas de las API están limitadas a 1 MiB y las páginas públicas a 2 MiB;
se validan tipos/unidades/rangos y no se siguen redirecciones.

## Actualización y PWA

Consulta inicial y refresco silencioso cada 300 s con los datos anteriores visibles.
Al regresar desde segundo plano, `visibilitychange` consulta si pasaron 5 minutos.
Un reloj local actualiza edades sin hacer solicitudes. Al desmontar se cancelan
solicitudes, intervalos y listeners. Si falla la conexión, se conservan los datos en
memoria rotulados como anteriores. No hay persistencia offline entre reinicios.
Si otra solicitud está completando la caché (`refreshing`), se reintenta cada 2 segundos,
hasta tres veces; después se conserva el intervalo normal de cinco minutos.

El frontend enlaza el manifiesto web y los iconos del proyecto. No incluye
service worker ni una infraestructura offline. La instalación/ejecución como PWA
depende del soporte del navegador y de servir por HTTPS fuera de localhost.

## Pruebas y ejecución local

Preparar el entorno según [Desarrollo](DEVELOPMENT.md#pruebas-locales-aisladas).
Para ejecutar solo las pruebas de este módulo, desde `amandaye_backend`:

```powershell
..\.venv\Scripts\python.exe manage.py test apps.conditions --settings=amandaye_backend.settings_test --noinput
```

Las pruebas de proveedores usan respuestas simuladas y no requieren Internet. Backend cubre conversiones,
normalización, timestamp, dirección, consolidación, proveedores, pronóstico, HTTP,
errores y caché/concurrencia. Frontend usa el runner Node existente para presentación,
render SSR y ciclo de refresco/visibilidad/cancelación. Las pruebas de scraping cubren
formato público, fechas, unidades, fuente offline, transporte y selección API/página.
Los comandos de pruebas, comprobación de tipos y compilación del frontend están en
la [guía de desarrollo](DEVELOPMENT.md#frontend).

Arranque habitual sobre entorno ya configurado:

```powershell
docker compose -f docker-compose.dev.yml up -d --build backend frontend
```

Abrir [Condiciones del río](http://127.0.0.1:5173/condiciones-del-rio).
Para editar Vue con recarga automática, usar el
[frontend nativo](DEVELOPMENT.md#frontend-nativo-con-recarga-de-cambios).

## Extensiones posteriores

- Otra estación: agregar metadatos, adaptador, normalizador y tarea cacheada; conservar
  el contrato normalizado y probar fallos/unidades/antigüedad. Agregación admite más de dos.
- Altura del río: nueva familia `river` con su proveedor verificado, unidades y caché,
  timestamp y edad propios. No añadirla como medición de una estación meteorológica.
- INUMET: familia `alerts` independiente del pronóstico, con vigencia y fuente propias.
- Navegación: futura capa de evaluación sobre familias normalizadas, umbrales backend,
  razones explicables y estado de datos insuficientes; sin acoplarla a Vue.
- Garmin: adaptador independiente, con autorización y contrato por definir cuando se
  especifique qué datos necesita el club. No hay OAuth, claves ni endpoints supuestos hoy.

Estas extensiones son propuestas, no funcionalidades disponibles. El
[registro de traspaso](CONDITIONS_HANDOFF.md) conserva las verificaciones históricas
y el contexto de implementación.

## Código de referencia

| Componente | Ubicación |
| --- | --- |
| Configuración, normalización, consolidación y API | [apps/conditions](../amandaye_backend/apps/conditions/) |
| Adaptadores y caché | [services](../amandaye_backend/apps/conditions/services/) |
| Lectura provisional de páginas públicas | [scraping.py](../amandaye_backend/apps/conditions/services/scraping.py) |
| Página Vue | [RiverConditionsPage.vue](../amandaye_frontend/src/pages/RiverConditionsPage.vue) |
| Visualización del panel | [ConditionsDashboard.vue](../amandaye_frontend/src/components/ConditionsDashboard.vue) |
| Tipos, presentación y actualización | [src/conditions](../amandaye_frontend/src/conditions/) |
| Plantilla de variables | [.env.example](../amandaye_backend/.env.example) |
