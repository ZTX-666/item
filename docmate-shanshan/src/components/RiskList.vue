<script setup lang="ts">
import type { RiskItem } from '@/types'

defineProps<{
  risks: RiskItem[]
}>()

const emit = defineEmits<{
  locate: [excerpt: string]
  accept: [id: string]
  ignore: [id: string]
}>()

function levelIcon(level: string) {
  if (level === 'high') return '🔴'
  if (level === 'medium') return '🟡'
  return '🟢'
}

function levelLabel(level: string) {
  if (level === 'high') return '高风险'
  if (level === 'medium') return '中风险'
  return '建议优化'
}
</script>

<template>
  <div class="risk-list">
    <div
      v-for="risk in risks"
      :key="risk.id"
      class="risk-card"
      :class="{ resolved: risk.resolved, [`level-${risk.level}`]: true }"
      @click="emit('locate', risk.excerpt)"
    >
      <div class="risk-header">
        <span class="risk-icon">{{ levelIcon(risk.level) }}</span>
        <span class="risk-level">{{ levelLabel(risk.level) }}</span>
      </div>
      <p class="risk-excerpt">「{{ risk.excerpt }}」</p>
      <p class="risk-reason">{{ risk.reason }}</p>
      <p class="risk-suggestion">建议：{{ risk.suggestion }}</p>
      <div v-if="!risk.resolved" class="risk-actions" @click.stop>
        <button class="risk-btn accept" @click="emit('accept', risk.id)">采纳建议</button>
        <button class="risk-btn" @click="emit('locate', risk.excerpt)">定位</button>
        <button class="risk-btn" @click="emit('ignore', risk.id)">忽略</button>
      </div>
      <div v-else class="risk-done">✓ 已处理</div>
    </div>
  </div>
</template>

<style scoped>
.risk-list {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.risk-card {
  padding: 10px 12px;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--bg-base);
  cursor: pointer;
  transition: border-color 0.15s;
}

.risk-card:hover {
  border-color: var(--border-focus);
}

.risk-card.resolved {
  opacity: 0.55;
}

.risk-card.level-high { border-left: 3px solid var(--red); }
.risk-card.level-medium { border-left: 3px solid #dcdcaa; }
.risk-card.level-low { border-left: 3px solid var(--green); }

.risk-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.risk-level {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
}

.risk-excerpt {
  font-size: 12px;
  color: var(--text-bright);
  margin-bottom: 4px;
}

.risk-reason {
  font-size: 12px;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.risk-suggestion {
  font-size: 11px;
  color: var(--text-muted);
}

.risk-actions {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}

.risk-btn {
  padding: 4px 10px;
  font-size: 11px;
  border-radius: 4px;
  background: var(--bg-hover);
  color: var(--text-secondary);
  border: 1px solid var(--border-light);
  transition: all 0.15s;
}

.risk-btn:hover {
  background: var(--bg-active);
  color: var(--text-primary);
}

.risk-btn.accept {
  background: var(--green-bg);
  color: var(--green);
  border-color: transparent;
}

.risk-done {
  font-size: 11px;
  color: var(--green);
  margin-top: 6px;
}
</style>
