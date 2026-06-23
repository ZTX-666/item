<script setup lang="ts">
import type { RiskLevel } from '../../types/domain'

/**
 * RiskBadge — 风险等级徽标
 * 用形状区分风险等级，不依赖颜色alone：
 * - 高风险：红色填充圆形 + "高"
 * - 中风险：橙色三角 + "中"
 * - 低风险：绿色圆点 + "低"
 */
const props = defineProps<{
  level: RiskLevel | string
}>()

function normalizeLevel(level: string): 'high' | 'medium' | 'low' {
  if (level === 'high' || level === 'critical') return 'high'
  if (level === 'medium') return 'medium'
  return 'low'
}

function levelLabel(level: string): string {
  const normalized = normalizeLevel(level)
  if (normalized === 'high') return '高风险'
  if (normalized === 'medium') return '中风险'
  return '低风险'
}
</script>

<template>
  <span class="risk-badge" :class="`risk-badge--${normalizeLevel(props.level)}`">
    <span class="risk-badge__shape">
      <!-- 高风险：填充圆形 -->
      <svg v-if="normalizeLevel(props.level) === 'high'" viewBox="0 0 16 16" class="risk-badge__icon" aria-hidden="true">
        <circle cx="8" cy="8" r="6" fill="currentColor" />
      </svg>
      <!-- 中风险：三角 -->
      <svg v-else-if="normalizeLevel(props.level) === 'medium'" viewBox="0 0 16 16" class="risk-badge__icon" aria-hidden="true">
        <path d="M8 2 L14 13 L2 13 Z" fill="currentColor" />
      </svg>
      <!-- 低风险：圆点 -->
      <svg v-else viewBox="0 0 16 16" class="risk-badge__icon" aria-hidden="true">
        <circle cx="8" cy="8" r="4" fill="currentColor" />
      </svg>
    </span>
    <span class="risk-badge__label">{{ levelLabel(props.level) }}</span>
  </span>
</template>

<style scoped>
.risk-badge {
  align-items: center;
  border-radius: var(--radius-sm, 4px);
  display: inline-flex;
  font-size: 10px;
  font-weight: 600;
  gap: 3px;
  padding: 2px 6px;
  white-space: nowrap;
}

.risk-badge__icon {
  height: 12px;
  width: 12px;
}

.risk-badge__label {
  line-height: 1;
}

.risk-badge--high {
  background: rgba(229, 57, 53, 0.12);
  color: var(--risk-high, #E53935);
}

.risk-badge--medium {
  background: rgba(251, 140, 0, 0.12);
  color: var(--risk-medium, #FB8C00);
}

.risk-badge--low {
  background: rgba(67, 160, 71, 0.12);
  color: var(--risk-low, #43A047);
}
</style>
