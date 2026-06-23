<script setup lang="ts">
import { computed, ref } from 'vue'
import { useDocmateSession } from '../../composables/useDocmateSession'
import { docmateDownloadUrl } from '../../services/chitungApi'
import RiskBadge from './RiskBadge.vue'
import ConfidenceBadge from './ConfidenceBadge.vue'

/**
 * DocmateDiffReview — 改稿审阅面板
 * P1-1: 消费置信度/风险/理由字段
 * P1-5: 统一色彩体系（用CSS变量，替换硬编码颜色）
 * P2-3: 批量操作按置信度/风险筛选
 * P2-6: 拒绝理由反馈
 */
const {
  state,
  hasWork,
  isDone,
  pendingCount,
  selectedCount,
  highRiskCount,
  toggleSelect,
  selectAll,
  clearSelection,
  selectLowRiskOnly,
  selectExceptHigh,
  acceptSelected,
  rejectSelected,
  acceptAllExceptHigh,
  acceptLowOnly,
  rejectWithReason,
  retryAll,
  startNewInstruction,
} = useDocmateSession()

const downloadUrl = computed(() => (state.outputResultPath ? docmateDownloadUrl(state.outputResultPath) : ''))

/** 拒绝理由弹窗状态 */
const rejectingItemId = ref<string | null>(null)
const rejectReason = ref('')
const customReason = ref('')
const rejectReasons = ['修改过度', '语义错误', '不符合规范', '其他'] as const

/** 置信度筛选 */
const confidenceFilter = ref<'all' | 'high' | 'medium' | 'low'>('all')

const filteredItems = computed(() => {
  if (confidenceFilter.value === 'all') return state.workItems
  return state.workItems.filter((item) => {
    const c = item.card.confidence
    if (confidenceFilter.value === 'high') return c >= 0.9
    if (confidenceFilter.value === 'medium') return c >= 0.6 && c < 0.9
    return c < 0.6
  })
})

function confirmReject() {
  if (!rejectingItemId.value) return
  const reason = rejectReason.value === '其他'
    ? customReason.value || '其他'
    : rejectReason.value || '未提供理由'
  rejectWithReason(rejectingItemId.value, reason)
  rejectingItemId.value = null
  rejectReason.value = ''
  customReason.value = ''
}

function cancelReject() {
  rejectingItemId.value = null
  rejectReason.value = ''
  customReason.value = ''
}

function getExplanation(item: typeof state.workItems[number]): string {
  return item.card.explanation || item.card.reason || item.change.explanation || item.change.reason || ''
}
</script>

