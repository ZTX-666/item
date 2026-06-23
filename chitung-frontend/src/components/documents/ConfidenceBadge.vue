<script setup lang="ts">
import { computed } from 'vue'

/**
 * ConfidenceBadge — AI 置信度徽标
 * - 高(90%+)：绿色 ✅
 * - 中(60-89%)：黄色 ⚠️
 * - 低(<60%)：灰色 ❓
 */
const props = defineProps<{
  confidence: number
}>()

const percentage = computed(() => Math.round(props.confidence * 100))

const tier = computed<'high' | 'medium' | 'low'>(() => {
  if (props.confidence >= 0.9) return 'high'
  if (props.confidence >= 0.6) return 'medium'
  return 'low'
})

const icon = computed(() => {
  if (tier.value === 'high') return '\u2705'
  if (tier.value === 'medium') return '\u26A0\uFE0F'
  return '\u2754'
})

</script>

<template>
  <span class="confidence-badge" :class="`confidence-badge--${tier}`" :title="`AI 置信度 ${percentage}%`">
    <span class="confidence-badge__icon">{{ icon }}</span>
    <span class="confidence-badge__text">{{ percentage }}%</span>
  </span>
</template>

<style scoped>
.confidence-badge {
  align-items: center;
  border-radius: var(--radius-sm, 4px);
  display: inline-flex;
  font-size: 10px;
  font-weight: 600;
  gap: 3px;
  padding: 2px 6px;
  white-space: nowrap;
}

.confidence-badge__icon {
  font-size: 11px;
  line-height: 1;
}

.confidence-badge--high {
  background: rgba(67, 160, 71, 0.12);
  color: var(--confidence-high, #43A047);
}

.confidence-badge--medium {
  background: rgba(251, 140, 0, 0.12);
  color: var(--confidence-medium, #FB8C00);
}

.confidence-badge--low {
  background: rgba(158, 158, 158, 0.12);
  color: var(--confidence-low, #9E9E9E);
}
</style>
