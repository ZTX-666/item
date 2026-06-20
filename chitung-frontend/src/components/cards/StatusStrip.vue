<script setup lang="ts">
import type { StatusMetric } from '../../types/domain'

defineProps<{
  metrics: StatusMetric[]
}>()
</script>

<template>
  <section class="status-strip" aria-label="安全状态指标">
    <article v-for="metric in metrics" :key="metric.id" class="status-card" :class="`status-card--${metric.tone}`">
      <div class="status-card__label">{{ metric.label }}</div>
      <div class="status-card__value">{{ metric.value }}</div>
      <div class="status-card__helper">{{ metric.helper }}</div>
    </article>
  </section>
</template>
