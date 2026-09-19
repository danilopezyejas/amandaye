<template>
  <div class="conditions-page min-h-screen bg-gradient-to-b from-blue-950 via-blue-900 to-blue-950 text-white">
    <header class="border-b border-white/10">
      <nav aria-label="Navegación principal" class="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-4 sm:px-6">
        <RouterLink to="/" class="flex min-w-0 items-center gap-3 rounded-lg focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-orange-400" aria-label="Club Amandayé Ipeguá, inicio">
          <img src="/logo.svg" alt="" class="h-11 w-11 shrink-0" />
          <span class="text-sm font-extrabold tracking-wide text-orange-400 sm:text-base">AMANDAYÉ IPEGUÁ</span>
        </RouterLink>
        <RouterLink to="/" class="btn-secondary inline-flex min-h-11 items-center text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-orange-400">Inicio</RouterLink>
      </nav>
    </header>

    <main class="mx-auto max-w-5xl px-4 py-7 sm:px-6 sm:py-10">
      <div class="mb-7">
        <p class="mb-2 text-sm font-semibold tracking-wide text-blue-200">Paysandú, Uruguay</p>
        <h1 class="text-3xl font-extrabold tracking-tight sm:text-4xl">Condiciones del río</h1>
        <p class="mt-3 text-base text-blue-100">¿Cómo está el río ahora?</p>
      </div>
      <ConditionsDashboard :data="data" :loading="loading" :refreshing="refreshing" :error="error" :now="now" @refresh="refresh" />
    </main>
    <footer class="mx-auto max-w-5xl px-4 pb-8 text-sm text-blue-200 sm:px-6">
      Club Amandayé Ipeguá · Costa de Paysandú
    </footer>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue';
import { publicApi } from '../api/axios';
import ConditionsDashboard from '../components/ConditionsDashboard.vue';
import { createConditionsFeed } from '../conditions/feed';
import type { ConditionsResponse } from '../conditions/types';

const { data, loading, refreshing, error, now, refresh, start, stop } = createConditionsFeed({
  fetchConditions: async (signal) => (await publicApi.get<ConditionsResponse>('conditions/', { signal })).data,
  visibility: typeof document === 'undefined' ? undefined : document,
});
const previousTitle = typeof document === 'undefined' ? '' : document.title;
onMounted(() => {
  document.title = 'Condiciones del río · Amandayé Ipeguá';
  start();
});
onUnmounted(() => {
  stop();
  document.title = previousTitle;
});
</script>

<style scoped>
.conditions-page { min-height: 100dvh; padding-bottom: env(safe-area-inset-bottom); }
</style>
