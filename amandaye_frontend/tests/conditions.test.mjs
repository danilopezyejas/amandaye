import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
import { createSSRApp } from 'vue';
import { renderToString } from '@vue/server-renderer';
import { compileScript, parse } from '@vue/compiler-sfc';
import ts from 'typescript';
import { createConditionsFeed, REFRESH_INTERVAL_MS } from '../src/conditions/feed.ts';
import * as presentation from '../src/conditions/presentation.ts';
import { createApiClients } from '../src/api/client.ts';

// Compile the real Vue template using the project's existing compiler/runtime.
// Node's built-in runner remains the only test harness; no DOM package is needed.
const require = createRequire(import.meta.url);
const filename = new URL('../src/components/ConditionsDashboard.vue', import.meta.url);
const { descriptor } = parse(readFileSync(filename, 'utf8'));
const compiled = compileScript(descriptor, { id: 'conditions-tests', inlineTemplate: true });
const compiledJs = ts.transpileModule(compiled.content, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const componentModule = { exports: {} };
new Function('require', 'module', 'exports', compiledJs)(
  (id) => id === '../conditions/presentation' ? presentation : require(id),
  componentModule,
  componentModule.exports,
);
const Dashboard = componentModule.exports.default;
const NOW = Date.parse('2026-09-15T12:05:00Z');

function fixture() {
  const metrics = {
    temperature_c: 21.1, humidity_pct: 73, pressure_hpa: 1014,
    wind_speed_kmh: 15.2, wind_gust_kmh: 26, wind_direction_deg: 135,
    wind_direction_cardinal: 'SE', rain_1h_mm: 0, rain_rate_mmh: null,
    rain_detected: false,
  };
  const observation = {
    ...metrics, available: true, stale: false, timestamp: '2026-09-15T12:03:00Z', age_minutes: 2,
  };
  return {
    weather: {
      current: { ...observation, stations_available: 2, station_ids: ['pescadores', 'yacht'], fallback: null },
      sources: [
        { ...observation, id: 'pescadores', name: 'Club de Pescadores', provider: 'ecowitt', location: 'Paysandú', source_url: 'https://www.ecowitt.net/home/share?authorize=PHC0G3' },
        { ...observation, id: 'yacht', name: 'Yacht Club Paysandú', provider: 'wunderground', location: 'Paysandú', source_url: 'https://www.wunderground.com/dashboard/pws/IPAYSA15' },
      ],
      comparison: { significant: false, differing_fields: [], wind_difference_kmh: 0, gust_difference_kmh: 0, temperature_difference_c: 0, pressure_difference_hpa: 0 },
    },
    forecast: {
      available: true, provider: 'open_meteo', source_url: 'https://open-meteo.com/',
      fetched_at: '2026-09-15T12:00:00Z', age_minutes: 5, stale: false,
      hourly: [{ ...metrics, timestamp: '2026-09-15T12:00:00Z', precipitation_mm: 0.2, precipitation_probability_pct: 20, weather_code: 2 }],
      daily: { date: '2026-09-15', temperature_min_c: 16, temperature_max_c: 24, wind_speed_min_kmh: 12, wind_speed_max_kmh: 26, wind_gust_max_kmh: 34, precipitation_probability_max_pct: 20, precipitation_sum_mm: 0.5, weather_code: 2 },
    },
    meta: { generated_at: '2026-09-15T12:05:00Z', stale_after_minutes: 20, forecast_stale_after_seconds: 900, refresh_interval_seconds: 300 },
  };
}

function render(data = fixture(), props = {}) {
  return renderToString(createSSRApp(Dashboard, {
    data, loading: false, refreshing: false, error: false, now: NOW, ...props,
  }));
}

test('initial rendering has a loading status and stable placeholders, no fictitious measurements', async () => {
  const html = await render(null, { loading: true });
  assert.match(html, /Cargando condiciones del río/);
  assert.match(html, /role="status"/);
  assert.doesNotMatch(html, /Basado en|15,2|Pronóstico de/);
});

test('real template renders consolidated observations, direction origin, forecast and both sources', async () => {
  const html = await render();
  for (const text of ['Condiciones actuales', 'Basado en 2 estaciones locales', 'Actualizado hace 2 min', 'Viento desde', 'SE · 135°', 'Próximas horas', 'Hoy', '09:00', 'Club de Pescadores', 'Yacht Club Paysandú', 'Weather Underground']) {
    assert.ok(html.includes(text), text);
  }
  assert.match(html, /rotate\(135deg\)/);
  assert.match(html, /<details/);
  assert.match(html, /Consultado <time[^>]*>hace 5 min/);
  assert.match(html, /href="https:\/\/open-meteo.com\/"/);
});

test('one available station uses singular count and still displays the failed station', async () => {
  const data = fixture();
  data.weather.current.station_ids = ['pescadores'];
  data.weather.current.stations_available = 1;
  data.weather.sources[1].available = false;
  const html = await render(data);
  assert.match(html, /Basado en 1 estación local/);
  assert.match(html, /Yacht Club Paysandú/);
  assert.match(html, /Datos temporalmente no disponibles/);
});

test('both stations unavailable does not remove the independent forecast', async () => {
  const data = fixture();
  data.weather.current.available = false;
  data.weather.current.stations_available = 0;
  for (const source of data.weather.sources) source.available = false;
  const html = await render(data);
  assert.match(html, /Datos meteorológicos locales temporalmente no disponibles/);
  assert.match(html, /Próximas horas/);
  assert.match(html, /09:00/);
  assert.match(html, /16–24 °C/);
  assert.equal(html.match(/Datos temporalmente no disponibles/g).length, 2);
});

test('observation age advances without an API refresh and uses its timestamp, not generated_at', async () => {
  const data = fixture();
  data.meta.generated_at = '2026-09-15T12:40:00Z';
  const html = await render(data, { now: Date.parse('2026-09-15T12:40:00Z') });
  assert.match(html, /Datos antiguos/);
  assert.match(html, /Datos de hace 37 min/);
  assert.doesNotMatch(html, /Actualizado hace 2 min/);
  data.meta.stale_after_minutes = 60;
  assert.doesNotMatch(await render(data, { now: Date.parse('2026-09-15T12:40:00Z') }), /Datos antiguos/);
});

test('cached provider fallback remains explicit even when its observation is still recent', async () => {
  const data = fixture();
  data.weather.current.last_known = true;
  data.weather.sources[0].last_known = true;
  data.weather.current.wind_direction_deg = null;
  data.weather.current.wind_direction_cardinal = null;
  data.weather.current.wind_direction_ambiguous = true;
  const html = await render(data);
  assert.match(html, /Últimos datos disponibles/);
  assert.match(html, /La fuente no pudo actualizarse/);
  assert.match(html, /Variable \/ no definida/);
  assert.doesNotMatch(html, /rotate\(null/);
});

test('forecast age advances locally using the threshold supplied by Django', async () => {
  const data = fixture();
  const now = Date.parse('2026-09-15T12:16:00Z');
  assert.match(await render(data, { now }), /Pronóstico anterior · Pendiente de actualización/);
  data.meta.forecast_stale_after_seconds = 1800;
  assert.doesNotMatch(await render(data, { now }), /Pronóstico anterior/);
  data.forecast.stale = true;
  assert.match(await render(data, { now }), /Pronóstico anterior/);
});

test('missing measurements never become zero; rainfall rate keeps its own unit', async () => {
  const data = fixture();
  for (const value of [data.weather.current, ...data.weather.sources]) {
    value.temperature_c = null;
    value.rain_1h_mm = null;
    value.rain_rate_mmh = 1.5;
  }
  const html = await render(data);
  assert.match(html, /Intensidad de lluvia/);
  assert.match(html, /1,5 mm\/h/);
  assert.match(html, /—/);
  assert.equal(presentation.formatNumber(null), '—');
  assert.equal(presentation.formatNumber(0), '0');
  assert.equal(presentation.stationMeasurements(data.weather.sources[0]).some((metric) => metric.label === 'Temperatura'), false);
});

test('positive rain rate is visible even when another station reports a zero hourly total', async () => {
  const data = fixture();
  data.weather.current.rain_1h_mm = 0;
  data.weather.current.rain_rate_mmh = 2;
  data.weather.current.rain_detected = true;
  const html = await render(data);
  assert.match(html, /Intensidad de lluvia/);
  assert.match(html, /2 mm\/h/);
  assert.deepEqual(presentation.rainDisplay(data.weather.current), { label: 'Intensidad de lluvia', value: '2 mm/h' });
  data.weather.current.rain_1h_mm = 1.5;
  data.weather.current.rain_rate_mmh = 0;
  assert.deepEqual(presentation.rainDisplay(data.weather.current), { label: 'Lluvia · última hora', value: '1,5 mm' });
  const metrics = presentation.stationMeasurements(data.weather.current);
  assert.ok(metrics.some((metric) => metric.label === 'Lluvia · última hora' && metric.value === '1,5 mm'));
  assert.ok(metrics.some((metric) => metric.label === 'Intensidad de lluvia' && metric.value === '0 mm/h'));
});

test('failed forecast and differences are readable alongside observations', async () => {
  const data = fixture();
  data.forecast.available = false;
  data.weather.comparison.significant = true;
  const html = await render(data, { error: true });
  assert.match(html, /Pronóstico temporalmente no disponible/);
  assert.match(html, /Las estaciones presentan diferencias significativas/);
  assert.match(html, /Últimos datos disponibles/);
  assert.match(html, /Basado en 2 estaciones locales/);
});

test('hourly and daily labels use Paysandú time and remove past forecast periods', async () => {
  const data = fixture();
  const nextDay = Date.parse('2026-09-16T03:10:00Z');
  const html = await render(data, { now: nextDay });
  assert.match(html, /No hay horas de pronóstico vigentes/);
  assert.doesNotMatch(html, />Hoy /);
  assert.equal(presentation.dateKey(Date.parse('2026-09-16T02:59:00Z')), '2026-09-15');
  assert.equal(presentation.formatHour('2026-09-16T03:00:00Z'), '00:00');
});

class Visibility extends EventTarget {
  visibilityState = 'visible';
  listeners = new Set();
  addEventListener(name, callback) { this.listeners.add(callback); super.addEventListener(name, callback); }
  removeEventListener(name, callback) { this.listeners.delete(callback); super.removeEventListener(name, callback); }
  change(state) { this.visibilityState = state; this.dispatchEvent(new Event('visibilitychange')); }
}

const settle = () => new Promise((resolve) => setImmediate(resolve));

function feedFixture(fetcher = async () => fixture()) {
  let time = NOW;
  let sequence = 0;
  const timers = new Map();
  const visibility = new Visibility();
  const signals = [];
  const feed = createConditionsFeed({
    clock: () => time,
    visibility,
    schedule: (callback, interval) => { const id = ++sequence; timers.set(id, { callback, interval }); return id; },
    unschedule: (id) => timers.delete(id),
    fetchConditions: (signal) => { signals.push(signal); return fetcher(signal); },
  });
  return {
    feed, timers, visibility, signals,
    elapse(ms) { time += ms; },
    async tick(interval = REFRESH_INTERVAL_MS) {
      for (const timer of timers.values()) if (timer.interval === interval) timer.callback();
      await settle();
    },
  };
}

test('automatic refresh every five minutes is silent and keeps existing values while loading', async () => {
  let release;
  let calls = 0;
  const state = feedFixture(() => ++calls === 1 ? Promise.resolve(fixture()) : new Promise((resolve) => { release = resolve; }));
  state.feed.start();
  state.feed.start();
  await settle();
  assert.equal(calls, 1);
  assert.equal(state.timers.size, 2);
  assert.equal(state.visibility.listeners.size, 1);
  const previous = state.feed.data.value;
  state.elapse(REFRESH_INTERVAL_MS);
  await state.tick();
  assert.equal(calls, 2);
  assert.equal(state.feed.loading.value, false);
  assert.equal(state.feed.refreshing.value, true);
  assert.equal(state.feed.data.value, previous);
  const updated = fixture();
  updated.weather.current.wind_speed_kmh = 19;
  release(updated);
  await settle();
  assert.equal(state.feed.data.value.weather.current.wind_speed_kmh, 19);
  state.feed.stop();
});

test('return from a hidden PWA refreshes immediately after five minutes, never before', async () => {
  const state = feedFixture();
  state.feed.start();
  await settle();
  state.visibility.change('hidden');
  state.elapse(REFRESH_INTERVAL_MS - 1);
  state.visibility.change('visible');
  await settle();
  assert.equal(state.signals.length, 1);
  state.visibility.change('hidden');
  state.elapse(2);
  await state.tick();
  assert.equal(state.signals.length, 1);
  state.visibility.change('visible');
  await settle();
  assert.equal(state.signals.length, 2);
  assert.equal(state.feed.now.value, NOW + REFRESH_INTERVAL_MS + 1);
  state.feed.stop();
});

test('network failure preserves the last response and later refresh recovers', async () => {
  let fail = false;
  const state = feedFixture(async () => { if (fail) throw new Error('Network error'); return fixture(); });
  state.feed.start();
  await settle();
  const previous = state.feed.data.value;
  fail = true;
  state.elapse(REFRESH_INTERVAL_MS);
  await state.tick();
  assert.equal(state.feed.data.value, previous);
  assert.equal(state.feed.error.value, true);
  fail = false;
  await state.feed.refresh();
  assert.equal(state.feed.error.value, false);
  state.feed.stop();
});

test('initial failure and malformed response exit loading without inventing data', async () => {
  const state = feedFixture(async () => { throw new Error('offline'); });
  state.feed.start();
  await settle();
  assert.equal(state.feed.loading.value, false);
  assert.equal(state.feed.data.value, null);
  assert.equal(state.feed.error.value, true);
  state.feed.stop();
  const malformed = feedFixture(async () => ({ forecast: { hourly: [] } }));
  malformed.feed.start();
  await settle();
  assert.equal(malformed.feed.data.value, null);
  assert.equal(malformed.feed.error.value, true);
  malformed.feed.stop();
});

test('overlapping refreshes are deduplicated, stop cleans both timers, listener and request', async () => {
  let release;
  const state = feedFixture(() => new Promise((resolve) => { release = resolve; }));
  state.feed.start();
  await state.feed.refresh();
  await state.tick();
  assert.equal(state.signals.length, 1);
  state.feed.stop();
  assert.equal(state.timers.size, 0);
  assert.equal(state.visibility.listeners.size, 0);
  assert.equal(state.signals[0].aborted, true);
  release(fixture());
  await settle();
  assert.equal(state.feed.data.value, null);
  assert.equal(state.feed.error.value, false);
  state.visibility.change('visible');
  assert.equal(state.signals.length, 1);
});

test('the age clock advances without extra network requests', async () => {
  const state = feedFixture();
  state.feed.start();
  await settle();
  state.elapse(30_000);
  await state.tick(30_000);
  assert.equal(state.feed.now.value, NOW + 30_000);
  assert.equal(state.signals.length, 1);
  state.feed.stop();
});

test('a cold-cache response being refreshed retries soon and recovers before five minutes', async () => {
  let calls = 0;
  const pending = fixture();
  pending.weather.current.available = false;
  pending.weather.sources[0].available = false;
  pending.weather.sources[0].refreshing = true;
  const state = feedFixture(async () => ++calls === 1 ? pending : fixture());
  state.feed.start();
  await settle();
  assert.equal(state.feed.data.value.weather.current.available, false);
  assert.equal(state.timers.size, 3);
  state.elapse(2_000);
  await state.tick(2_000);
  assert.equal(calls, 2);
  assert.equal(state.feed.data.value.weather.current.available, true);
  assert.equal(state.timers.size, 2);
  state.elapse(2_000);
  await state.tick(2_000);
  assert.equal(calls, 2);
  state.feed.stop();
});

test('cache-lease retries are bounded and regular provider errors do not trigger them', async () => {
  const pending = fixture();
  pending.forecast.available = false;
  pending.forecast.refreshing = true;
  const state = feedFixture(async () => pending);
  state.feed.start();
  await settle();
  for (let attempt = 0; attempt < 6; attempt += 1) {
    state.elapse(2_000);
    await state.tick(2_000);
  }
  assert.equal(state.signals.length, 4); // Initial request plus at most three brief retries.
  assert.equal(state.timers.size, 2);
  state.feed.stop();
  pending.forecast.refreshing = false;
  const unavailable = feedFixture(async () => pending);
  unavailable.feed.start();
  await settle();
  assert.equal(unavailable.timers.size, 2);
  unavailable.feed.stop();
});

test('stop cancels a pending cache-lease retry and an in-flight retry is never overlapped', async () => {
  const pending = fixture();
  pending.weather.current.refreshing = true;
  const stopped = feedFixture(async () => pending);
  stopped.feed.start();
  await settle();
  assert.equal(stopped.timers.size, 3);
  stopped.feed.stop();
  assert.equal(stopped.timers.size, 0);
  await stopped.tick(2_000);
  assert.equal(stopped.signals.length, 1);

  let release;
  let calls = 0;
  const running = feedFixture(() => ++calls === 1 ? Promise.resolve(pending) : new Promise((resolve) => { release = resolve; }));
  running.feed.start();
  await settle();
  running.elapse(2_000);
  await running.tick(2_000);
  await running.feed.refresh();
  await running.tick();
  assert.equal(calls, 2);
  running.feed.stop();
  assert.equal(running.signals[1].aborted, true);
  release(fixture());
  await settle();
  assert.equal(running.feed.data.value, pending);
  assert.equal(running.timers.size, 0);
});

test('conditions uses the existing public Django API and passes cancellation without credentials', async () => {
  const { publicApi } = createApiClients({
    getOrigin: () => 'https://club.example',
    getAuth: () => { throw new Error('Public conditions must not access authentication'); },
    redirectToLogin: () => { throw new Error('Public conditions must not redirect'); },
  });
  const controller = new AbortController();
  publicApi.defaults.adapter = async (config) => {
    assert.equal(config.baseURL + config.url, '/api/conditions/');
    assert.equal(config.headers.Authorization, undefined);
    assert.equal(config.signal, controller.signal);
    return { data: fixture(), status: 200, statusText: 'OK', headers: {}, config };
  };
  assert.equal((await publicApi.get('conditions/', { signal: controller.signal })).data.weather.current.available, true);
});