<template>
  <div class="diff-review">
    <div v-if="state.step === 'committing'" class="review-status">
      <span class="spinner"></span>
      <span>正在写入文档...</span>
    </div>

    <div v-else-if="isDone" class="review-done">
      <template v-if="downloadUrl">
        <p class="review-done__lead">已完成 {{ state.completedCount }} 处更改</p>
        <a class="download-btn" :href="downloadUrl" download>下载修改后的文档</a>
        <button class="ghost-btn" @click="startNewInstruction">继续修改本文档</button>
      </template>
      <template v-else>
        <p class="review-done__lead">本轮未采纳任何修改，文档保持不变。</p>
        <button class="ghost-btn" @click="startNewInstruction">重新下达指令</button>
      </template>
    </div>

    <div v-else-if="hasWork" class="worklist">
      <!-- 批量操作区 (P2-3) -->
      <div class="worklist__batch">
        <div class="batch-stats">
          <span class="batch-stat">待处理 {{ pendingCount }} 项</span>
          <span class="batch-stat batch-stat--high">高风险 {{ highRiskCount }} 项</span>
          <span class="batch-stat">已选 {{ selectedCount }} 项</span>
        </div>
        <div class="batch-actions">
          <button class="batch-btn batch-btn--smart" :disabled="state.step === 'generating'" @click="acceptAllExceptHigh">
            全部接受（高风险除外）
          </button>
          <button class="batch-btn" :disabled="state.step === 'generating'" @click="acceptLowOnly">
            仅接受低风险
          </button>
          <button class="batch-btn batch-btn--review" :disabled="highRiskCount === 0 || state.step === 'generating'">
            高风险待人工复核（{{ highRiskCount }}）
          </button>
        </div>
      </div>

      <!-- 筛选区 -->
      <div class="worklist__filter">
        <div class="filter-tabs">
          <button
            v-for="opt in [
              { v: 'all', label: '全部' },
              { v: 'high', label: '高置信' },
              { v: 'medium', label: '中置信' },
              { v: 'low', label: '低置信' },
            ]"
            :key="opt.v"
            class="filter-tab"
            :class="{ 'filter-tab--active': confidenceFilter === opt.v }"
            @click="confidenceFilter = opt.v as typeof confidenceFilter"
          >
            {{ opt.label }}
          </button>
        </div>
        <div class="worklist__select">
          <button class="mini-btn" :disabled="state.step === 'generating'" @click="selectAll">全选</button>
          <button class="mini-btn" :disabled="state.step === 'generating'" @click="clearSelection">全不选</button>
          <button class="mini-btn" :disabled="state.step === 'generating'" @click="selectLowRiskOnly">仅选低风险</button>
          <button class="mini-btn" :disabled="state.step === 'generating'" @click="selectExceptHigh">选非高风险</button>
        </div>
      </div>

      <!-- 工作项列表 -->
      <div class="worklist__items">
        <div
          v-for="item in filteredItems"
          :key="item.changeId"
          class="diff-item"
          :class="{ 'diff-item--selected': item.selected, 'diff-item--high-risk': item.card.risk_level === 'high' || item.card.risk_level === 'critical' }"
        >
          <label class="diff-item__check" @click.stop>
            <input
              type="checkbox"
              :checked="item.selected"
              :disabled="state.step === 'generating'"
              @change="toggleSelect(item.changeId)"
            />
          </label>

          <div class="diff-item__body">
            <div class="diff-item__head">
              <span class="diff-item__title">{{ item.card.title }}</span>
              <div class="diff-item__badges">
                <RiskBadge :level="item.card.risk_level" />
                <ConfidenceBadge :confidence="item.card.confidence" />
              </div>
            </div>

            <!-- 段落定位 (P1-1) -->
            <div v-if="item.change.paragraph_index != null || item.card.paragraph_index != null" class="diff-item__location">
              第 {{ (item.card.paragraph_index ?? item.change.paragraph_index ?? 0) + 1 }} 段
              <span v-if="item.change.source || item.card.source" class="diff-item__source">
                &middot; 来源：{{ item.change.source || item.card.source }}
              </span>
            </div>

            <div class="diff-line diff-line--old">{{ item.card.before }}</div>
            <div class="diff-line diff-line--new">{{ item.card.after }}</div>

            <!-- 修改理由 (P1-1) -->
            <details v-if="getExplanation(item)" class="diff-item__reason">
              <summary>为什么建议这样改？</summary>
              <p>{{ getExplanation(item) }}</p>
            </details>
          </div>

          <!-- 拒绝理由弹窗 (P2-6) -->
          <div v-if="rejectingItemId === item.changeId" class="reject-form">
            <p class="reject-form__title">请选择拒绝理由：</p>
            <div class="reject-form__options">
              <label v-for="reason in rejectReasons" :key="reason" class="reject-option">
                <input v-model="rejectReason" :value="reason" type="radio" name="reject-reason" />
                <span>{{ reason }}</span>
              </label>
            </div>
            <textarea
              v-if="rejectReason === '其他'"
              v-model="customReason"
              class="reject-form__custom"
              placeholder="请输入具体原因..."
              rows="2"
            ></textarea>
            <div class="reject-form__actions">
              <button class="mini-btn" @click="cancelReject">取消</button>
              <button class="mini-btn mini-btn--danger" :disabled="!rejectReason" @click="confirmReject">确认拒绝</button>
            </div>
          </div>
        </div>
      </div>

      <!-- 操作按钮 -->
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

      <p v-if="state.error && state.step === 'reviewing'" class="worklist-error">{{ state.error }}</p>
    </div>
  </div>
</template>

