<script setup lang="ts">
import { computed } from 'vue'
import { useDocmateSession } from '../../composables/useDocmateSession'
import { docmateDownloadUrl } from '../../services/chitungApi'

const {
  state,
  hasWork,
  isDone,
  pendingCount,
  selectedCount,
  toggleSelect,
  selectAll,
  clearSelection,
  acceptSelected,
  rejectSelected,
  retryAll,
  startNewInstruction,
} = useDocmateSession()

const downloadUrl = computed(() =>
  state.outputResultPath ? docmateDownloadUrl(state.outputResultPath) : '',
)

function riskClass(level: string) {
  if (level === 'high' || level === 'critical') return 'risk-high'
  if (level === 'medium') return 'risk-medium'
  return 'risk-low'
}

function riskLabel(level: string) {
  if (level === 'high' || level === 'critical') return '高风险'
  if (level === 'medium') return '中风险'
  return '低风险'
}
</script>

<template>
  <div class="diff-review">
    <!-- 写入中 -->
    <div v-if="state.step === 'committing'" class="review-status">
      <span class="spinner"></span><span>正在写入文档...</span>
    </div>

    <!-- 全部处理完：汇总 + 下载 -->
    <div v-else-if="isDone" class="review-done">
      <template v-if="downloadUrl">
        <p class="review-done__lead">✅ 已完成 {{ state.completedCount }} 处更改</p>
        <a class="download-btn" :href="downloadUrl" download>⬇️ 下载修改后的文档</a>
        <button class="ghost-btn" @click="startNewInstruction">继续修改本文档</button>
      </template>
      <template v-else>
        <p class="review-done__lead">本轮未采纳任何修改，文档保持不变。</p>
        <button class="ghost-btn" @click="startNewInstruction">重新下达指令</button>
      </template>
    </div>

    <!-- 工作清单 -->
    <div v-else-if="hasWork" class="worklist">
      <div class="worklist__header">
        <h3>待处理修改（{{ pendingCount }} 项）</h3>
        <div class="worklist__select">
          <button class="mini-btn" :disabled="state.step === 'generating'" @click="selectAll">全选</button>
          <button class="mini-btn" :disabled="state.step === 'generating'" @click="clearSelection">全不选</button>
        </div>
      </div>

      <div class="worklist__items">
        <label
          v-for="item in state.workItems"
          :key="item.changeId"
          class="diff-item"
          :class="{ 'diff-item--selected': item.selected }"
        >
          <input
            type="checkbox"
            class="diff-item__check"
            :checked="item.selected"
            :disabled="state.step === 'generating'"
            @change="toggleSelect(item.changeId)"
          />
          <div class="diff-item__body">
            <div class="diff-item__head">
              <span class="diff-item__title">{{ item.card.title }}</span>
              <span class="diff-item__badge" :class="riskClass(item.card.risk_level)">
                {{ riskLabel(item.card.risk_level) }}
              </span>
            </div>
            <div class="diff-line diff-line--old">{{ item.card.before }}</div>
            <div class="diff-line diff-line--new">{{ item.card.after }}</div>
          </div>
        </label>
      </div>

      <div class="worklist__actions">
        <button
          class="act-btn act-btn--accept"
          :disabled="selectedCount === 0 || state.step === 'generating'"
          @click="acceptSelected"
        >
          采纳选中
        </button>
        <button
          class="act-btn act-btn--reject"
          :disabled="selectedCount === 0 || state.step === 'generating'"
          @click="rejectSelected"
        >
          不采纳
        </button>
        <button
          class="act-btn act-btn--retry"
          :disabled="pendingCount === 0 || state.step === 'generating'"
          @click="retryAll"
        >
          <span v-if="state.step === 'generating'" class="spinner"></span>
          <span>{{ state.step === 'generating' ? '重试中...' : '全部重试' }}</span>
        </button>
      </div>

      <p v-if="state.error && state.step === 'reviewing'" class="worklist-error">⚠️ {{ state.error }}</p>
    </div>
  </div>
