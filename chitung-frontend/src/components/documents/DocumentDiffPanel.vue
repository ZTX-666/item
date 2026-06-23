<script setup lang="ts">
import { computed, ref } from 'vue'
import type { DocumentRevisionPreview } from '../../types/domain'

/**
 * DocumentDiffPanel — AI 文档改写预览面板
 * P1-2: 统一diff颜色 + 空状态
 * P2-2: 并排/红线/变更列表三模式（Draftable模式）
 */

const props = defineProps<{
  revision: DocumentRevisionPreview
  isLoading?: boolean
}>()

const emit = defineEmits<{
  accept: []
  reject: []
  regenerate: []
}>()

/** 视图模式：并排 / 红线 / 变更列表 */
const viewMode = ref<'side-by-side' | 'redline' | 'list'>('redline')

/** 变更行（仅 added + removed） */
const changeLines = computed(() => props.revision.lines.filter((line) => line.type !== 'context'))

/** 并排视图数据：将连续的 removed+added 配对 */
const sideBySidePairs = computed(() => {
  const lines = props.revision.lines
  const pairs: Array<{ left: typeof lines[number] | null; right: typeof lines[number] | null }> = []
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    if (line.type === 'context') {
      pairs.push({ left: line, right: line })
      i++
    } else if (line.type === 'removed') {
      const next = lines[i + 1]
      if (next && next.type === 'added') {
        pairs.push({ left: line, right: next })
        i += 2
      } else {
        pairs.push({ left: line, right: null })
        i++
      }
    } else {
      // added without preceding removed
      pairs.push({ left: null, right: line })
      i++
    }
  }
  return pairs
})

const statusLabel = computed(() => {
  if (props.revision.status === 'accepted') return '已采纳'
  if (props.revision.status === 'rejected') return '已拒绝'
  return '待人工确认'
})
</script>

<template>
  <section class="panel document-diff-panel">
    <div class="panel__header">
      <div>
        <h2>AI 文档改写预览</h2>
        <p>{{ revision.title }} &middot; {{ revision.source }}</p>
      </div>
      <div class="diff-stat-group" aria-label="文档修改统计">
        <span class="diff-stat diff-stat--add">+{{ revision.additions }}</span>
        <span class="diff-stat diff-stat--remove">-{{ revision.deletions }}</span>
      </div>
    </div>

    <div class="diff-instruction">
      <span>指令</span>
      <strong>{{ revision.instruction }}</strong>
    </div>

    <!-- 视图模式切换 (P2-2) -->
    <div v-if="revision.lines.length" class="view-mode-tabs">
      <button
        class="view-mode-tab"
        :class="{ 'view-mode-tab--active': viewMode === 'side-by-side' }"
        @click="viewMode = 'side-by-side'"
      >
        并排视图
      </button>
      <button
        class="view-mode-tab"
        :class="{ 'view-mode-tab--active': viewMode === 'redline' }"
        @click="viewMode = 'redline'"
      >
        红线视图
      </button>
      <button
        class="view-mode-tab"
        :class="{ 'view-mode-tab--active': viewMode === 'list' }"
        @click="viewMode = 'list'"
      >
        变更列表
      </button>
    </div>

    <!-- 空状态 (P1-2) -->
    <div v-if="!revision.lines.length && !isLoading" class="diff-empty-state">
      <div class="diff-empty-state__icon">&#128196;</div>
      <p class="diff-empty-state__title">暂无改写内容</p>
      <p class="diff-empty-state__hint">输入修改指令并点击「重新生成」，AI 将在此展示改写预览。</p>
    </div>

    <!-- 加载骨架 (P1-6) -->
    <div v-else-if="isLoading" class="diff-skeleton">
      <div v-for="i in 4" :key="i" class="diff-skeleton__row">
        <div class="diff-skeleton__bar" :style="{ width: `${80 - i * 8}%` }"></div>
      </div>
    </div>

    <!-- 红线视图（默认） -->
    <div v-else-if="viewMode === 'redline'" class="document-diff" aria-label="AI 文档改写差异">
      <p
        v-for="line in revision.lines"
        :key="line.id"
        class="document-diff__line"
        :class="`document-diff__line--${line.type}`"
      >
        <span class="document-diff__marker">
          {{ line.type === 'added' ? '+' : line.type === 'removed' ? '-' : ' ' }}
        </span>
        <span>{{ line.text }}</span>
      </p>
    </div>

    <!-- 并排视图 -->
    <div v-else-if="viewMode === 'side-by-side'" class="diff-side-by-side">
      <div class="diff-side-by-side__col">
        <div class="diff-side-by-side__head">原文</div>
        <div class="diff-side-by-side__body">
          <p
            v-for="(pair, idx) in sideBySidePairs"
            :key="`l-${idx}`"
            class="sb-line"
            :class="pair.left ? `sb-line--${pair.left.type}` : 'sb-line--empty'"
          >
            {{ pair.left?.text || '' }}
          </p>
        </div>
      </div>
      <div class="diff-side-by-side__col">
        <div class="diff-side-by-side__head">修改后</div>
        <div class="diff-side-by-side__body">
          <p
            v-for="(pair, idx) in sideBySidePairs"
            :key="`r-${idx}`"
            class="sb-line"
            :class="pair.right ? `sb-line--${pair.right.type}` : 'sb-line--empty'"
          >
            {{ pair.right?.text || '' }}
          </p>
        </div>
      </div>
    </div>

    <!-- 变更列表 -->
    <div v-else class="diff-change-list">
      <div v-for="(line, idx) in changeLines" :key="line.id" class="change-list__item">
        <span class="change-list__index">#{{ idx + 1 }}</span>
        <span class="change-list__type" :class="`change-list__type--${line.type}`">
          {{ line.type === 'added' ? '新增' : '删除' }}
        </span>
        <span class="change-list__text">{{ line.text }}</span>
      </div>
      <p v-if="!changeLines.length" class="change-list__empty">没有检测到变更。</p>
    </div>

    <!-- 操作栏 -->
    <div v-if="revision.lines.length" class="diff-actions-bar">
      <span class="diff-status" :class="`diff-status--${revision.status}`">
        {{ statusLabel }}
      </span>
      <button class="mini-button" type="button" @click="emit('regenerate')">重新生成</button>
      <button class="mini-button" type="button" @click="emit('reject')">拒绝</button>
      <button class="primary-soft-button" type="button" @click="emit('accept')">采纳修改</button>
    </div>
  </section>