<style scoped>
.diff-review {
  color: var(--text-primary, #1a1d23);
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
  color: var(--risk-low, #43A047);
  font-size: 13px;
  font-weight: 600;
  margin: 0;
}

.download-btn {
  background: var(--brand-cyan, #0f9ed5);
  border-radius: var(--radius-md, 8px);
  color: var(--text-white, #fff);
  font-size: 13px;
  font-weight: 600;
  padding: 9px 14px;
  text-align: center;
  text-decoration: none;
}

.ghost-btn {
  background: transparent;
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-md, 8px);
  color: var(--text-secondary, #5b626c);
  font-size: 12px;
  padding: 7px 12px;
}

.ghost-btn:hover {
  background: var(--bg-subtle, #f5f7fa);
  color: var(--text-primary, #1a1d23);
}

.worklist {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
}

/* 批量操作区 */
.worklist__batch {
  background: var(--bg-subtle, #f5f7fa);
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-md, 8px);
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
}

.batch-stats {
  display: flex;
  gap: 12px;
}

.batch-stat {
  color: var(--text-secondary, #5b626c);
  font-size: 11px;
}

.batch-stat--high {
  color: var(--risk-high, #E53935);
  font-weight: 600;
}

.batch-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.batch-btn {
  background: var(--bg-white, #fff);
  border: 1px solid var(--border-normal, #d0d5dd);
  border-radius: var(--radius-sm, 4px);
  color: var(--text-secondary, #5b626c);
  cursor: pointer;
  font-size: 11px;
  padding: 5px 10px;
}

.batch-btn:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

.batch-btn--smart {
  background: var(--brand-cyan, #0f9ed5);
  border-color: var(--brand-cyan, #0f9ed5);
  color: var(--text-white, #fff);
  font-weight: 600;
}

.batch-btn--review {
  background: rgba(229, 57, 53, 0.1);
  border-color: rgba(229, 57, 53, 0.3);
  color: var(--risk-high, #E53935);
}

/* 筛选区 */
.worklist__filter {
  align-items: center;
  display: flex;
  gap: 8px;
  justify-content: space-between;
}

.filter-tabs {
  display: flex;
  gap: 2px;
}

.filter-tab {
  background: transparent;
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-sm, 4px);
  color: var(--text-secondary, #5b626c);
  cursor: pointer;
  font-size: 11px;
  padding: 3px 8px;
}

.filter-tab--active {
  background: var(--brand-cyan, #0f9ed5);
  border-color: var(--brand-cyan, #0f9ed5);
  color: var(--text-white, #fff);
}

.worklist__select {
  display: flex;
  gap: 4px;
}

.mini-btn {
  background: var(--bg-subtle, #f5f7fa);
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-sm, 4px);
  color: var(--text-primary, #1a1d23);
  cursor: pointer;
  font-size: 11px;
  padding: 3px 8px;
}

.mini-btn:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

.mini-btn--danger {
  background: var(--risk-high, #E53935);
  border-color: var(--risk-high, #E53935);
  color: var(--text-white, #fff);
}

.worklist__items {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 400px;
  overflow-y: auto;
}

.diff-item {
  background: var(--bg-subtle, #f5f7fa);
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-md, 8px);
  display: flex;
  gap: 8px;
  padding: 10px;
}

.diff-item--selected {
  background: rgba(15, 158, 213, 0.06);
  border-color: rgba(15, 158, 213, 0.35);
}

.diff-item--high-risk {
  border-left: 3px solid var(--risk-high, #E53935);
}

.diff-item__check input {
  accent-color: var(--brand-cyan, #0f9ed5);
  cursor: pointer;
  height: 15px;
  margin-top: 2px;
  width: 15px;
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
  color: var(--text-primary, #1a1d23);
  flex: 1;
  font-size: 12px;
  font-weight: 600;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.diff-item__badges {
  align-items: center;
  display: flex;
  flex-shrink: 0;
  gap: 4px;
}

.diff-item__location {
  color: var(--text-secondary, #5b626c);
  font-size: 11px;
  margin-bottom: 4px;
}

.diff-item__source {
  color: var(--text-muted, #9ca3af);
}

.diff-line {
  border-radius: var(--radius-sm, 4px);
  font-size: 11px;
  line-height: 1.5;
  overflow: hidden;
  padding: 3px 6px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.diff-line--old {
  background: var(--diff-del-bg, #FFEBEE);
  color: var(--diff-del-text, #C62828);
  text-decoration: line-through;
}

.diff-line--new {
  background: var(--diff-add-bg, #E8F5E9);
  color: var(--diff-add-text, #2E7D32);
  margin-top: 2px;
}

.diff-item__reason {
  margin-top: 6px;
}

.diff-item__reason summary {
  color: var(--brand-cyan, #0f9ed5);
  cursor: pointer;
  font-size: 11px;
}

.diff-item__reason p {
  color: var(--text-secondary, #5b626c);
  font-size: 11px;
  line-height: 1.6;
  margin: 4px 0 0;
}

/* 拒绝理由弹窗 */
.reject-form {
  background: var(--bg-white, #fff);
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-sm, 4px);
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-left: 23px;
  padding: 10px;
}

.reject-form__title {
  color: var(--text-primary, #1a1d23);
  font-size: 12px;
  font-weight: 600;
  margin: 0;
}

.reject-form__options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.reject-option {
  align-items: center;
  cursor: pointer;
  display: flex;
  font-size: 12px;
  gap: 4px;
}

.reject-option input {
  accent-color: var(--brand-cyan, #0f9ed5);
}

.reject-form__custom {
  background: var(--bg-subtle, #f5f7fa);
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-sm, 4px);
  color: var(--text-primary, #1a1d23);
  font-size: 12px;
  padding: 6px 8px;
  resize: vertical;
  width: 100%;
}

.reject-form__actions {
  display: flex;
  gap: 6px;
  justify-content: flex-end;
}

.worklist__actions {
  border-top: 1px solid var(--border-light, #e8eaef);
  display: flex;
  gap: 6px;
  padding-top: 8px;
}

.act-btn {
  align-items: center;
  border: none;
  border-radius: var(--radius-md, 8px);
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
  background: var(--brand-cyan, #0f9ed5);
  color: var(--text-white, #fff);
}

.act-btn--reject {
  background: rgba(229, 57, 53, 0.12);
  color: var(--risk-high, #E53935);
}

.act-btn--retry {
  background: var(--bg-subtle, #f5f7fa);
  border: 1px solid var(--border-light, #e8eaef);
  color: var(--text-primary, #1a1d23);
}

.worklist-error {
  color: var(--risk-high, #E53935);
  font-size: 11px;
  margin: 4px 0 0;
}

.spinner {
  animation: spin 0.6s linear infinite;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  border-top-color: currentColor;
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
