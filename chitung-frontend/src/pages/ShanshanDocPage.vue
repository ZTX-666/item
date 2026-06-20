<script setup lang="ts">
import { ref, computed } from 'vue'
import { docmateRead, docmateGenerate, docmatePreview, docmateApply } from '../services/chitungApi'
import type {
  DocmateReadResult,
  DocmateGenerateResult,
  DocmatePreviewResult,
  DocmateApplyResult,
  DocmatePreviewCard,
} from '../types/domain'

// ── State ──
const step = ref<
  'idle' | 'loading' | 'loaded' | 'generating' | 'generated' | 'previewing' | 'previewed' | 'applying' | 'applied' | 'error'
>('idle')

const filePath = ref('')
const docId = ref('')
const readResult = ref<DocmateReadResult | null>(null)
const genResult = ref<DocmateGenerateResult | null>(null)
const previewResult = ref<DocmatePreviewResult | null>(null)
const applyResult = ref<DocmateApplyResult | null>(null)

const instruction = ref('')
const outputPath = ref('')
const acceptedChangeIds = ref<Set<string>>(new Set())
const errorMsg = ref('')

// ── Computed ──
const previewCards = computed<DocmatePreviewCard[]>(() =>
  previewResult.value?.data?.preview_cards ?? genResult.value?.data?.preview_cards ?? []
)

const docStats = computed(() => readResult.value?.data?.stats ?? { paragraph_count: 0, table_count: 0, image_count: 0 })

const allRiskLow = computed(() =>
  previewCards.value.every((c) => c.risk_level === 'low')
)

const toggleChange = (changeId: string) => {
  const next = new Set(acceptedChangeIds.value)
  if (next.has(changeId)) next.delete(changeId)
  else next.add(changeId)
  acceptedChangeIds.value = next
}

const selectAll = () => {
  acceptedChangeIds.value = new Set(previewCards.value.map((c) => c.change_id))
}

const deselectAll = () => {
  acceptedChangeIds.value = new Set()
}

// ── Actions ──
async function handleLoad() {
  if (!filePath.value.trim()) return
  step.value = 'loading'
  errorMsg.value = ''
  try {
    const r = await docmateRead(filePath.value.trim())
    if (!r.ok) throw new Error(r.error ?? '读取失败')
    if (!r.data.doc_id) throw new Error('文档读取成功但未返回 doc_id')
    readResult.value = r
    docId.value = r.data.doc_id
    genResult.value = null
    previewResult.value = null
    applyResult.value = null
    acceptedChangeIds.value = new Set()
    step.value = 'loaded'
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : '未知错误'
    step.value = 'error'
  }
}

async function handleGenerate() {
  if (!instruction.value.trim() || !docId.value) return
  step.value = 'generating'
  errorMsg.value = ''
  try {
    const r = await docmateGenerate({ docId: docId.value, instruction: instruction.value.trim() })
    if (!r.ok) throw new Error(r.error ?? '生成失败')
    genResult.value = r
    previewResult.value = null
    acceptedChangeIds.value = new Set(r.data.preview_cards.map((c) => c.change_id))
    step.value = 'generated'

    if (!outputPath.value.trim() && readResult.value?.data?.source_path) {
      outputPath.value = readResult.value.data.source_path.replace(/\.docx$/i, '_modified.docx')
    }
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : '未知错误'
    step.value = 'error'
  }
}

async function handlePreview() {
  if (!genResult.value?.data?.changeset_id) return
  step.value = 'previewing'
  errorMsg.value = ''
  try {
    const r = await docmatePreview(genResult.value.data.changeset_id)
    if (!r.ok) throw new Error(r.error ?? '预览失败')
    previewResult.value = r
    acceptedChangeIds.value = new Set(r.data.preview_cards.map((c) => c.change_id))
    step.value = 'previewed'
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : '未知错误'
    step.value = 'error'
  }
}

async function handleApply() {
  if (!genResult.value?.data?.changeset_id || !outputPath.value.trim()) return
  step.value = 'applying'
  errorMsg.value = ''
  try {
    const r = await docmateApply({
      changesetId: genResult.value.data.changeset_id,
      acceptedChangeIds: [...acceptedChangeIds.value],
      saveAs: outputPath.value.trim(),
    })
    applyResult.value = r
    step.value = r.ok ? 'applied' : 'error'
    if (!r.ok) errorMsg.value = '应用失败'
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : '未知错误'
    step.value = 'error'
  }
}

