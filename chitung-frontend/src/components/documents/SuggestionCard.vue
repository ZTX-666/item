<script setup lang="ts">
import { ref } from 'vue'
import type { DocmatePreviewCard, RejectReason } from '../../types/domain'
import RiskBadge from './RiskBadge.vue'
import ConfidenceBadge from './ConfidenceBadge.vue'

/**
 * SuggestionCard — 单条修改建议卡片
 * 展示：标题 + 段落定位 + before/after diff + 风险徽标 + 置信度徽标 + 理由（折叠）
 * 操作：接受 / 拒绝 / 修改
 * 拒绝时弹出理由选择（P2-6）
 */
const props = defineProps<{
  suggestion: DocmatePreviewCard
  selected?: boolean
  disabled?: boolean
}>()

const emit = defineEmits<{
  accept: [changeId: string]
  reject: [changeId: string, reason?: string]
  edit: [changeId: string]
  toggleSelect: [changeId: string]
}>()

const showReason = ref(false)
const showExplanation = ref(false)
const customReason = ref('')
const selectedReason = ref<RejectReason | ''>('')

const rejectReasons: RejectReason[] = ['修改过度', '语义错误', '不符合规范', '其他']

const explanation = ref(
  props.suggestion.explanation || props.suggestion.reason || '',
)

const paragraphLabel = ref(
  props.suggestion.paragraph_index != null ? `第 ${props.suggestion.paragraph_index + 1} 段` : '',
)

function handleReject() {
  showReason.value = true
}

function confirmReject() {
  const reason = selectedReason.value === '其他' ? customReason.value || '其他' : selectedReason.value || '未提供理由'
  emit('reject', props.suggestion.change_id, reason)
  showReason.value = false
  selectedReason.value = ''
  customReason.value = ''
}

function cancelReject() {
  showReason.value = false
  selectedReason.value = ''
  customReason.value = ''
}
</script>

<template>
  <div class="suggestion-card" :class="{ 'suggestion-card--selected': props.selected }">
    <div class="suggestion-card__header">
      <label class="suggestion-card__check" @click.stop>
        <input
          type="checkbox"
          :checked="props.selected"
          :disabled="props.disabled"
          @change="emit('toggleSelect', props.suggestion.change_id)"
        />
      </label>
      <span class="suggestion-card__title">{{ props.suggestion.title }}</span>
      <div class="suggestion-card__badges">
        <RiskBadge :level="props.suggestion.risk_level" />
        <ConfidenceBadge :confidence="props.suggestion.confidence" />
      </div>
    </div>

    <div v-if="paragraphLabel" class="suggestion-card__location">
      <span class="location-icon">&#9999;</span>
      <span>{{ paragraphLabel }}</span>
      <span v-if="props.suggestion.source" class="location-source">&middot; 来源：{{ props.suggestion.source }}</span>
    </div>

    <div class="suggestion-card__diff">
      <div class="diff-line diff-line--before">
        <span class="diff-line__marker">-</span>
        <span class="diff-line__text">{{ props.suggestion.before }}</span>
      </div>
      <div class="diff-line diff-line--after">
        <span class="diff-line__marker">+</span>
        <span class="diff-line__text">{{ props.suggestion.after }}</span>
      </div>
    </div>

    <div v-if="explanation" class="suggestion-card__explanation">
      <button class="explanation-toggle" @click="showExplanation = !showExplanation">
        <span class="explanation-toggle__icon">{{ showExplanation ? '\u{25BC}' : '\u{25B8}' }}</span>
        为什么建议这样改？
      </button>
      <p v-if="showExplanation" class="explanation-text">{{ explanation }}</p>
    </div>

    <div v-if="!showReason" class="suggestion-card__actions">
      <button class="action-btn action-btn--accept" :disabled="props.disabled" @click="emit('accept', props.suggestion.change_id)">
        接受
      </button>
      <button class="action-btn action-btn--reject" :disabled="props.disabled" @click="handleReject">
        拒绝
      </button>
      <button class="action-btn action-btn--edit" :disabled="props.disabled" @click="emit('edit', props.suggestion.change_id)">
        修改
      </button>
    </div>

    <div v-if="showReason" class="suggestion-card__reject-form">
      <p class="reject-form__title">请选择拒绝理由（用于模型优化）：</p>
      <div class="reject-form__options">
        <label v-for="reason in rejectReasons" :key="reason" class="reject-option">
          <input v-model="selectedReason" :value="reason" type="radio" name="reject-reason" />
          <span>{{ reason }}</span>
        </label>
      </div>
      <textarea
        v-if="selectedReason === '其他'"
        v-model="customReason"
        class="reject-form__custom"
        placeholder="请输入具体原因..."
        rows="2"
      ></textarea>
      <div class="reject-form__actions">
        <button class="action-btn action-btn--cancel" @click="cancelReject">取消</button>
        <button class="action-btn action-btn--confirm-reject" :disabled="!selectedReason" @click="confirmReject">
          确认拒绝
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.suggestion-card {
  background: var(--bg-subtle, #f5f7fa);
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-md, 8px);
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  transition: border-color 120ms ease;
}

