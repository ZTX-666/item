<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  docmateUpload,
  extractTableMappingFields,
  listTableMappingForms,
  runTableMappingFill,
} from '../services/chitungApi'
import type {
  TableMappingExtractResult,
  TableMappingForm,
  TableMappingRunResult,
} from '../types/domain'
import SkeletonLoader from '../components/common/SkeletonLoader.vue'

/**
 * TableMappingPage — 表格映射页
 * P0-4: 拖拽上传替代手填路径
 * P0-5: 隐藏调试信息，移除"填入测试值"
 * P1-4: 空状态 + CTA
 * P1-6: 骨架屏
 */

type Step = 'idle' | 'loadingForms' | 'uploading' | 'extracting' | 'extracted' | 'running' | 'completed' | 'error'

const step = ref<Step>('idle')
const forms = ref<TableMappingForm[]>([])
const filePath = ref('')
const uploadedFileName = ref('')
const selectedFormId = ref('')
const extractResult = ref<TableMappingExtractResult | null>(null)
const runResult = ref<TableMappingRunResult | null>(null)
const fieldValues = ref<Record<string, string>>({})
const errorMsg = ref('')
const screenshot = ref(true)
const dryRun = ref(false)

// 拖拽上传状态
const dragOver = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

const selectedForm = computed(() => forms.value.find((item) => item.id === selectedFormId.value) ?? null)

const groupedForms = computed(() => {
  const groups: Record<string, TableMappingForm[]> = {}
  for (const form of forms.value) {
    const key = form.category || '未分类'
    if (!groups[key]) groups[key] = []
    groups[key].push(form)
  }
  return groups
})

const editableFields = computed(() => selectedForm.value?.fields ?? [])
const matchedCount = computed(() => Object.values(fieldValues.value).filter((value) => value.trim()).length)
const canExtract = computed(() => Boolean(filePath.value.trim() && selectedFormId.value && step.value !== 'extracting' && step.value !== 'uploading'))
const canRun = computed(() => Boolean(canExtract.value && matchedCount.value > 0 && step.value !== 'running'))

onMounted(loadForms)

async function loadForms() {
  step.value = 'loadingForms'
  errorMsg.value = ''
  try {
    const result = await listTableMappingForms()
    forms.value = result.items
    if (!selectedFormId.value && result.items.length) {
      selectedFormId.value = result.items[0].id
    }
    seedFields()
    step.value = 'idle'
  } catch (error) {
    errorMsg.value = error instanceof Error ? error.message : '加载表单清单失败'
    step.value = 'error'
  }
}

function seedFields() {
  const next: Record<string, string> = {}
  for (const field of editableFields.value) {
    next[field.name] = fieldValues.value[field.name] ?? ''
  }
  fieldValues.value = next
}

function handleFormChange() {
  extractResult.value = null
  runResult.value = null
  seedFields()
}

// P0-4: 拖拽上传
function pickFile() {
  fileInput.value?.click()
}

async function handleUpload(file: File) {
  if (!file.name.toLowerCase().endsWith('.docx')) {
    errorMsg.value = '仅支持 .docx 文件'
    step.value = 'error'
    return
  }

  step.value = 'uploading'
  errorMsg.value = ''
  try {
    const result = await docmateUpload(file)
    if (!result.ok || !result.file_path) {
      throw new Error(result.error || '文件上传失败')
    }
    filePath.value = result.file_path
    uploadedFileName.value = result.file_name || file.name
    step.value = 'idle'
  } catch (error) {
    errorMsg.value = error instanceof Error ? error.message : '文件上传失败'
    step.value = 'error'
  }
}

function onFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) handleUpload(file)
  target.value = ''
}

function onDrop(event: DragEvent) {
  dragOver.value = false
  const file = event.dataTransfer?.files?.[0]
  if (file) handleUpload(file)
}

async function handleExtract() {
  if (!canExtract.value) return
  step.value = 'extracting'
  errorMsg.value = ''
  runResult.value = null
  try {
    const result = await extractTableMappingFields({
      filePath: filePath.value.trim(),
      formId: selectedFormId.value,
    })
    extractResult.value = result
    const next: Record<string, string> = {}
    for (const field of result.form.fields) {
      next[field.name] = result.fields[field.name]?.value ?? ''
    }
    fieldValues.value = next
    step.value = 'extracted'
  } catch (error) {
    errorMsg.value = error instanceof Error ? error.message : '字段抽取失败'
    step.value = 'error'
  }
}