function handleReset() {
  step.value = 'idle'
  readResult.value = null
  genResult.value = null
  previewResult.value = null
  applyResult.value = null
  docId.value = ''
  instruction.value = ''
  outputPath.value = ''
  acceptedChangeIds.value = new Set()
  errorMsg.value = ''
}

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
  <div class="shanshan-doc">
    <!-- Left Panel: File Input + Doc Info -->
    <aside class="panel panel--left">
      <h2 class="panel__title">文档加载</h2>
      <div class="field">
        <label class="field__label" for="docx-path">.docx 文件路径</label>
        <input
          id="docx-path"
          v-model="filePath"
          type="text"
          class="field__input"
          placeholder="C:\path\to\document.docx"
          :disabled="step === 'loading' || step === 'generating' || step === 'applying'"
        />
      </div>
      <button
        class="btn btn--primary"
        :disabled="!filePath.trim() || step === 'loading'"
        @click="handleLoad"
      >
        <span v-if="step === 'loading'" class="spinner"></span>
        <span v-else>加载文档</span>
      </button>

      <div v-if="readResult" class="doc-info">
        <h3 class="doc-info__title">文档信息</h3>
        <div class="doc-info__stat">
          <span class="stat-label">段落数</span>
          <span class="stat-value">{{ docStats.paragraph_count }}</span>
        </div>
        <div class="doc-info__stat">
          <span class="stat-label">表格数</span>
          <span class="stat-value">{{ docStats.table_count }}</span>
        </div>
        <div class="doc-info__stat">
          <span class="stat-label">图片数</span>
          <span class="stat-value">{{ docStats.image_count }}</span>
        </div>
        <div class="doc-info__stat">
          <span class="stat-label">Doc ID</span>
          <span class="stat-value stat-value--mono">{{ docId.slice(0, 12) }}...</span>
        </div>
      </div>
    </aside>

    <!-- Center Panel: Document Content Preview -->
    <main class="panel panel--center">
      <h2 class="panel__title">文档预览</h2>
      <div v-if="step === 'idle'" class="empty-state">
        <span class="empty-state__icon">📄</span>
        <p>输入 .docx 文件路径后点击「加载文档」</p>
      </div>
      <div v-else-if="step === 'loading'" class="empty-state">
        <span class="spinner spinner--large"></span>
        <p>正在解析文档...</p>
      </div>
      <div v-else-if="readResult" class="doc-preview">
        <div class="doc-preview__text">
          <p class="doc-preview__heading">文档段落内容</p>
          <div
            v-for="(p, idx) in readResult.data.structure.paragraphs"
            :key="idx"
            class="doc-preview__para"
          >
            <span class="para-index">{{ idx + 1 }}</span>
            <span class="para-text">{{ p.text }}</span>
          </div>
        </div>
      </div>
      <div v-else-if="errorMsg" class="error-card">
        <span class="error-card__icon">⚠️</span>
        <p>{{ errorMsg }}</p>
      </div>
    </main>

    <!-- Right Panel: AI Instruction + Changes -->
    <aside class="panel panel--right">
      <h2 class="panel__title">AI 编辑指令</h2>

      <!-- Instruction input -->
      <div class="field">
        <label class="field__label" for="instruction">修改指令</label>
        <textarea
          id="instruction"
          v-model="instruction"
          class="field__textarea"
          rows="3"
          placeholder="例如：将巡检人员从张三改为李四&#10;或：把风险等级改为高风险"
          :disabled="step !== 'loaded'"
        ></textarea>
      </div>
      <button
        class="btn btn--accent"
        :disabled="!instruction.trim() || step !== 'loaded'"
        @click="handleGenerate"
      >
        <span v-if="step === 'generating'" class="spinner"></span>
        <span v-else>生成修改方案</span>
      </button>

      <button
        class="btn btn--small btn--preview"
        :disabled="!genResult?.data?.changeset_id || (step !== 'generated' && step !== 'previewed')"
        @click="handlePreview"
      >
        <span v-if="step === 'previewing'" class="spinner"></span>
        <span v-else>刷新预览</span>
      </button>

      <!-- Change preview cards -->
      <div v-if="previewCards.length > 0" class="changes-section">
        <div class="changes-section__header">
          <h3>变更预览 ({{ previewCards.length }} 项)</h3>
          <div class="changes-section__actions">
            <button class="btn btn--small" @click="selectAll">全选</button>
            <button class="btn btn--small" @click="deselectAll">取消</button>
          </div>
        </div>
        <div class="changes-list">
          <div
            v-for="card in previewCards"
            :key="card.change_id"
            class="change-card"
            :class="{ 'change-card--selected': acceptedChangeIds.has(card.change_id) }"
            @click="toggleChange(card.change_id)"
          >
            <div class="change-card__header">
              <span class="change-card__checkbox">
                {{ acceptedChangeIds.has(card.change_id) ? '☑' : '☐' }}
              </span>
              <span class="change-card__title">{{ card.title }}</span>
              <span class="change-card__badge" :class="riskClass(card.risk_level)">
                {{ riskLabel(card.risk_level) }}
              </span>
            </div>
            <div class="change-card__diff">
              <div class="diff-line diff-line--old">{{ card.before }}</div>
              <div class="diff-line diff-line--new">{{ card.after }}</div>
            </div>
            <div class="change-card__meta">
              <span>{{ card.type }}</span>
              <span>置信度 {{ Math.round(card.confidence * 100) }}%</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Output & Apply -->
      <div v-if="step === 'generated' || step === 'previewed' || step === 'applying'" class="apply-section">
        <div class="field">
          <label class="field__label" for="output-path">输出路径</label>
          <input
            id="output-path"
            v-model="outputPath"
            type="text"
            class="field__input"
            :placeholder="readResult?.data?.source_path?.replace('.docx', '_modified.docx') ?? 'C:\\output.docx'"
          />
        </div>
        <button
          class="btn btn--primary"
          :disabled="!outputPath.trim() || acceptedChangeIds.size === 0"
          @click="handleApply"
        >
          <span v-if="step === 'applying'" class="spinner"></span>
          <span>{{ step === 'applying' ? '应用中...' : `应用修改 (${acceptedChangeIds.size} 项)` }}</span>
        </button>
        <p v-if="!allRiskLow" class="risk-warning">
          ⚠️ 包含中高风险变更，请仔细确认后再应用。
        </p>
      </div>

      <!-- Apply result -->
      <div v-if="step === 'applied' && applyResult" class="result-card result-card--success">
        <span class="result-card__icon">✅</span>
        <p><strong>应用成功</strong></p>
        <p>已应用 {{ applyResult.data.applied }} 项，拒绝 {{ applyResult.data.rejected }} 项</p>
        <p class="result-card__path">输出：{{ applyResult.data.output_path }}</p>
        <p class="result-card__path">备份：{{ applyResult.data.backup_path }}</p>
      </div>

      <!-- Error -->
      <div v-if="errorMsg && step === 'error'" class="result-card result-card--error">
        <span class="result-card__icon">❌</span>
        <p>{{ errorMsg }}</p>
      </div>

      <!-- Reset -->
      <div v-if="step === 'applied' || step === 'error'" class="reset-area">
        <button class="btn btn--ghost" @click="handleReset">重新开始</button>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.shanshan-doc {
  display: grid;
  grid-template-columns: 260px 1fr 340px;
  gap: 16px;
  height: calc(100vh - 56px);
  padding: 16px;
  overflow: hidden;
}

