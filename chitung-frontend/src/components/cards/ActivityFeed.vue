<script setup lang="ts">
import type { ActivityItem } from '../../types/domain'

defineProps<{
  items: ActivityItem[]
}>()

const emit = defineEmits<{
  'open-confirmations': []
}>()
</script>

<template>
  <section class="panel">
    <div class="panel__header">
      <div>
        <h2>近期活动</h2>
        <p>工具调用、确认动作和台账变化</p>
      </div>
    </div>
    <div class="activity-feed">
      <article v-for="item in items" :key="item.id" class="activity-item">
        <time>{{ item.time }}</time>
        <div>
          <strong>{{ item.title }}</strong>
          <p>{{ item.description }}</p>
        </div>
        <button
          v-if="item.actionLabel"
          class="mini-button"
          @click="emit('open-confirmations')"
        >
          {{ item.actionLabel }}
        </button>
      </article>
    </div>
  </section>
</template>
