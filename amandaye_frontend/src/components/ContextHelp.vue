<script setup lang="ts">
defineProps<{ title: string; steps: readonly string[] }>();
</script>

<template>
  <details class="context-help">
    <summary>Ayuda: {{ title }}</summary>
    <ol><li v-for="step in steps" :key="step">{{ step }}</li></ol>
  </details>
</template>

<style scoped>
.context-help { margin: 1rem 0; padding: .75rem 1rem; border: 1px solid #7394c7; border-radius: .75rem; background: #102b51; color: #fff; text-align: left; font-size: .95rem; line-height: 1.6; }
summary { cursor: pointer; font-weight: 600; min-height: 28px; }
summary:focus-visible { outline: 3px solid #fdba74; outline-offset: 4px; }
ol { padding-left: 1.4rem; margin-top: .75rem; }
li { margin-bottom: .5rem; }
</style>
