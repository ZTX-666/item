<script setup lang="ts">
import type { AuditEntry } from '../../types/domain'

/**
 * AuditTrail — 审计日志操作时间线
 * 记录每次操作：时间 + 操作人 + 动作（接受/拒绝/修改/重试）+ 对象
 * 时间线形式展示
 */

const props = defineProps<{
  entries: AuditEntry[]
  maxItems?: number
}>()

function actionIcon(action: AuditEntry['action']): string {
  const icons: Record<string, string> = {
    accept: '\u2705',
    reject: '\u274C',
    edit: '\u270F\uFE0F',
    retry: '\u{1F504}',
    generate: '\u2728',
    upload: '\u{1F4C4}',
    download: '\u{1F4E5}',
    batch_accept: '\u2705',
    batch_reject: '\u274C',
  }
  return icons[action] || '\u2022'
}

function actionLabel(action: AuditEntry['action']): string {
  const labels: Record<string, string> = {
    accept: '接受修改',
    reject: '拒绝修改',
    edit: '编辑修改',
    retry: '重试修改',
    generate: '生成方案',
    upload: '上传文档',
    download: '下载文档',
    batch_accept: '批量接受',
    batch_reject: '批量拒绝',
  }
  return labels[action] || action
}

const displayEntries = props.maxItems
  ? props.entries.slice(-props.maxItems).reverse()
  : [...props.entries].reverse()
</script>

<template>
  <div class="audit-trail">
    <div class="audit-trail__header">
      <h3>操作记录</h3>
      <span class="audit-trail__count">{{ props.entries.length }} 条</span>
    </div>

    <div v-if="!displayEntries.length" class="audit-trail__empty">
      暂无操作记录
    </div>

    <ol v-else class="audit-trail__list">
      <li v-for="entry in displayEntries" :key="entry.id" class="audit-entry">
        <span class="audit-entry__icon">{{ actionIcon(entry.action) }}</span>
        <div class="audit-entry__body">
          <div class="audit-entry__head">
            <span class="audit-entry__action">{{ actionLabel(entry.action) }}</span>
            <span class="audit-entry__target">{{ entry.target }}</span>
          </div>
          <div class="audit-entry__meta">
            <span class="audit-entry__time">{{ entry.timestamp }}</span>
            <span class="audit-entry__operator">{{ entry.operator }}</span>
          </div>
          <p v-if="entry.detail" class="audit-entry__detail">{{ entry.detail }}</p>
        </div>
      </li>
    </ol>
  </div>
</template>

<style scoped>
.audit-trail {
  background: var(--bg-white, #fff);
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-lg, 12px);
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
}

.audit-trail__header {
  align-items: center;
  display: flex;
  justify-content: space-between;
}

.audit-trail__header h3 {
  color: var(--text-secondary, #5b626c);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.4px;
  margin: 0;
  text-transform: uppercase;
}

.audit-trail__count {
  color: var(--text-muted, #9ca3af);
  font-size: 11px;
}

.audit-trail__empty {
  color: var(--text-muted, #9ca3af);
  font-size: 12px;
  padding: 12px 0;
  text-align: center;
}

.audit-trail__list {
  display: flex;
  flex-direction: column;
  gap: 0;
  list-style: none;
  margin: 0;
  padding: 0;
}

.audit-entry {
  display: flex;
  gap: 10px;
  padding: 8px 0;
  position: relative;
}

.audit-entry:not(:last-child)::before {
  background: var(--border-light, #e8eaef);
  bottom: 0;
  content: '';
  left: 11px;
  position: absolute;
  top: 28px;
  width: 2px;
}

.audit-entry__icon {
  background: var(--bg-subtle, #f5f7fa);
  border-radius: 50%;
  flex-shrink: 0;
  font-size: 12px;
  height: 24px;
  line-height: 24px;
  text-align: center;
  width: 24px;
  z-index: 1;
}

.audit-entry__body {
  flex: 1;
  min-width: 0;
}

.audit-entry__head {
  align-items: center;
  display: flex;
  gap: 6px;
}

.audit-entry__action {
  color: var(--text-primary, #1a1d23);
  font-size: 12px;
  font-weight: 600;
}

.audit-entry__target {
  color: var(--text-secondary, #5b626c);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.audit-entry__meta {
  align-items: center;
  display: flex;
  gap: 8px;
  margin-top: 2px;
}

.audit-entry__time {
  color: var(--text-muted, #9ca3af);
  font-size: 11px;
}

.audit-entry__operator {
  color: var(--text-muted, #9ca3af);
  font-size: 11px;
}

.audit-entry__detail {
  color: var(--text-secondary, #5b626c);
  font-size: 11px;
  line-height: 1.5;
  margin: 4px 0 0;
}
</style>
