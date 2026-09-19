# Condiciones del río: fuentes y contratos externos

Verificación: 15 de septiembre de 2026. Los servicios externos se consultan desde
Django; Vue/PWA consume solamente la API del club. Las mediciones de estaciones
permanecen separadas del pronóstico de modelos meteorológicos.

| Información | Fuente | Identificación |
| --- | --- | --- |
| Observaciones Club de Pescadores | Ecowitt | MAC real pendiente de configurar |
| Observaciones Yacht Club Paysandú | Weather Underground | `IPAYSA15` |
| Pronóstico Paysandú | Open-Meteo | Coordenadas configurables, zona `America/Montevideo` |

## Ecowitt: API oficial de observaciones

- [Dashboard compartido](https://www.ecowitt.net/home/share?authorize=PHC0G3).
- [Contrato oficial de datos actuales](https://doc.ecowitt.net/web/#/apiv3en?page_id=17).
- [Introducción, acceso y límites oficiales](https://doc.ecowitt.net/web/#/apiv3en?page_id=1).
- [Página de producto que enlaza la documentación oficial](https://api.ecowitt.net/api/quickstart/product?id=178).

La documentación se verificó mediante el contenido que carga su aplicación web.
No se extrajeron credenciales del dashboard ni se usaron claves de terceros.
`PHC0G3` identifica la autorización del enlace compartido: **no es una MAC ni una
credencial de la API oficial**. Ese enlace no proporciona los datos necesarios
para autenticar esta integración.

```text
GET https://api.ecowitt.net/api/v3/device/real_time
application_key=<ECOWITT_APPLICATION_KEY>
api_key=<ECOWITT_API_KEY>
mac=<ECOWITT_MAC>
call_back=outdoor,wind,pressure,rainfall,rainfall_piezo,solar_and_uvi
temp_unitid=1
pressure_unitid=3
wind_speed_unitid=7
rainfall_unitid=12
solar_irradiance_unitid=16
```

Las unidades solicitadas son °C, hPa, km/h, mm y W/m². La API también admite
`imei` como alternativa a `mac`; la integración actual configura una MAC.
Ambas claves se crean en la cuenta Ecowitt autorizada para el dispositivo.
La introducción publica límites de 3 solicitudes/s por aplicación y 1/s por
API key; la caché del backend reduce las consultas.

Una respuesta correcta tiene `code=0` y un objeto `data`. Cada medición contiene
`value` numérico representado como texto, `unit` y `time` Unix en segundos.

| Medición | Campo bajo `data` |
| --- | --- |
| Temperatura, humedad | `outdoor.temperature`, `outdoor.humidity` |
| Sensación, punto de rocío | `outdoor.feels_like`, `outdoor.dew_point` |
| Viento, ráfaga, dirección | `wind.wind_speed`, `wind.wind_gust`, `wind.wind_direction` |
| Presión relativa, absoluta | `pressure.relative`, `pressure.absolute` |
| Lluvia acumulada hora, día | `rainfall.hourly`, `rainfall.daily` |
| Intensidad de lluvia | `rainfall.rain_rate` |
| UV, radiación | `solar_and_uvi.uvi`, `solar_and_uvi.solar` |

`rainfall_piezo` ofrece el mismo grupo de lluvia para sensores piezoeléctricos.
No sumar ambas familias como si fueran estaciones distintas. Conservar los
timestamps de mediciones: el `time` general de la respuesta no acredita que una
observación sea reciente. La API puede retornar mediciones de las últimas dos
horas; se aplica además el umbral local de antigüedad.

## Weather Underground: observación de IPAYSA15

- [Dashboard Yacht Club Paysandú](https://www.wunderground.com/dashboard/pws/IPAYSA15).
- [PWS Current Observations: contrato oficial](https://developer.weather.com/docs/openapi/pws-current-observations-2-0/get-v2-pws-observations-current).
- [Descripción oficial de la API](https://developer.weather.com/docs/openapi/pws-current-observations-2-0).
- [Gestión de API keys de la cuenta](https://www.wunderground.com/member/api-keys), que requiere iniciar sesión.

```text
GET https://api.weather.com/v2/pws/observations/current
stationId=IPAYSA15
format=json
units=m
numericPrecision=decimal
apiKey=<WUNDERGROUND_API_KEY>
```

Se requiere una API key válida con acceso a este servicio. El station ID no es
una clave y tampoco sustituye esa credencial. El dashboard confirma nombre e
identidad de la estación; su copia web no se utiliza para decidir disponibilidad
en vivo ni para extraer observaciones.

La respuesta contiene `observations`. El registro incluye `stationID`, `epoch`,
`obsTimeUtc`, `humidity`, `winddir` y `qcStatus`; las mediciones están bajo
`metric`: `temp`, `heatIndex`, `windChill`, `windSpeed`, `windGust`, `pressure`,
`precipRate` y `precipTotal`. Con `units=m`, temperatura, velocidad, presión y
precipitación se expresan en °C, km/h, hPa y mm. El registro original determina
la hora de observación.

`heatIndex` y `windChill` son magnitudes diferentes; no inferir una sensación
térmica genérica sin una regla documentada. Los valores ausentes se conservan
como `null`.

## Precipitación: acumulado e intensidad

| Campo | Significado para la integración |
| --- | --- |
| Ecowitt `rainfall.hourly` / `rainfall_piezo.hourly` | Acumulado horario en mm: admite `rain_1h_mm` |
| Ecowitt `rain_rate` | Intensidad en mm/h: admite `rain_rate_mmh` |
| Weather Underground `precipRate` | Intensidad en mm/h: admite `rain_rate_mmh` |
| Weather Underground `precipTotal` | Total informado por el proveedor; no acredita acumulado de la última hora |
| Open-Meteo horario `precipitation` | Precipitación prevista durante la hora precedente, en mm |

`rain_1h_mm` de Weather Underground queda `null`. No convertir una intensidad
en acumulado multiplicando por una hora: implicaría inventar que la intensidad
se mantuvo constante. Una intensidad positiva puede comunicar lluvia registrada
sin fabricar ese acumulado. Los acumulados observados y previstos no se mezclan.

## Open-Meteo: pronóstico horario y diario

- [Documentación oficial Forecast API](https://open-meteo.com/en/docs).
- [Acceso, atribución y límites](https://open-meteo.com/en/pricing).
- [Condiciones de uso](https://open-meteo.com/en/terms).

```text
GET https://api.open-meteo.com/v1/forecast
latitude=<CONDITIONS_LATITUDE>
longitude=<CONDITIONS_LONGITUDE>
hourly=temperature_2m,relative_humidity_2m,precipitation,precipitation_probability,wind_speed_10m,wind_gusts_10m,wind_direction_10m,weather_code
daily=temperature_2m_min,temperature_2m_max,wind_speed_10m_max,wind_gusts_10m_max,precipitation_probability_max,precipitation_sum,weather_code
forecast_days=2
timezone=America/Montevideo
timeformat=unixtime
temperature_unit=celsius
wind_speed_unit=kmh
precipitation_unit=mm
```

`hourly` y `daily` contienen arrays paralelos indexados por `time`;
`hourly_units` y `daily_units` describen sus unidades. Humedad y probabilidad
son porcentajes, dirección son grados y `weather_code` es un código WMO.
La ráfaga horaria es el máximo de la hora precedente. `precipitation_sum` es
el acumulado diario previsto y `precipitation_probability_max` la probabilidad
horaria máxima del día. Las coordenadas retornadas corresponden a una celda
del modelo, no a una estación local medida.

### Timestamps: comprobación real

Se realizó una consulta sin secretos para las coordenadas aproximadas
`-32.31,-58.10`, con las ocho variables horarias y agregaciones diarias, dos días,
`timeformat=unixtime` y `timezone=America/Montevideo`. Devolvió 48 horas y dos
fechas diarias, unidades métricas y `utc_offset_seconds=-10800`.

El primer timestamp horario y diario fue `1789441200`:

```text
2026-09-15T03:00:00Z = 2026-09-15T00:00:00-03:00
```

Por tanto, interpretar el Unix timestamp como instante UTC y convertirlo a
`ZoneInfo("America/Montevideo")` antes de obtener la fecha local. No sumar el
offset al timestamp y después volver a convertir a la zona local. La indicación
documental de aplicar el offset para obtener la fecha se cumple con esta
conversión. Con `timeformat=iso8601`, las horas vienen como hora local conforme
a `timezone`; no deben interpretarse automáticamente como UTC.

### Acceso y atribución

El endpoint público no necesita API key para uso no comercial dentro de sus
límites publicados. Los datos están bajo CC BY 4.0 y requieren atribución:
mantener un enlace visible «Pronóstico: Open-Meteo». La licencia de los datos
y las condiciones del servicio son distintas; el uso comercial del servicio
requiere su plan correspondiente. El endpoint comercial documentado es
`customer-api.open-meteo.com` y utiliza el parámetro `apikey`.

## Configuración pendiente y alcance de la verificación

Configurar exclusivamente en backend, con valores reales autorizados:

```dotenv
ECOWITT_APPLICATION_KEY=
ECOWITT_API_KEY=
ECOWITT_MAC=
WUNDERGROUND_API_KEY=
```

La investigación verificó contratos oficiales y una respuesta real de pronóstico.
No acredita conectividad autenticada con las dos estaciones: faltan las claves
y la MAC de Pescadores. Hasta configurarlas, la integración debe informar cada
estación sin datos y permitir que el pronóstico siga funcionando. No modificar
`.env` con ejemplos ficticios ni enviar credenciales al frontend, logs o errores.

Consultar la configuración de `apps/conditions/config.py` y la documentación
operativa de la funcionalidad para caché, timeouts, antigüedad y endpoints del club.
