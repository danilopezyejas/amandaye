import { ref, shallowRef } from 'vue';
import type { ConditionsResponse } from './types.ts';

export const REFRESH_INTERVAL_MS = 300_000;
const AGE_INTERVAL_MS = 30_000;
const LEASE_RETRY_MS = 2_000;
const MAX_LEASE_RETRIES = 3;

interface FeedOptions {
  fetchConditions(signal: AbortSignal): Promise<ConditionsResponse>;
  clock?: () => number;
  visibility?: Pick<Document, 'visibilityState' | 'addEventListener' | 'removeEventListener'>;
  schedule?: typeof setInterval;
  unschedule?: typeof clearInterval;
}

/** Owns one page's requests and timers; aggregation stays entirely in Django. */
export function createConditionsFeed(options: FeedOptions) {
  const clock = options.clock ?? Date.now;
  const schedule = options.schedule ?? setInterval;
  const unschedule = options.unschedule ?? clearInterval;
  const data = shallowRef<ConditionsResponse | null>(null);
  const loading = ref(true);
  const refreshing = ref(false);
  const error = ref(false);
  const now = ref(clock());
  let active = false;
  let request: AbortController | null = null;
  let lastAttempt: number | null = null;
  let refreshTimer: ReturnType<typeof setInterval> | undefined;
  let ageTimer: ReturnType<typeof setInterval> | undefined;
  let leaseTimer: ReturnType<typeof setInterval> | undefined;
  let leaseRetries = 0;

  function clearLeaseTimer() {
    if (leaseTimer !== undefined) unschedule(leaseTimer);
    leaseTimer = undefined;
  }

  async function requestConditions(isLeaseRetry: boolean) {
    if (!active || request) return;
    if (!isLeaseRetry) {
      leaseRetries = 0;
      clearLeaseTimer();
    }
    const controller = new AbortController();
    request = controller;
    lastAttempt = clock();
    refreshing.value = true;
    try {
      const result = await options.fetchConditions(controller.signal);
      if (!active || controller.signal.aborted) return;
      if (!result?.weather?.current || !Array.isArray(result.weather.sources) || !result.weather.comparison
          || !Array.isArray(result.forecast?.hourly) || !result.meta) {
        throw new Error('Invalid conditions response');
      }
      data.value = result;
      error.value = false;
      const providerRefreshing = result.weather.current.refreshing
        || result.weather.sources.some((source) => source.refreshing) || result.forecast.refreshing;
      // Another request owns the cache lease. Briefly check for its completed data,
      // then leave persistent provider failures to the regular five-minute cycle.
      if (providerRefreshing && leaseRetries < MAX_LEASE_RETRIES) {
        leaseRetries += 1;
        leaseTimer = schedule(() => {
          clearLeaseTimer();
          void requestConditions(true);
        }, LEASE_RETRY_MS);
      }
    } catch {
      if (active && !controller.signal.aborted) error.value = true;
    } finally {
      if (request === controller) {
        request = null;
        if (active) {
          loading.value = false;
          refreshing.value = false;
          now.value = clock();
        }
      }
    }
  }

  function refresh() {
    return requestConditions(false);
  }

  function refreshWhenDue() {
    now.value = clock();
    if (options.visibility?.visibilityState === 'hidden') return;
    if (lastAttempt === null || now.value - lastAttempt >= REFRESH_INTERVAL_MS) void refresh();
  }

  function start() {
    if (active) return;
    active = true;
    void refresh();
    refreshTimer = schedule(() => {
      if (options.visibility?.visibilityState !== 'hidden') void refresh();
    }, REFRESH_INTERVAL_MS);
    ageTimer = schedule(() => { now.value = clock(); }, AGE_INTERVAL_MS);
    options.visibility?.addEventListener('visibilitychange', refreshWhenDue);
  }

  function stop() {
    active = false;
    if (refreshTimer !== undefined) unschedule(refreshTimer);
    if (ageTimer !== undefined) unschedule(ageTimer);
    clearLeaseTimer();
    options.visibility?.removeEventListener('visibilitychange', refreshWhenDue);
    request?.abort();
    request = null;
  }

  return { data, loading, refreshing, error, now, start, stop, refresh };
}
