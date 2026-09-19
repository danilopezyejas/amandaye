import type { ForecastHour, Observation, WeatherMeasurements } from './types.ts';

const numberFormat = new Intl.NumberFormat('es-UY', { maximumFractionDigits: 1 });
const localTime = new Intl.DateTimeFormat('es-UY', {
  timeZone: 'America/Montevideo', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
});
const localDate = new Intl.DateTimeFormat('es-UY', {
  timeZone: 'America/Montevideo', day: 'numeric', month: 'short',
});

export function hasNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

export function formatNumber(value: number | null | undefined): string {
  return hasNumber(value) ? numberFormat.format(value) : '—';
}

export function ageMinutes(timestamp: string | null | undefined, now: number): number | null {
  const observedAt = timestamp ? Date.parse(timestamp) : NaN;
  return Number.isFinite(observedAt) ? Math.max(0, (now - observedAt) / 60_000) : null;
}

export function ageText(timestamp: string | null | undefined, now: number): string {
  const age = ageMinutes(timestamp, now);
  if (age === null) return 'antigüedad no disponible';
  if (age < 1) return 'hace menos de 1 min';
  if (age < 60) return `hace ${Math.floor(age)} min`;
  if (age < 1440) return `hace ${Math.floor(age / 60)} h ${Math.floor(age % 60)} min`;
  return `hace ${Math.floor(age / 1440)} días ${Math.floor((age % 1440) / 60)} h`;
}

export function isObservationStale(observation: Observation, now: number, staleAfterMinutes: number): boolean {
  const age = ageMinutes(observation.timestamp, now);
  return observation.stale || age === null || age > staleAfterMinutes;
}

export function observationAge(observation: Observation, now: number, staleAfterMinutes: number): string {
  if (!observation.timestamp) return 'Antigüedad no disponible';
  const prefix = isObservationStale(observation, now, staleAfterMinutes) ? 'Datos de' : 'Actualizado';
  return `${prefix} ${ageText(observation.timestamp, now)}`;
}

export function formatHour(timestamp: string): string {
  const date = new Date(timestamp);
  return Number.isFinite(date.getTime()) ? localTime.format(date) : '—';
}

export function dateKey(timestamp: number): string {
  // Build an ISO day in Paysandú, even when the phone uses another time zone.
  const parts = new Intl.DateTimeFormat('en', {
    timeZone: 'America/Montevideo', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(timestamp);
  const part = (type: string) => parts.find((value) => value.type === type)?.value;
  return `${part('year')}-${part('month')}-${part('day')}`;
}

export function dayLabel(day: string, now: number): string {
  if (day === dateKey(now)) return 'Hoy';
  const date = new Date(`${day}T12:00:00-03:00`);
  return Number.isFinite(date.getTime()) ? localDate.format(date) : day;
}

export function upcomingHours(hours: ForecastHour[], now: number): ForecastHour[] {
  // Retain the current hourly period but never label yesterday's hours as upcoming.
  const startOfHour = Math.floor(now / 3_600_000) * 3_600_000;
  return hours.filter((hour) => Date.parse(hour.timestamp) >= startOfHour).slice(0, 12);
}

export function directionLabel(value: Pick<WeatherMeasurements, 'wind_direction_deg' | 'wind_direction_cardinal' | 'wind_direction_ambiguous'>): string {
  if (value.wind_direction_ambiguous) return 'Variable / no definida';
  const degrees = hasNumber(value.wind_direction_deg) ? `${formatNumber(value.wind_direction_deg)}°` : '';
  return [value.wind_direction_cardinal, degrees].filter(Boolean).join(' · ') || 'Sin dato';
}

export function weatherLabel(code: number | null): string {
  if (code === null) return '';
  if (code === 0) return 'Despejado';
  if (code === 1) return 'Mayormente despejado';
  if (code === 2) return 'Parcialmente nublado';
  if (code === 3) return 'Nublado';
  if ([45, 48].includes(code)) return 'Niebla';
  if ([51, 53, 55, 56, 57].includes(code)) return 'Llovizna';
  if ([61, 63, 65, 66, 67].includes(code)) return 'Lluvia';
  if ([71, 73, 75, 77, 85, 86].includes(code)) return 'Nieve';
  if ([80, 81, 82].includes(code)) return 'Chubascos';
  if ([95, 96, 99].includes(code)) return 'Tormenta';
  return '';
}

export function rainDisplay(value: WeatherMeasurements): { label: string; value: string } {
  // A positive rain rate from one station must not be hidden by a zero hourly
  // total from another. These measurements have different observation windows.
  if (hasNumber(value.rain_rate_mmh) && value.rain_rate_mmh > 0) return { label: 'Intensidad de lluvia', value: `${formatNumber(value.rain_rate_mmh)} mm/h` };
  if (hasNumber(value.rain_1h_mm)) return { label: 'Lluvia · última hora', value: `${formatNumber(value.rain_1h_mm)} mm` };
  if (hasNumber(value.rain_rate_mmh)) return { label: 'Intensidad de lluvia', value: `${formatNumber(value.rain_rate_mmh)} mm/h` };
  if (value.rain_detected === true) return { label: 'Lluvia', value: 'Detectada' };
  if (value.rain_detected === false) return { label: 'Lluvia', value: 'No detectada' };
  return { label: 'Lluvia', value: 'Sin dato' };
}

export function stationMeasurements(value: WeatherMeasurements): { label: string; value: string }[] {
  const metrics: [string, number | null, string][] = [
    ['Viento', value.wind_speed_kmh, 'km/h'],
    ['Ráfagas', value.wind_gust_kmh, 'km/h'],
    ['Temperatura', value.temperature_c, '°C'],
    ['Humedad', value.humidity_pct, '%'],
    ['Presión', value.pressure_hpa, 'hPa'],
  ];
  const result = metrics.filter(([, metric]) => hasNumber(metric)).map(([label, metric, unit]) => ({
    label, value: `${formatNumber(metric)} ${unit}`,
  }));
  if (directionLabel(value) !== 'Sin dato') result.splice(2, 0, { label: 'Viento desde', value: directionLabel(value) });
  if (hasNumber(value.rain_1h_mm)) result.push({ label: 'Lluvia · última hora', value: `${formatNumber(value.rain_1h_mm)} mm` });
  if (hasNumber(value.rain_rate_mmh)) result.push({ label: 'Intensidad de lluvia', value: `${formatNumber(value.rain_rate_mmh)} mm/h` });
  if (!hasNumber(value.rain_1h_mm) && !hasNumber(value.rain_rate_mmh)) {
    const rain = rainDisplay(value);
    if (rain.value !== 'Sin dato') result.push(rain);
  }
  return result;
}