.panel {
  background: var(--bg-card, #1a1a1e);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  padding: 16px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary, #a0a0a8);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 0;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.field__label {
  font-size: 11px;
  color: var(--text-secondary, #a0a0a8);
}

.field__input,
.field__textarea {
  background: var(--bg-primary, #0f0f12);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  padding: 8px 12px;
  color: var(--text-primary, #e8e8ec);
  font-size: 13px;
  font-family: inherit;
  outline: none;
  transition: border-color 0.15s;
}

.field__input:focus,
.field__textarea:focus {
  border-color: var(--accent, #6c8cff);
}

.field__textarea {
  resize: vertical;
  min-height: 60px;
}

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: none;
  border-radius: 8px;
  padding: 8px 16px;
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s;
}

.btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn--primary {
  background: linear-gradient(135deg, #6c8cff, #5070e0);
  color: #fff;
}

.btn--primary:hover:not(:disabled) {
  background: linear-gradient(135deg, #7d9aff, #6080f0);
}

.btn--accent {
  background: linear-gradient(135deg, #a78bfa, #8b5cf6);
  color: #fff;
}

.btn--accent:hover:not(:disabled) {
  background: linear-gradient(135deg, #b89eff, #9d6fff);
}

.btn--small {
  padding: 4px 10px;
  font-size: 11px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-secondary, #a0a0a8);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.btn--small:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--text-primary, #e8e8ec);
}

.btn--preview {
  align-self: flex-start;
}

.btn--ghost {
  background: transparent;
  color: var(--text-secondary, #a0a0a8);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.btn--ghost:hover {
  color: var(--text-primary, #e8e8ec);
  border-color: rgba(255, 255, 255, 0.2);
}

.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  display: inline-block;
}

.spinner--large {
  width: 32px;
  height: 32px;
  border-width: 3px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.doc-info {
  margin-top: 4px;
}

.doc-info__title {
  font-size: 12px;
  color: var(--text-secondary, #a0a0a8);
  margin: 0 0 8px 0;
}

.doc-info__stat {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 12px;
}

.stat-label { color: var(--text-secondary, #a0a0a8); }
.stat-value { color: var(--text-primary, #e8e8ec); font-weight: 500; }
.stat-value--mono { font-family: 'Consolas', monospace; font-size: 11px; }

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--text-secondary, #a0a0a8);
  font-size: 13px;
}

.empty-state__icon { font-size: 32px; }

.doc-preview { flex: 1; overflow-y: auto; }

.doc-preview__heading {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary, #a0a0a8);
  margin-bottom: 8px;
}

.doc-preview__para {
  display: flex;
  gap: 8px;
  padding: 4px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.para-index {
  flex-shrink: 0;
  width: 22px;
  font-size: 10px;
  color: var(--text-secondary, #a0a0a8);
  text-align: right;
}

.para-text {
  font-size: 13px;
  color: var(--text-primary, #e8e8ec);
  line-height: 1.5;
}

.error-card {
  display: flex;
  gap: 8px;
  padding: 12px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.25);
  border-radius: 8px;
  font-size: 13px;
  color: #fca5a5;
}

.error-card__icon { font-size: 16px; flex-shrink: 0; }

.changes-section {
  margin-top: 4px;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.changes-section__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.changes-section__header h3 {
  font-size: 12px;
  color: var(--text-secondary, #a0a0a8);
  margin: 0;
}

.changes-section__actions {
  display: flex;
  gap: 4px;
}

.changes-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.change-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 8px;
  padding: 10px;
  cursor: pointer;
  transition: all 0.15s;
}

.change-card:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.12);
}

.change-card--selected {
  border-color: rgba(108, 140, 255, 0.4);
  background: rgba(108, 140, 255, 0.08);
}

.change-card__header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.change-card__checkbox { font-size: 14px; }

.change-card__title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary, #e8e8ec);
  flex: 1;
}

.change-card__badge {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 500;
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

.change-card__diff {
  margin-bottom: 6px;
}

.diff-line {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 3px;
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.diff-line--old {
  color: #f87171;
  background: rgba(239, 68, 68, 0.08);
}

.diff-line--new {
  color: #4ade80;
  background: rgba(34, 197, 94, 0.08);
}

.change-card__meta {
  display: flex;
  gap: 12px;
  font-size: 10px;
  color: var(--text-secondary, #a0a0a8);
}

.apply-section {
  margin-top: auto;
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.risk-warning {
  font-size: 11px;
  color: #fbbf24;
  margin: 0;
}

.result-card {
  padding: 12px;
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.6;
}

.result-card--success {
  background: rgba(34, 197, 94, 0.1);
  border: 1px solid rgba(34, 197, 94, 0.2);
  color: #86efac;
}

.result-card--error {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.2);
  color: #fca5a5;
}

.result-card__icon { font-size: 18px; }
.result-card p { margin: 2px 0; }
.result-card__path {
  font-family: 'Consolas', monospace;
  font-size: 10px;
  opacity: 0.8;
  word-break: break-all;
}

.reset-area {
  text-align: center;
  padding-top: 4px;
}
</style>