async function handleRun() {
  if (!canRun.value) return
  step.value = 'running'
  errorMsg.value = ''
  runResult.value = null
  try {
    const result = await runTableMappingFill({
      filePath: filePath.value.trim(),
      formId: selectedFormId.value,
      fields: fieldValues.value,
      action: 'draft',
      screenshot: screenshot.value,
      dryRun: dryRun.value,
    })
    runResult.value = result
    step.value = result.ok ? 'completed' : 'error'
    if (!result.ok) {
      errorMsg.value = '保存草稿失败，请检查表单字段是否完整'
    }
  } catch (error) {
    errorMsg.value = error instanceof Error ? error.message : '保存草稿失败'
    step.value = 'error'
  }
}
</script>

<template>
  <div class="table-mapping-page">
    <!-- 左栏：设置 -->
    <section class="mapping-card mapping-card--setup">
      <div class="mapping-card__header">
        <div>
          <p class="eyebrow">闪闪文档 · 表格映射</p>
          <h2>C-SMART 自动填表</h2>
        </div>
      </div>

      <!-- P0-4: 拖拽上传区 -->
      <div class="upload-section">
        <label class="field__label">DOCX 文档</label>
        <div
          v-if="!uploadedFileName"
          class="dropzone"
          :class="{ 'dropzone--over': dragOver, 'dropzone--busy': step === 'uploading' }"
          @click="pickFile"
          @dragover.prevent="dragOver = true"
          @dragleave.prevent="dragOver = false"
          @drop.prevent="onDrop"
        >
          <template v-if="step === 'uploading'">
            <span class="spinner"></span>
            <p>正在上传...</p>
          </template>
          <template v-else>
            <div class="dropzone__icon">&#128194;</div>
            <p class="dropzone__lead">点击或拖拽上传 .docx 文档</p>
            <p class="dropzone__hint">上传后自动提取字段</p>
          </template>
        </div>
        <div v-else class="uploaded-file">
          <span class="uploaded-file__icon">&#128196;</span>
          <span class="uploaded-file__name" :title="uploadedFileName">{{ uploadedFileName }}</span>
          <button class="uploaded-file__change" @click="pickFile">点击重新选择</button>
        </div>
        <input ref="fileInput" type="file" accept=".docx" class="hidden-input" @change="onFileChange" />
      </div>

      <label class="field">
        <span class="field__label">目标表单</span>
        <select v-model="selectedFormId" class="input" @change="handleFormChange">
          <optgroup v-for="(items, category) in groupedForms" :key="category" :label="category">
            <option v-for="form in items" :key="form.id" :value="form.id">
              {{ form.id }} · {{ form.name }}
            </option>
          </optgroup>
        </select>
      </label>

      <div v-if="selectedForm" class="form-summary">
        <strong>{{ selectedForm.name }}</strong>
        <span>{{ selectedForm.category || '未分类' }} · {{ selectedForm.fields.length }} 个字段</span>
      </div>

      <div class="actions">
        <button class="btn btn--primary" :disabled="!canExtract" @click="handleExtract">
          {{ step === 'extracting' ? '抽取中...' : '从文档抽取字段' }}
        </button>
      </div>

      <div class="options">
        <label><input v-model="screenshot" type="checkbox" /> 保存执行截图</label>
        <label><input v-model="dryRun" type="checkbox" /> 只预览，不真正填表</label>
      </div>

      <!-- P1-4: 使用步骤说明 -->
      <div v-if="!uploadedFileName" class="usage-steps">
        <h3>使用步骤</h3>
        <ol>
          <li>上传 .docx 源文档</li>
          <li>选择目标表单</li>
          <li>点击「从文档抽取字段」</li>
          <li>确认字段后保存到系统草稿</li>
        </ol>
      </div>
    </section>

    <!-- 中栏：字段确认 -->
    <section class="mapping-card mapping-card--fields">
      <div class="mapping-card__header">
        <div>
          <p class="eyebrow">字段确认</p>
          <h2>文档字段 → 系统字段</h2>
        </div>
        <span class="counter">{{ matchedCount }}/{{ editableFields.length }}</span>
      </div>

      <!-- 骨架屏 (P1-6) -->
      <SkeletonLoader v-if="step === 'loadingForms'" type="rows" :count="5" />

      <div v-else-if="!selectedForm" class="empty-state">
        <p>正在加载表单...</p>
      </div>

      <div v-else class="field-list">
        <label v-for="field in editableFields" :key="field.name" class="mapping-row">
          <span class="mapping-row__name">{{ field.name }}</span>
          <input v-model="fieldValues[field.name]" class="input" type="text" placeholder="未抽取到，可手动填写" />
          <span class="mapping-row__source" :class="`source--${extractResult?.fields[field.name]?.source || 'manual'}`">
            {{ extractResult?.fields[field.name]?.source || 'manual' }}
          </span>
        </label>
      </div>
    </section>

    <!-- 右栏：执行 -->
    <section class="mapping-card mapping-card--run">
      <div class="mapping-card__header">
        <div>
          <p class="eyebrow">执行</p>
          <h2>保存到系统草稿</h2>
        </div>
      </div>

      <button class="btn btn--accent" :disabled="!canRun" @click="handleRun">
        {{ step === 'running' ? '正在保存...' : dryRun ? '预览执行命令' : '保存到系统草稿' }}
      </button>

      <div v-if="extractResult?.document_preview" class="preview-box">
        <strong>文档预览</strong>
        <p>{{ extractResult.document_preview }}</p>
      </div>

      <div v-if="runResult" class="result-box" :class="{ 'result-box--ok': runResult.ok }">
        <strong>{{ runResult.ok ? '执行成功' : '执行失败' }}</strong>
        <p>编号：{{ runResult.job_id }}</p>
        <p v-if="runResult.duration_ms">耗时：{{ Math.round(runResult.duration_ms / 1000) }} 秒</p>
      </div>

      <!-- P0-5: 技术详情折叠 -->
      <details v-if="runResult" class="tech-details">
        <summary>查看技术详情</summary>
        <div class="tech-details__body">
          <p v-if="runResult.command"><strong>命令：</strong>{{ runResult.command.join(' ') }}</p>
          <pre v-if="runResult.stdout" class="log-box">{{ runResult.stdout }}</pre>
          <pre v-if="runResult.stderr" class="log-box log-box--error">{{ runResult.stderr }}</pre>
        </div>
      </details>

      <!-- P0-5: 人话错误文案 -->
      <div v-if="errorMsg" class="error-card">
        <span class="error-card__icon">!</span>
        <p>{{ errorMsg }}</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.table-mapping-page {
  background: var(--bg-page, #f5f7fa);
  color: var(--text-primary, #1a1d23);
  display: grid;
  gap: 12px;
  grid-template-columns: 300px minmax(360px, 1fr) 360px;
  height: 100%;
  overflow: hidden;
  padding: 12px;
}

.mapping-card {
  background: var(--bg-white, #fff);
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-xl, 16px);
  box-shadow: var(--shadow-sm, 0 1px 3px rgba(0,0,0,0.06));
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
  overflow-y: auto;
  padding: 16px;
}

.mapping-card__header {
  align-items: flex-start;
  display: flex;
  gap: 12px;
  justify-content: space-between;
}

.mapping-card__header h2 {
  color: var(--text-primary, #1a1d23);
  font-size: 18px;
  margin: 2px 0 0;
}

.eyebrow {
  color: var(--brand-cyan, #0f9ed5);
  font-size: 11px;
  letter-spacing: 0.08em;
  margin: 0;
  text-transform: uppercase;
}

/* 上传区 */
.upload-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field__label {
  color: var(--text-secondary, #5b626c);
  font-size: 12px;
}

.dropzone {
  align-items: center;
  background: var(--bg-subtle, #f5f7fa);
  border: 1.5px dashed var(--border-normal, #d0d5dd);
  border-radius: var(--radius-lg, 12px);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 6px;
  justify-content: center;
  padding: 24px 12px;
  text-align: center;
  transition: all 120ms ease;
}

.dropzone:hover,
.dropzone--over {
  background: rgba(15, 158, 213, 0.06);
  border-color: var(--brand-cyan, #0f9ed5);
}

.dropzone--busy {
  cursor: default;
  opacity: 0.72;
}

.dropzone__icon {
  font-size: 28px;
}

.dropzone__lead {
  color: var(--text-primary, #1a1d23);
  font-size: 13px;
  margin: 0;
}

.dropzone__hint {
  color: var(--text-secondary, #5b626c);
  font-size: 11px;
  margin: 0;
}

.uploaded-file {
  align-items: center;
  background: var(--diff-add-bg, #E8F5E9);
  border: 1px solid rgba(67, 160, 71, 0.2);
  border-radius: var(--radius-md, 8px);
  display: flex;
  gap: 8px;
  padding: 10px 12px;
}

.uploaded-file__icon {
  font-size: 16px;
}

.uploaded-file__name {
  color: var(--text-primary, #1a1d23);
  flex: 1;
  font-size: 13px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.uploaded-file__change {
  background: none;
  border: none;
  color: var(--brand-cyan, #0f9ed5);
  cursor: pointer;
  font-size: 11px;
  white-space: nowrap;
}

.hidden-input {
  display: none;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.input {
  background: var(--bg-white, #fff);
  border: 1px solid var(--border-normal, #d0d5dd);
  border-radius: var(--radius-md, 8px);
  color: var(--text-primary, #1a1d23);
  min-height: 36px;
  padding: 8px 10px;
}

.input:focus {
  border-color: var(--brand-cyan, #0f9ed5);
  outline: none;
}

.form-summary {
  background: var(--bg-subtle, #f5f7fa);
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-md, 8px);
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
}

.form-summary strong {
  color: var(--text-primary, #1a1d23);
  font-size: 13px;
}

.form-summary span {
  color: var(--text-secondary, #5b626c);
  font-size: 12px;
}

.actions {
  display: flex;
  gap: 8px;
}

.options {
  color: var(--text-secondary, #5b626c);
  display: flex;
  flex-direction: column;
  font-size: 12px;
  gap: 4px;
}

.options label {
  cursor: pointer;
}

.btn {
  background: var(--bg-white, #fff);
  border: 1px solid var(--border-normal, #d0d5dd);
  border-radius: var(--radius-md, 8px);
  color: var(--text-secondary, #5b626c);
  cursor: pointer;
  flex: 1;
  font-size: 13px;
  padding: 9px 12px;
}

.btn:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.btn--primary {
  background: var(--brand-cyan, #0f9ed5);
  border-color: var(--brand-cyan, #0f9ed5);
  color: var(--text-white, #fff);
}

.btn--accent {
  background: var(--brand-cyan, #0f9ed5);
  border: none;
  color: var(--text-white, #fff);
  font-weight: 700;
  width: 100%;
}

.counter {
  border: 1px solid rgba(15, 158, 213, 0.28);
  border-radius: 999px;
  color: var(--brand-cyan, #0f9ed5);
  font-size: 12px;
  padding: 4px 8px;
  white-space: nowrap;
}

/* 使用步骤 */
.usage-steps {
  background: var(--bg-subtle, #f5f7fa);
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-md, 8px);
  padding: 12px;
}

.usage-steps h3 {
  color: var(--text-secondary, #5b626c);
  font-size: 12px;
  margin: 0 0 6px;
}

.usage-steps ol {
  color: var(--text-secondary, #5b626c);
  font-size: 12px;
  line-height: 1.8;
  margin: 0;
  padding-left: 18px;
}

/* 字段列表 */
.field-list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
}

.mapping-row {
  align-items: center;
  display: grid;
  gap: 8px;
  grid-template-columns: 130px minmax(160px, 1fr) 58px;
}

.mapping-row__name {
  color: var(--text-primary, #1a1d23);
  font-size: 13px;
}

.mapping-row__source {
  border-radius: var(--radius-sm, 4px);
  font-size: 10px;
  padding: 2px 4px;
  text-align: center;
}

.source--document {
  background: var(--diff-add-bg, #E8F5E9);
  color: var(--diff-add-text, #2E7D32);
}

.source--inferred {
  background: rgba(251, 140, 0, 0.1);
  color: var(--risk-medium, #FB8C00);
}

.source--manual {
  background: var(--bg-subtle, #f5f7fa);
  color: var(--text-muted, #9ca3af);
}

/* 结果 */
.preview-box,
.result-box {
  background: var(--bg-subtle, #f5f7fa);
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-md, 8px);
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px;
}

.preview-box strong,
.result-box strong {
  color: var(--text-primary, #1a1d23);
  font-size: 13px;
}

.preview-box p,
.result-box p {
  color: var(--text-secondary, #5b626c);
  font-size: 12px;
  margin: 0;
}

.result-box--ok {
  border-color: rgba(67, 160, 71, 0.3);
  background: var(--diff-add-bg, #E8F5E9);
}

/* 技术详情折叠 (P0-5) */
.tech-details {
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-md, 8px);
}

.tech-details summary {
  color: var(--text-secondary, #5b626c);
  cursor: pointer;
  font-size: 12px;
  padding: 8px 12px;
}

.tech-details__body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 0 12px 12px;
}

.tech-details__body p {
  color: var(--text-secondary, #5b626c);
  font-size: 11px;
  margin: 0;
  word-break: break-all;
}

.log-box {
  background: #1f2329;
  border-radius: var(--radius-md, 8px);
  color: #dbeafe;
  font-size: 11px;
  line-height: 1.5;
  max-height: 200px;
  overflow: auto;
  padding: 10px;
  white-space: pre-wrap;
}

.log-box--error {
  color: #fca5a5;
}

/* 错误 (P0-5: 人话文案) */
.error-card {
  align-items: flex-start;
  background: var(--diff-del-bg, #FFEBEE);
  border: 1px solid rgba(229, 57, 53, 0.2);
  border-radius: var(--radius-md, 8px);
  color: var(--diff-del-text, #C62828);
  display: flex;
  font-size: 12px;
  gap: 8px;
  padding: 10px 12px;
}

.error-card__icon {
  flex-shrink: 0;
  font-weight: 700;
}

.error-card p {
  margin: 0;
}

.empty-state {
  color: var(--text-muted, #9ca3af);
  margin: auto;
}

/* Spinner */
.spinner {
  animation: spin 0.6s linear infinite;
  border: 2px solid rgba(15, 158, 213, 0.25);
  border-radius: 50%;
  border-top-color: var(--brand-cyan, #0f9ed5);
  display: inline-block;
  height: 24px;
  width: 24px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
