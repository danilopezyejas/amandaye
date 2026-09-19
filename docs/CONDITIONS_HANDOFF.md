# Traspaso — Condiciones del río

## Objetivo y alcance autorizado

Implementar directamente en este repositorio la solicitud completa adjunta en
`C:/Users/Danilo/.codex/attachments/96db4606-ec60-4487-9c60-39d90403a391/pasted-text.txt`.
Leerla antes de continuar: contiene 65 secciones y criterios de aceptación.
El usuario pidió trabajo autónomo, commits claros cuando corresponda y un contexto
de traspaso antes de agotar tokens. No inventar datos ni credenciales.

Crear Condiciones del río: observaciones reales Ecowitt/Pescadores y
Weather Underground/Yacht IPAYSA15, consolidación backend, pronóstico Open-Meteo,
API `/api/conditions/` y `/api/conditions/stations/`, página móvil Vue.
NO implementar altura del río, INUMET, Garmin, navegación/semáforo, push,
histórico ni persistencia de lecturas. Solo permitir ampliación futura.

## Arquitectura encontrada

- Backend `amandaye_backend/`: Django 5.2 LTS, DRF, MySQL, apps bajo `apps/`.
- Seguridad JWT y permisos por operación; portada/inscripción públicas.
- Caché Django existente: Redis obligatorio en producción, LocMem en desarrollo/tests.
- Settings test aislados: `amandaye_backend.settings_test`, SQLite memoria, secretos sintéticos.
- Frontend `amandaye_frontend/`: Vue 3/TS, Vite, Tailwind 4, Pinia, axios, vue-router.
- `src/App.vue` es portada completa; `main.ts` la monta y router '/' también apunta allí,
  pero no existe RouterView. Conservar portada; habilitar salida de rutas mínima.
- `src/api/axios.ts` exporta `publicApi`; usarlo para consultas meteorológicas públicas.
  `client.ts` impone mismo origen `/api/`. Nunca consultar proveedores desde Vue.
- Estética azul/naranja, Inter, SVG inline. No agregar biblioteca UI.
- Hay manifest sin enlazar, sin service worker/offline implementado.
- Compose producción aísla backend en redes internas: revisar salida a Internet necesaria
  para APIs sin publicar puertos del backend ni MySQL/Redis.

## Estado actual (2026-09-19)

Implementación y verificaciones terminadas; no reiniciar ni reemplazar lo hecho.
Documentación de uso: `docs/CONDITIONS.md`; investigación: `docs/CONDITIONS_SOURCES.md`.

- Nueva app `apps.conditions`: config, utils, normalization, aggregation, services
  (http/weather/forecast/cache), views, urls y 62 pruebas. Sin modelos/migraciones.
- Nueva página Vue `/condiciones-del-rio`, dashboard, tipos/presentación/feed,
  y 21 pruebas nuevas usando el runner Node existente.
- API pública GET conditions + stations, rate limit 60/minuto, sin acceso a datos de socios.
- Cache por fuente 300/900 s, concesión cache.add, último éxito hasta 3600 s;
  metadata de antigüedad se recalcula en cada respuesta.
- Polling 300 s, reloj de edad 30 s, reanudación por visibilidad, AbortController;
  reintento de coordinación de caché cada 2 s hasta 3 intentos cuando `refreshing`.
- Datos medidos y pronóstico separados. Intensidad positiva de lluvia no queda
  oculta por acumulado horario 0 de la otra estación. Datos ausentes null.
- Compose pasa variables opcionales a backend y producción tiene red saliente
  `conditions_egress`; puertos de DB/Redis/backend siguen sin publicarse.
- Reset CSS universal pasó a `@layer base`: antes anulaba todos los márgenes
  Tailwind; ahora funcionan `mt`, `mb`, `mx-auto`, `space-y` en página y portada.
- Manifest existente enlazado, favicon SVG existente y lang=es; sin service worker.

Validación completada:
- Baseline previo: backend 104 OK (4 omitidas), frontend 7 OK.
- Backend completo actual: 166 OK, mismas 4 omitidas por requerir MySQL.
- Frontend actual: 28 OK; `vue-tsc --noEmit` OK; build Vite runner y
  `npm run build` estándar OK (este último fuera del aislamiento Windows).
- `makemigrations --check --dry-run`: sin cambios.
- Compose dev y producción: `config --quiet` OK (host ficticio club.example solo para validar sintaxis).
- Open-Meteo real mediante adaptador Python: available=true, 12 próximas horas,
  resumen fecha 2026-09-19. Se requirió ejecución fuera del aislamiento por WinError10013.
- Navegador: página vacía sin credenciales/fallo de red; fuentes visibles;
  fixture sintético en servidor QA aislado, viento/dirección/ráfagas/pronóstico;
  móvil 390px y escritorio 1280px sin overflow de documento, main centrado 1024px.
- Navegación de vuelta a portada y apertura del formulario de inscripción
  verificadas en navegador, sin enviar datos. `git diff --check` OK.
- El commit local de esta funcionalidad se crea como último paso; consultar `git log -1`
  y el resumen final de la conversación para su identificador. No se hizo push ni despliegue.