.suggestion-card--selected {
  border-color: var(--brand-cyan, #0f9ed5);
  background: rgba(15, 158, 213, 0.04);
}

.suggestion-card__header {
  align-items: center;
  display: flex;
  gap: 8px;
}

.suggestion-card__check input {
  accent-color: var(--brand-cyan, #0f9ed5);
  cursor: pointer;
  height: 15px;
  width: 15px;
}

.suggestion-card__title {
  color: var(--text-primary, #1a1d23);
  flex: 1;
  font-size: 13px;
  font-weight: 600;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.suggestion-card__badges {
  align-items: center;
  display: flex;
  flex-shrink: 0;
  gap: 4px;
}

.suggestion-card__location {
  align-items: center;
  color: var(--text-secondary, #5b626c);
  display: flex;
  font-size: 11px;
  gap: 4px;
}

.location-icon {
  font-size: 10px;
}

.location-source {
  color: var(--text-muted, #9ca3af);
}

.suggestion-card__diff {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.diff-line {
  align-items: flex-start;
  border-radius: var(--radius-sm, 4px);
  display: flex;
  font-size: 12px;
  gap: 6px;
  line-height: 1.5;
  padding: 4px 8px;
}

.diff-line__marker {
  flex-shrink: 0;
  font-weight: 700;
  width: 12px;
}

.diff-line--before {
  background: var(--diff-del-bg, #FFEBEE);
  color: var(--diff-del-text, #C62828);
  text-decoration: line-through;
}

.diff-line--after {
  background: var(--diff-add-bg, #E8F5E9);
  color: var(--diff-add-text, #2E7D32);
}

.diff-line__text {
  word-break: break-word;
}

.suggestion-card__explanation {
  border-top: 1px solid var(--border-light, #e8eaef);
  padding-top: 6px;
}

.explanation-toggle {
  align-items: center;
  background: none;
  border: none;
  color: var(--brand-cyan, #0f9ed5);
  cursor: pointer;
  display: flex;
  font-size: 11px;
  gap: 4px;
  padding: 0;
}

.explanation-toggle__icon {
  font-size: 9px;
}

.explanation-text {
  color: var(--text-secondary, #5b626c);
  font-size: 12px;
  line-height: 1.6;
  margin: 6px 0 0;
}

.suggestion-card__actions {
  display: flex;
  gap: 6px;
}

.action-btn {
  border: none;
  border-radius: var(--radius-sm, 4px);
  cursor: pointer;
  flex: 1;
  font-size: 12px;
  font-weight: 600;
  padding: 7px 10px;
  transition: opacity 120ms ease;
}

.action-btn:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

.action-btn--accept {
  background: var(--brand-cyan, #0f9ed5);
  color: var(--text-white, #fff);
}

.action-btn--reject {
  background: rgba(229, 57, 53, 0.12);
  color: var(--risk-high, #E53935);
}

.action-btn--edit {
  background: var(--bg-white, #fff);
  border: 1px solid var(--border-normal, #d0d5dd);
  color: var(--text-secondary, #5b626c);
}

.suggestion-card__reject-form {
  background: var(--bg-white, #fff);
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-sm, 4px);
  display: flex;
  flex-direction: column;
  gap: 8px;
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

.action-btn--cancel {
  background: var(--bg-subtle, #f5f7fa);
  border: 1px solid var(--border-light, #e8eaef);
  color: var(--text-secondary, #5b626c);
  flex: none;
  padding: 6px 12px;
}

.action-btn--confirm-reject {
  background: var(--risk-high, #E53935);
  color: var(--text-white, #fff);
  flex: none;
  padding: 6px 12px;
}

.action-btn--confirm-reject:disabled {
  opacity: 0.4;
}
</style>