</template>

<style scoped>
.document-diff-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel__header {
  align-items: flex-start;
  display: flex;
  justify-content: space-between;
}

.panel__header h2 {
  font-size: 16px;
  margin: 0;
}

.panel__header p {
  color: var(--text-secondary, #5b626c);
  font-size: 12px;
  margin: 4px 0 0;
}

.diff-stat-group {
  display: flex;
  gap: 6px;
}

.diff-stat {
  border-radius: var(--radius-sm, 4px);
  font-size: 12px;
  font-weight: 700;
  padding: 2px 8px;
}

.diff-stat--add {
  background: var(--diff-add-bg, #E8F5E9);
  color: var(--diff-add-text, #2E7D32);
}

.diff-stat--remove {
  background: var(--diff-del-bg, #FFEBEE);
  color: var(--diff-del-text, #C62828);
}

.diff-instruction {
  align-items: center;
  background: var(--bg-subtle, #f5f7fa);
  border-radius: var(--radius-md, 8px);
  display: flex;
  font-size: 12px;
  gap: 8px;
  padding: 8px 12px;
}

.diff-instruction span {
  color: var(--text-secondary, #5b626c);
  flex-shrink: 0;
}

.diff-instruction strong {
  color: var(--text-primary, #1a1d23);
  font-weight: 600;
}

/* 视图模式切换 */
.view-mode-tabs {
  display: flex;
  gap: 2px;
}

.view-mode-tab {
  background: transparent;
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-sm, 4px);
  color: var(--text-secondary, #5b626c);
  cursor: pointer;
  font-size: 12px;
  padding: 5px 12px;
}

.view-mode-tab--active {
  background: var(--brand-cyan, #0f9ed5);
  border-color: var(--brand-cyan, #0f9ed5);
  color: var(--text-white, #fff);
}

/* 空状态 */
.diff-empty-state {
  align-items: center;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 40px 20px;
  text-align: center;
}

.diff-empty-state__icon {
  font-size: 36px;
  opacity: 0.5;
}

.diff-empty-state__title {
  color: var(--text-primary, #1a1d23);
  font-size: 14px;
  font-weight: 600;
  margin: 0;
}

.diff-empty-state__hint {
  color: var(--text-secondary, #5b626c);
  font-size: 12px;
  margin: 0;
  max-width: 320px;
}

/* 骨架屏 */
.diff-skeleton {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 0;
}

.diff-skeleton__row {
  display: flex;
}

.diff-skeleton__bar {
  animation: skeleton-pulse 1.4s ease-in-out infinite;
  background: linear-gradient(90deg, var(--bg-subtle, #f0f2f5) 25%, var(--bg-active, #e4e8ee) 50%, var(--bg-subtle, #f0f2f5) 75%);
  background-size: 200% 100%;
  border-radius: var(--radius-sm, 4px);
  height: 14px;
}

@keyframes skeleton-pulse {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* 红线视图 */
.document-diff {
  background: var(--bg-white, #fff);
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-md, 8px);
  max-height: 400px;
  overflow-y: auto;
  padding: 12px;
}

.document-diff__line {
  display: flex;
  font-family: var(--font-mono, monospace);
  font-size: 12px;
  gap: 8px;
  line-height: 1.6;
  padding: 2px 6px;
}

.document-diff__marker {
  color: var(--text-muted, #9ca3af);
  flex-shrink: 0;
  width: 14px;
}

.document-diff__line--added {
  background: var(--diff-add-bg, #E8F5E9);
  color: var(--diff-add-text, #2E7D32);
}

.document-diff__line--removed {
  background: var(--diff-del-bg, #FFEBEE);
  color: var(--diff-del-text, #C62828);
  text-decoration: line-through;
}

/* 并排视图 */
.diff-side-by-side {
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-md, 8px);
  display: grid;
  grid-template-columns: 1fr 1fr;
  max-height: 400px;
  overflow: hidden;
}

.diff-side-by-side__col {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.diff-side-by-side__col + .diff-side-by-side__col {
  border-left: 1px solid var(--border-light, #e8eaef);
}

.diff-side-by-side__head {
  background: var(--bg-subtle, #f5f7fa);
  border-bottom: 1px solid var(--border-light, #e8eaef);
  color: var(--text-secondary, #5b626c);
  font-size: 11px;
  font-weight: 600;
  padding: 6px 10px;
  text-transform: uppercase;
}

.diff-side-by-side__body {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.sb-line {
  font-family: var(--font-mono, monospace);
  font-size: 12px;
  line-height: 1.6;
  margin: 0;
  padding: 1px 4px;
}

.sb-line--added {
  background: var(--diff-add-bg, #E8F5E9);
  color: var(--diff-add-text, #2E7D32);
}

.sb-line--removed {
  background: var(--diff-del-bg, #FFEBEE);
  color: var(--diff-del-text, #C62828);
  text-decoration: line-through;
}

.sb-line--empty {
  background: var(--bg-subtle, #f5f7fa);
  color: var(--text-muted, #9ca3af);
  min-height: 1.6em;
}

/* 变更列表 */
.diff-change-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 400px;
  overflow-y: auto;
}

.change-list__item {
  align-items: flex-start;
  display: flex;
  font-size: 12px;
  gap: 8px;
  padding: 6px 8px;
}

.change-list__index {
  color: var(--text-muted, #9ca3af);
  flex-shrink: 0;
  font-weight: 600;
  width: 28px;
}

.change-list__type {
  border-radius: var(--radius-sm, 4px);
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
}

.change-list__type--added {
  background: var(--diff-add-bg, #E8F5E9);
  color: var(--diff-add-text, #2E7D32);
}

.change-list__type--removed {
  background: var(--diff-del-bg, #FFEBEE);
  color: var(--diff-del-text, #C62828);
}

.change-list__text {
  flex: 1;
  line-height: 1.5;
  word-break: break-word;
}

.change-list__empty {
  color: var(--text-muted, #9ca3af);
  font-size: 12px;
  padding: 20px;
  text-align: center;
}

/* 操作栏 */
.diff-actions-bar {
  align-items: center;
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.diff-status {
  border-radius: var(--radius-sm, 4px);
  font-size: 11px;
  font-weight: 600;
  margin-right: auto;
  padding: 3px 8px;
}

.diff-status--draft {
  background: rgba(15, 158, 213, 0.1);
  color: var(--brand-cyan, #0f9ed5);
}

.diff-status--accepted {
  background: var(--diff-add-bg, #E8F5E9);
  color: var(--diff-add-text, #2E7D32);
}

.diff-status--rejected {
  background: var(--diff-del-bg, #FFEBEE);
  color: var(--diff-del-text, #C62828);
}

.mini-button {
  background: var(--bg-white, #fff);
  border: 1px solid var(--border-normal, #d0d5dd);
  border-radius: var(--radius-sm, 4px);
  color: var(--text-secondary, #5b626c);
  cursor: pointer;
  font-size: 12px;
  padding: 6px 12px;
}

.mini-button:hover {
  border-color: var(--brand-cyan, #0f9ed5);
  color: var(--brand-cyan, #0f9ed5);
}

.primary-soft-button {
  background: var(--brand-cyan, #0f9ed5);
  border: none;
  border-radius: var(--radius-sm, 4px);
  color: var(--text-white, #fff);
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  padding: 6px 14px;
}

.primary-soft-button:hover {
  opacity: 0.9;
}
</style>