Credenciales verificadas solo por presencia (sin imprimir valores): faltan
ECOWITT_APPLICATION_KEY, ECOWITT_API_KEY, ECOWITT_MAC, WUNDERGROUND_API_KEY tanto
en entorno como `.env` backend. El pronóstico no depende de ellas. No escribir claves ficticias.
No se probó acceso autenticado a estaciones, un teléfono físico, Redis/MySQL en
contenedores ni un despliegue real. No se ejecutaron migraciones ni cambios de DB.

Git 2.36.1 en sandbox rechaza ownership; ejecutar lecturas y commit con revisión
de aprobación `require_escalated` y alcance exacto. Reintento autorizado ya funciona.
No cambiar safe.directory global. Hubo interrupciones por cuota, no por problemas del código.

## Herramientas/comandos

Usar PowerShell `login:false`: perfil por defecto quedó colgado. Algunas sesiones
demoraron al reanudar. Los procesos devuelven session_id y se recuperan con write_stdin.
Para variables de entorno usar `$env:NOMBRE = 'valor'`; `set` estilo cmd no funcionó
en esta herramienta incluso al solicitar shell cmd.exe.
Backend desde `amandaye_backend/`:
`..\.venv\Scripts\python.exe manage.py test --settings=amandaye_backend.settings_test --noinput`
Frontend desde `amandaye_frontend/`:
`node 'C:/Program Files/nodejs/node_modules/npm/bin/npm-cli.js' test`
y mismo comando `run build`. Evita advertencia de npm.ps1 por perfil npm inaccesible.
Build alternativo dentro del sandbox: `node node_modules/vite/bin/vite.js build --configLoader runner`.
Para preview usar `preview --configLoader runner`, porque dev dispara esbuild optimizeDeps
y vuelve a encontrar restricción de lectura del directorio padre.
No leer ni imprimir secretos `.env`/`secrets/`; no alterar DB real.

## Trabajo delegado en esta sesión

- `provider_research`: completó docs fuentes + 21 tests services/API/cache/HTTP.
- `frontend`: completó frontend + 28 tests totales, tipo/build y fixes revisión.
- `weather_core`: completó núcleo + 41 tests, revisión crítica cache/forecast.
- Root: config/transportes/cache/API/docs/Compose, pruebas globales y navegador.

Si retoma otro agente, leer primero los tres documentos y `git status`/diff. Revisar
resultados pendientes en este archivo y completar solo lo que falte. No publicar
ni arrancar/migrar DB de producción. No crear funcionalidades futuras fuera del alcance.
Commitear únicamente archivos de esta funcionalidad con mensaje explícito; no incluir
`.env`, `.local`, secrets, dist, node_modules ni base local.

## QA local temporal

`.local/conditions_visual_qa.py` está excluido de Git. Reutiliza fixtures sintéticos
de tests, con nombres de fuentes marcados como prueba; no incorpora datos falsos al producto.
Los servidores temporales de esta ejecución (puertos 8765, 8766 y 5174) se detienen
al finalizar. La pestaña de QA se cerró y el viewport se restauró. No entregar una
vista sintética como datos reales. Para una nueva revisión, iniciar explícitamente
los procesos y usar el Browser skill; no reutilizar identificadores de sesiones antiguas.

## Hallazgo verificado de proveedor

WU: `https://api.weather.com/v2/pws/observations/current`, parámetros
`stationId=IPAYSA15`, `format=json`, `units=m`, `numericPrecision=decimal`, `apiKey` backend.
Fuente: https://developer.weather.com/docs/openapi/pws-current-observations-2-0/get-v2-pws-observations-current
Observación `observations[0]`, métricas bajo `metric`, humedad/winddir y epoch/obsTimeUtc raíz.
`precipRate` es intensidad mm/h, NO acumulación última hora; conservar `rain_1h_mm=null`
si no hay acumulado real. Dashboard no suministra credencial autorizada; preparar env.

## Reglas obligatorias a preservar

- Ausentes = null, timestamp original; edad recalculada aun si respuesta proviene de caché.
- Umbral antiguo configurable 20 min. Frescas excluyen antiguas de consolidación.
- Temp/humedad/presión promedio; viento función separada; ráfaga máxima; lluvia estrategia explícita.
- Dirección vectorial; 350+10 debe dar norte; opuestas/ambiguas null.
- Errores de estaciones aislados; pronóstico independiente aun con ambas caídas.
- Timeouts, errores JSON/estructura/HTTP/DNS, logs sin claves ni texto de excepción sensible.
- Caché observaciones 300 s, pronóstico 900 s, bloqueo simple cache.add para evitar ráfagas de consultas.
- Frontend refresco silencioso 300 s; visibilitychange al volver si vencido; limpiar timers/listeners/requests.
- Edad visible y dinámica; retener últimos datos ante fallo y rotularlos.
- Tests externos siempre mocks; validar build/tests existentes y nuevos, typecheck.
- Final debe incluir arquitectura, archivos, métodos proveedores, env/credenciales pendientes,
  endpoints/contrato, cache/refresco, pruebas/comandos, arranque y ampliaciones futuras.
