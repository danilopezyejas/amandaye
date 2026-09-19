<template>
  <div class="space-y-6">
    <div v-if="loading && !data" role="status" class="space-y-6" aria-label="Cargando condiciones del río">
      <span class="sr-only">Cargando condiciones del río…</span>
      <div class="min-h-80 rounded-3xl border border-white/10 bg-black/20 p-6 motion-safe:animate-pulse" aria-hidden="true">
        <div class="h-4 w-28 rounded bg-white/15"></div>
        <div class="mt-9 h-16 w-44 rounded-xl bg-white/15"></div>
        <div class="mt-7 h-12 w-full rounded-xl bg-white/10"></div>
        <div class="mt-6 h-4 w-48 rounded bg-white/10"></div>
      </div>
      <div class="h-64 rounded-3xl border border-white/10 bg-white/5 motion-safe:animate-pulse" aria-hidden="true"></div>
    </div>

    <div v-if="error" role="status" class="rounded-2xl border border-orange-400/40 bg-orange-400/10 p-4 text-sm text-orange-100">
      <p class="font-semibold">{{ data ? 'Últimos datos disponibles' : 'No se pudieron obtener las condiciones' }}</p>
      <p class="mt-1">{{ data ? 'No se pudo actualizar. Revisá la antigüedad de cada dato.' : 'Revisá tu conexión. Volveremos a intentar automáticamente.' }}</p>
    </div>

    <template v-if="data">
      <section aria-labelledby="current-heading" class="overflow-hidden rounded-3xl border border-white/15 bg-black/20 shadow-xl shadow-blue-950/20">
        <div class="p-5 sm:p-7">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <h2 id="current-heading" class="text-sm font-bold uppercase tracking-widest text-orange-300">Condiciones actuales</h2>
            <span class="text-xs text-blue-200">Observaciones locales</span>
          </div>

          <template v-if="current?.available">
            <p v-if="currentStale || current.last_known" class="mt-4 rounded-xl border border-orange-400/40 bg-orange-400/10 px-3 py-2 text-sm font-medium text-orange-100">
              {{ currentStale ? 'Datos antiguos · Últimas observaciones disponibles' : 'Últimos datos disponibles · La fuente no pudo actualizarse' }}
            </p>
            <div class="mt-6 grid grid-cols-2 gap-4 sm:gap-8">
              <div>
                <p class="text-base text-blue-100">Viento</p>
                <p class="mt-2 flex flex-wrap items-baseline gap-x-2 tabular-nums">
                  <span class="text-5xl font-extrabold tracking-tight sm:text-6xl">{{ formatNumber(current.wind_speed_kmh) }}</span>
                  <span class="text-sm font-medium text-blue-200">km/h</span>
                </p>
              </div>
              <div class="border-l border-white/15 pl-4 sm:pl-8">
                <p class="text-base text-blue-100">Ráfagas</p>
                <p class="mt-2 flex flex-wrap items-baseline gap-x-2 tabular-nums">
                  <span class="text-4xl font-bold tracking-tight text-orange-300 sm:text-5xl">{{ formatNumber(current.wind_gust_kmh) }}</span>
                  <span class="text-sm font-medium text-blue-200">km/h</span>
                </p>
              </div>
            </div>

            <div class="mt-6 flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 p-3">
              <span class="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-blue-950/60 text-orange-300">
                <!-- The arrow points toward the meteorological origin; the label explicitly says Desde. -->
                <svg v-if="hasNumber(current.wind_direction_deg)" aria-hidden="true" class="h-7 w-7" :style="{ transform: `rotate(${current.wind_direction_deg}deg)` }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 20V4m-6 6 6-6 6 6" /></svg>
                <span v-else aria-hidden="true">—</span>
              </span>
              <div>
                <p class="text-xs text-blue-200">Viento desde</p>
                <p class="text-lg font-semibold">{{ directionLabel(current) }}</p>
              </div>
            </div>

            <dl class="mt-6 grid grid-cols-2 gap-x-5 gap-y-5 sm:grid-cols-4">
              <div>
                <dt class="text-xs text-blue-200">{{ rainDisplay(current).label }}</dt>
                <dd class="mt-1 text-lg font-semibold tabular-nums">{{ rainDisplay(current).value }}</dd>
              </div>
              <div>
                <dt class="text-xs text-blue-200">Temperatura</dt>
                <dd class="mt-1 text-lg font-semibold tabular-nums">{{ formatNumber(current.temperature_c) }} <span class="text-sm font-normal text-blue-200">°C</span></dd>
              </div>
              <div>
                <dt class="text-xs text-blue-200">Humedad</dt>
                <dd class="mt-1 text-lg font-semibold tabular-nums">{{ formatNumber(current.humidity_pct) }} <span class="text-sm font-normal text-blue-200">%</span></dd>
              </div>
              <div>
                <dt class="text-xs text-blue-200">Presión</dt>
                <dd class="mt-1 text-lg font-semibold tabular-nums">{{ formatNumber(current.pressure_hpa) }} <span class="text-sm font-normal text-blue-200">hPa</span></dd>
              </div>
            </dl>
            <p class="mt-6 text-sm text-blue-100">Basado en {{ current.stations_available }} {{ current.stations_available === 1 ? 'estación local' : 'estaciones locales' }}</p>
            <p class="mt-1 text-sm" :class="currentStale ? 'text-orange-200' : 'text-blue-200'">
              <time :datetime="current.timestamp || undefined">{{ observationAge(current, now, staleAfterMinutes) }}</time>
            </p>
            <p v-if="current.refreshing" class="mt-2 text-xs text-blue-200">Actualizando las fuentes locales…</p>
          </template>
          <div v-else class="flex min-h-56 flex-col justify-center py-6">
            <p class="max-w-md text-xl font-semibold leading-relaxed">Datos meteorológicos locales temporalmente no disponibles</p>
            <p class="mt-3 text-sm leading-relaxed text-blue-200">Las estaciones locales no están aportando observaciones en este momento.</p>
          </div>
          <p v-if="data.weather.comparison.significant" class="mt-5 rounded-xl border border-orange-400/30 bg-orange-400/10 px-3 py-2 text-sm text-orange-100">
            Las estaciones presentan diferencias significativas.
          </p>
        </div>
      </section>

      <section aria-labelledby="forecast-heading" class="rounded-3xl border border-white/10 bg-black/15 p-5 sm:p-7">
        <div class="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="forecast-heading" class="text-xl font-bold">Próximas horas</h2>
          <span class="text-xs font-medium uppercase tracking-wider text-blue-200">Pronóstico</span>
        </div>
        <p class="mt-2 text-xs leading-relaxed text-blue-200">
          Pronóstico de <a :href="data.forecast.source_url" target="_blank" rel="noopener noreferrer" class="inline-flex min-h-6 items-center underline underline-offset-4 hover:text-orange-300 focus-visible:outline-2 focus-visible:outline-orange-400">Open-Meteo</a>
          <template v-if="data.forecast.fetched_at"> · Consultado <time :datetime="data.forecast.fetched_at">{{ ageText(data.forecast.fetched_at, now) }}</time></template>
        </p>
        <p v-if="forecastOld" class="mt-3 text-sm font-medium text-orange-200">Pronóstico anterior · Pendiente de actualización.</p>
        <p v-else-if="data.forecast.refreshing" class="mt-3 text-xs text-blue-200">Actualizando la fuente del pronóstico…</p>

        <template v-if="data.forecast.available">
          <div v-if="hours.length" class="-mx-1 mt-5 overflow-x-auto rounded-xl pb-3 focus-visible:outline-2 focus-visible:outline-orange-400" tabindex="0" aria-label="Pronóstico por hora, desplazable horizontalmente">
            <ol class="flex gap-3 px-1">
              <li v-for="hour in hours" :key="hour.timestamp" class="w-40 shrink-0 rounded-2xl border border-white/10 bg-white/5 p-4">
                <time :datetime="hour.timestamp" class="text-base font-bold">{{ formatHour(hour.timestamp) }}</time>
                <span v-if="dateKey(Date.parse(hour.timestamp)) !== dateKey(now)" class="ml-1 text-xs text-blue-200">{{ dayLabel(dateKey(Date.parse(hour.timestamp)), now) }}</span>
                <p class="mt-3 text-xl font-bold tabular-nums">{{ formatNumber(hour.wind_speed_kmh) }} <span class="text-xs font-normal text-blue-200">km/h</span></p>
                <p class="mt-1 text-sm text-orange-200">Ráf. {{ formatNumber(hour.wind_gust_kmh) }} km/h</p>
                <p class="mt-2 text-xs text-blue-100">Desde {{ directionLabel(hour) }}</p>
                <dl class="mt-4 space-y-2 border-t border-white/10 pt-3 text-xs">
                  <div class="flex items-center justify-between gap-1"><dt class="text-blue-200">Lluvia</dt><dd>{{ formatNumber(hour.precipitation_probability_pct) }} %</dd></div>
                  <div class="flex items-center justify-between gap-1"><dt class="text-blue-200">Cantidad</dt><dd>{{ formatNumber(hour.precipitation_mm) }} mm</dd></div>
                  <div class="flex items-center justify-between gap-1"><dt class="text-blue-200">Temp.</dt><dd>{{ formatNumber(hour.temperature_c) }} °C</dd></div>
                </dl>
                <p v-if="weatherLabel(hour.weather_code)" class="mt-3 text-xs text-blue-200">{{ weatherLabel(hour.weather_code) }}</p>
              </li>
            </ol>
          </div>
          <p v-else class="py-6 text-sm text-blue-100">No hay horas de pronóstico vigentes disponibles.</p>

          <div v-if="data.forecast.daily" class="mt-4 border-t border-white/15 pt-5">
            <h3 class="text-base font-bold">{{ dayLabel(data.forecast.daily.date, now) }} <span class="ml-1 text-xs font-normal text-blue-200">· Resumen previsto</span></h3>
            <dl class="mt-4 grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
              <div><dt class="text-xs text-blue-200">Temperatura</dt><dd class="mt-1 font-semibold">{{ formatNumber(data.forecast.daily.temperature_min_c) }}–{{ formatNumber(data.forecast.daily.temperature_max_c) }} °C</dd><dd class="mt-1 text-xs text-blue-200">Mínima–máxima</dd></div>
              <div><dt class="text-xs text-blue-200">Viento</dt><dd class="mt-1 font-semibold">{{ formatNumber(data.forecast.daily.wind_speed_min_kmh) }}–{{ formatNumber(data.forecast.daily.wind_speed_max_kmh) }} km/h</dd></div>
              <div><dt class="text-xs text-blue-200">Ráfagas máximas</dt><dd class="mt-1 font-semibold">{{ formatNumber(data.forecast.daily.wind_gust_max_kmh) }} km/h</dd></div>
              <div><dt class="text-xs text-blue-200">Probabilidad de lluvia</dt><dd class="mt-1 font-semibold">{{ formatNumber(data.forecast.daily.precipitation_probability_max_pct) }} %</dd></div>
              <div><dt class="text-xs text-blue-200">Lluvia prevista</dt><dd class="mt-1 font-semibold">{{ formatNumber(data.forecast.daily.precipitation_sum_mm) }} mm</dd></div>
              <div v-if="weatherLabel(data.forecast.daily.weather_code)"><dt class="text-xs text-blue-200">Pronóstico del día</dt><dd class="mt-1 font-semibold">{{ weatherLabel(data.forecast.daily.weather_code) }}</dd></div>
            </dl>
          </div>
        </template>
        <p v-else class="py-6 text-sm leading-relaxed text-blue-100">Pronóstico temporalmente no disponible.</p>
        <p class="mt-4 text-xs text-blue-200">Horarios de Paysandú, Uruguay.</p>
      </section>

      <details class="group rounded-2xl border border-white/15 bg-black/15">
        <summary class="min-h-14 cursor-pointer rounded-2xl px-5 py-4 text-sm font-semibold marker:text-orange-300 hover:bg-white/5 focus-visible:outline-2 focus-visible:outline-orange-400 sm:px-7">Ver estaciones meteorológicas</summary>
        <div class="grid gap-4 px-4 pb-4 sm:grid-cols-2 sm:px-5 sm:pb-5">
          <article v-for="source in data.weather.sources" :key="source.id" class="rounded-2xl border border-white/10 bg-white/5 p-4">
            <h3 class="font-bold">{{ source.name }}</h3>
            <p class="mt-1 text-xs text-blue-200">Fuente: {{ source.provider === 'ecowitt' ? 'Ecowitt' : source.provider === 'wunderground' ? 'Weather Underground' : source.provider }}</p>
            <template v-if="source.available">
              <p v-if="source.last_known" class="mt-3 text-sm text-orange-200">Últimos datos disponibles · La fuente no pudo actualizarse.</p>
              <p v-if="current?.station_ids.includes(source.id)" class="mt-3 text-xs text-blue-100">Utilizada en las condiciones actuales</p>
              <p v-else class="mt-3 text-xs text-blue-200">Sin uso en las condiciones actuales</p>
              <p class="mt-2 text-sm" :class="isObservationStale(source, now, staleAfterMinutes) ? 'text-orange-200' : 'text-blue-100'">
                <time :datetime="source.timestamp || undefined">{{ observationAge(source, now, staleAfterMinutes) }}</time>
              </p>
              <dl class="mt-4 space-y-3 text-sm">
                <div v-for="metric in stationMeasurements(source)" :key="metric.label" class="flex justify-between gap-3"><dt class="text-blue-200">{{ metric.label }}</dt><dd class="text-right font-semibold tabular-nums">{{ metric.value }}</dd></div>
              </dl>
            </template>
            <p v-else class="mt-4 text-sm text-blue-100">Datos temporalmente no disponibles</p>
            <a :href="source.source_url" target="_blank" rel="noopener noreferrer" class="mt-4 inline-flex min-h-11 items-center rounded-lg text-xs font-medium text-blue-200 underline underline-offset-4 hover:text-orange-300 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-400">Ver fuente pública<span class="sr-only">: {{ source.name }} (abre en otra pestaña)</span></a>
          </article>
        </div>
      </details>
    </template>

    <div v-if="!loading || data" class="flex flex-wrap items-center justify-between gap-3">
      <p role="status" class="text-xs text-blue-200">{{ refreshing ? 'Actualizando…' : 'Actualización automática cada 5 minutos' }}</p>
      <button type="button" class="btn-secondary min-h-11 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-400" :disabled="refreshing" @click="$emit('refresh')">Actualizar ahora</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { ConditionsResponse } from '../conditions/types';
import {
  ageMinutes, ageText, dateKey, dayLabel, directionLabel, formatHour, formatNumber, hasNumber,
  isObservationStale, observationAge, rainDisplay, stationMeasurements, upcomingHours, weatherLabel,
} from '../conditions/presentation';

const props = defineProps<{
  data: ConditionsResponse | null;
  loading: boolean;
  refreshing: boolean;
  error: boolean;
  now: number;
}>();
defineEmits<{ refresh: [] }>();
const current = computed(() => props.data?.weather.current);
const staleAfterMinutes = computed(() => props.data?.meta.stale_after_minutes ?? 20);
const currentStale = computed(() => current.value && isObservationStale(current.value, props.now, staleAfterMinutes.value));
const hours = computed(() => upcomingHours(props.data?.forecast.hourly ?? [], props.now));
const forecastOld = computed(() => {
  if (!props.data?.forecast.available) return false;
  const age = ageMinutes(props.data.forecast.fetched_at, props.now);
  return props.data.forecast.stale || age === null || age * 60 > props.data.meta.forecast_stale_after_seconds;
});
</script>