</template>

<style scoped>
.diff-review {
  color: #c9d1d9;
}

.review-status {
  align-items: center;
  display: flex;
  font-size: 13px;
  gap: 8px;
  padding: 8px 0;
}

.review-done {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.review-done__lead {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: #86efac;
}

.download-btn {
  background: linear-gradient(135deg, #6c8cff, #5070e0);
  border-radius: 8px;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  padding: 9px 14px;
  text-align: center;
  text-decoration: none;
}

.download-btn:hover {
  background: linear-gradient(135deg, #7d9aff, #6080f0);
}

.ghost-btn {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 8px;
  color: #8b949e;
  font-size: 12px;
  padding: 7px 12px;
}

.ghost-btn:hover {
  color: #c9d1d9;
  border-color: rgba(255, 255, 255, 0.3);
}

.worklist {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
}

.worklist__header {
  align-items: center;
  display: flex;
  justify-content: space-between;
}

.worklist__header h3 {
  color: #c9d1d9;
  font-size: 12px;
  margin: 0;
}

.worklist__select {
  display: flex;
  gap: 4px;
}

.mini-btn {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  color: #c9d1d9;
  font-size: 11px;
  padding: 3px 8px;
}

.mini-btn:hover {
  background: rgba(255, 255, 255, 0.12);
}

.mini-btn:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

.worklist__items {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 300px;
  overflow-y: auto;
}

.diff-item {
  align-items: flex-start;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  gap: 8px;
  padding: 9px 10px;
}

.diff-item:hover {
  background: rgba(255, 255, 255, 0.06);
}

.diff-item--selected {
  background: rgba(108, 140, 255, 0.1);
  border-color: rgba(108, 140, 255, 0.45);
}

.diff-item__check {
  margin-top: 2px;
  flex-shrink: 0;
  width: 15px;
  height: 15px;
  accent-color: #6c8cff;
  cursor: pointer;
}

.diff-item__body {
  flex: 1;
  min-width: 0;
}

.diff-item__head {
  align-items: center;
  display: flex;
  gap: 6px;
  margin-bottom: 6px;
}

.diff-item__title {
  color: #e8e8ec;
  flex: 1;
  font-size: 12px;
  font-weight: 600;
}

.diff-item__badge {
  border-radius: 4px;
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 500;
  padding: 2px 6px;
}

.risk-low {
  background: rgba(34, 197, 94, 0.15);
  color: #4ade80;
}

.risk-medium {
  background: rgba(251, 191, 36, 0.15);
  color: #fbbf24;
}

.risk-high {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
}

.diff-line {
  border-radius: 3px;
  font-size: 11px;
  line-height: 1.45;
  overflow: hidden;
  padding: 2px 6px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.diff-line--old {
  background: rgba(239, 68, 68, 0.1);
  color: #f87171;
  text-decoration: line-through;
}

.diff-line--new {
  background: rgba(34, 197, 94, 0.1);
  color: #6ee7a8;
  margin-top: 2px;
}

.worklist__actions {
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  gap: 6px;
  padding-top: 8px;
}

.act-btn {
  align-items: center;
  border: 0;
  border-radius: 8px;
  display: inline-flex;
  flex: 1;
  font-size: 12px;
  gap: 5px;
  justify-content: center;
  padding: 8px 6px;
}

.act-btn:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

.act-btn--accept {
  background: linear-gradient(135deg, #6c8cff, #5070e0);
  color: #fff;
}

.act-btn--reject {
  background: rgba(239, 68, 68, 0.16);
  color: #f87171;
}

.act-btn--retry {
  background: rgba(255, 255, 255, 0.08);
  color: #c9d1d9;
}

.worklist-error {
  color: #fca5a5;
  font-size: 11px;
  margin: 4px 0 0;
}

.spinner {
  animation: spin 0.6s linear infinite;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  border-top-color: #fff;
  display: inline-block;
  height: 13px;
  width: 13px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
