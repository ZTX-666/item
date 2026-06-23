<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import { useDocmateSession } from '../composables/useDocmateSession'
import { openChatbotKey } from '../composables/useAppNavigation'
import type { DocmateChange } from '../types/domain'
import AuditTrail from '../components/documents/AuditTrail.vue'
import SkeletonLoader from '../components/common/SkeletonLoader.vue'

const {
  state,
  isLoaded,
  pendingCount,
  previewParagraphs,
  acceptedAppends,
  docName,
  docStats,
  uploadDocument,
  unload,
} = useDocmateSession()

const openChatbot = inject(openChatbotKey, () => {})
const fileInput = ref<HTMLInputElement | null>(null)
const dragOver = ref(false)

function pickFile() {
  fileInput.value?.click()
}

async function ingest(file: File) {
  const result = await uploadDocument(file)
  if (result.ok) openChatbot()
}

async function onFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) await ingest(file)
  target.value = ''
}

async function onDrop(event: DragEvent) {
  dragOver.value = false
  const file = event.dataTransfer?.files?.[0]
  if (file) await ingest(file)
}

interface Segment {
  kind: 'context' | 'delete' | 'insert'
  text: string
}

const appendChanges = computed(() =>
  state.workItems
    .filter((item) => item.change.type === 'text_append' && item.change.replacement)
    .map((item) => item.change),
)

function changesForText(text: string): DocmateChange[] {
  return state.workItems
    .map((item) => item.change)
    .filter((change) => change.type !== 'text_append' && Boolean(change.target) && text.includes(change.target as string))
}

function segmentsFor(text: string): Segment[] {
  const hits = changesForText(text)
    .map((change) => ({ change, at: text.indexOf(change.target as string) }))
    .filter((hit) => hit.at >= 0)
    .sort((a, b) => a.at - b.at)

  if (!hits.length) return [{ kind: 'context', text }]

  const segments: Segment[] = []
  let cursor = 0

  for (const { change, at } of hits) {
    if (at < cursor) continue
    if (at > cursor) segments.push({ kind: 'context', text: text.slice(cursor, at) })
    const target = change.target as string
    segments.push({ kind: 'delete', text: target })
    if (change.type !== 'text_delete' && change.replacement) {
      segments.push({ kind: 'insert', text: change.replacement })
    }
    cursor = at + target.length
  }

  if (cursor < text.length) segments.push({ kind: 'context', text: text.slice(cursor) })
  return segments
}

function paragraphChanged(text: string): boolean {
  return changesForText(text).length > 0
}
</script>

<template>
  <div class="shanshan-doc">
    <!-- 左栏：文档区 -->
    <aside class="sd-panel sd-panel--left">
      <h2 class="sd-title">文档</h2>

      <div
        class="dropzone"
        :class="{ 'dropzone--over': dragOver, 'dropzone--busy': state.step === 'loading' }"
        @click="pickFile"
        @dragover.prevent="dragOver = true"
        @dragleave.prevent="dragOver = false"
        @drop.prevent="onDrop"
      >
        <template v-if="state.step === 'loading'">
          <span class="spinner spinner--large"></span>
          <p>正在解析文档...</p>
        </template>
        <template v-else>
          <span class="dropzone__icon">DOCX</span>
          <p class="dropzone__lead">点击或拖拽上传 .docx 文档</p>
          <p class="dropzone__hint">支持 Word 2007+ 格式，上传后可预览和 AI 改稿</p>
        </template>
      </div>
      <input ref="fileInput" type="file" accept=".docx" class="hidden-input" @change="onFileChange" />

      <!-- 空状态引导 (P1-4) -->
      <div v-if="!isLoaded && state.step !== 'loading'" class="empty-guide">
        <h3 class="empty-guide__title">操作建议</h3>
        <ol class="empty-guide__list">
          <li>上传 .docx 文档</li>
          <li>打开右侧闪闪助手输入改稿指令</li>
          <li>在闪闪助手中逐条审阅 AI 修改建议</li>
          <li>采纳或拒绝后下载文档</li>
        </ol>
      </div>

      <div v-if="isLoaded" class="doc-info">
        <h3 class="doc-info__title">当前文档</h3>
        <div class="doc-info__stat">
          <span class="stat-label">文件名</span>
          <span class="stat-value" :title="docName">{{ docName }}</span>
        </div>
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
        <button class="primary-soft-button" @click="openChatbot">打开闪闪助手改稿</button>
        <button class="ghost-btn" @click="unload">移除文档</button>
      </div>

      <div v-if="isLoaded" class="assistant-hint">
        <strong>改稿交互已移至闪闪助手</strong>
        <p>请在右侧闪闪助手输入自然语言指令，例如“把第二段改正式”或“检查全文安全合规性”。</p>
      </div>

      <AuditTrail v-if="state.auditLog.length" :entries="state.auditLog" :max-items="6" />

      <div v-if="state.step === 'error' && state.error" class="error-card">
        <span>!</span>
        <p>{{ state.error }}</p>
      </div>
    </aside>

    <!-- 中栏：预览区 -->
    <main class="sd-panel sd-panel--center">
      <div class="sd-center-head">
        <h2 class="sd-title">文档预览</h2>
        <span v-if="pendingCount" class="diff-legend">
          <span class="legend legend--delete">删除</span>
          <span class="legend legend--insert">新增</span>
          待审阅 {{ pendingCount }} 处
        </span>
      </div>

      <!-- 空状态 (P1-4) -->
      <div v-if="!isLoaded && state.step !== 'loading'" class="empty-state">
        <span class="empty-state__icon">DOCX</span>
        <p class="empty-state__lead">上传一份 .docx 文档后在此预览</p>
        <p class="empty-state__hint">支持段落、表格、图片的完整解析</p>
        <button class="empty-state__cta" @click="pickFile">选择文档</button>
      </div>

      <!-- 骨架屏 (P1-6) -->
      <SkeletonLoader v-else-if="state.step === 'loading'" type="paragraphs" :count="5" />

      <div v-else-if="state.structure" ref="previewRef" class="doc-preview">
        <div
          v-for="(paragraph, idx) in previewParagraphs"
          :key="`${paragraph.index}-${idx}`"
          class="doc-para"
          :class="{ 'doc-para--changed': paragraphChanged(paragraph.text), 'doc-para--accepted': paragraph.accepted }"
        >
          <span class="para-index">{{ idx + 1 }}</span>
          <span v-if="paragraph.deleted" class="para-text para-text--deleted">（本段已删除）</span>
          <span v-else class="para-text">
            <template v-for="(segment, segmentIndex) in segmentsFor(paragraph.text)" :key="segmentIndex">
              <del v-if="segment.kind === 'delete'" class="seg-delete">{{ segment.text }}</del>
              <ins v-else-if="segment.kind === 'insert'" class="seg-insert">{{ segment.text }}</ins>
              <span v-else>{{ segment.text }}</span>
            </template>
          </span>
        </div>

        <div v-for="(change, index) in acceptedAppends" :key="`accepted-${index}`" class="doc-para doc-para--accepted">
          <span class="para-index">+</span>
          <span class="para-text">{{ change.replacement }}</span>
        </div>

        <div v-for="(change, index) in appendChanges" :key="`pending-${index}`" class="doc-para doc-para--changed">
          <span class="para-index">+</span>
          <span class="para-text"><ins class="seg-insert">{{ change.replacement }}</ins></span>
        </div>
      </div>

    </main>
  </div>
</template>

<style scoped>
.shanshan-doc {
  display: grid;
  gap: 12px;
  grid-template-columns: 300px minmax(0, 1fr);
  height: calc(100vh - 56px);
  overflow: hidden;
  padding: 12px;
}

.sd-panel {
  background: var(--bg-white, #fff);
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-xl, 16px);
  box-shadow: var(--shadow-sm, 0 1px 3px rgba(0,0,0,0.06));
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow-y: auto;
  padding: 14px;
}

.sd-title {
  color: var(--text-secondary, #5b626c);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.4px;
  margin: 0;
  text-transform: uppercase;
}

.sd-center-head {
  align-items: center;
  display: flex;
  gap: 12px;
  justify-content: space-between;
}

.diff-legend {
  align-items: center;
  color: var(--text-secondary, #5b626c);
  display: flex;
  font-size: 11px;
  gap: 6px;
}

.legend {
  border-radius: var(--radius-xs, 3px);
  font-size: 10px;
  padding: 1px 6px;
}

.legend--delete {
  background: var(--diff-del-bg, #FFEBEE);
  color: var(--diff-del-text, #C62828);
  text-decoration: line-through;
}

.legend--insert {
  background: var(--diff-add-bg, #E8F5E9);
  color: var(--diff-add-text, #2E7D32);
}

/* 上传区 */
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
  padding: 20px 12px;
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

.dropzone__icon,
.empty-state__icon {
  color: var(--brand-cyan, #0f9ed5);
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.6px;
}

.dropzone__lead {
  color: var(--text-primary, #1a1d23);
  font-size: 12px;
  margin: 0;
}

.dropzone__hint {
  color: var(--text-secondary, #5b626c);
  font-size: 11px;
  margin: 0;
}

.hidden-input {
  display: none;
}

/* 空状态引导 */
.empty-guide {
  background: var(--bg-subtle, #f5f7fa);
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-md, 8px);
  padding: 12px;
}

.empty-guide__title {
  color: var(--text-secondary, #5b626c);
  font-size: 12px;
  margin: 0 0 8px;
}

.empty-guide__list {
  color: var(--text-secondary, #5b626c);
  font-size: 12px;
  line-height: 1.8;
  margin: 0;
  padding-left: 18px;
}

/* 文档信息 */
.doc-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.doc-info__title {
  color: var(--text-secondary, #5b626c);
  font-size: 12px;
  margin: 0 0 4px;
}

.doc-info__stat {
  display: flex;
  font-size: 12px;
  gap: 8px;
  justify-content: space-between;
  padding: 2px 0;
}

.stat-label {
  color: var(--text-secondary, #5b626c);
  flex-shrink: 0;
}

.stat-value {
  color: var(--text-primary, #1a1d23);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ghost-btn {
  background: var(--bg-white, #fff);
  border: 1px solid var(--border-normal, #d0d5dd);
  border-radius: var(--radius-md, 8px);
  color: var(--text-secondary, #5b626c);
  cursor: pointer;
  font-size: 12px;
  margin-top: 6px;
  padding: 7px 12px;
  width: 100%;
}

.ghost-btn:hover {
  border-color: var(--brand-cyan, #0f9ed5);
  color: var(--brand-cyan, #0f9ed5);
}

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

.error-card p {
  margin: 0;
}

/* 空状态 */
.empty-state {
  align-items: center;
  color: var(--text-secondary, #5b626c);
  display: flex;
  flex: 1;
  flex-direction: column;
  font-size: 13px;
  gap: 8px;
  justify-content: center;
}

.empty-state__lead {
  color: var(--text-primary, #1a1d23);
  font-size: 14px;
  font-weight: 600;
  margin: 0;
}

.empty-state__hint {
  color: var(--text-secondary, #5b626c);
  font-size: 12px;
  margin: 0;
}

.empty-state__cta {
  background: var(--brand-cyan, #0f9ed5);
  border: none;
  border-radius: var(--radius-md, 8px);
  color: var(--text-white, #fff);
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  margin-top: 8px;
  padding: 8px 20px;
}

/* 文档预览 */
.doc-preview {
  flex: 1;
  overflow-y: auto;
}

.doc-para {
  border-bottom: 1px solid var(--border-light, #e8eaef);
  display: flex;
  gap: 8px;
  padding: 6px 4px;
}

.doc-para--changed {
  background: rgba(15, 158, 213, 0.04);
  border-radius: var(--radius-sm, 4px);
}

.doc-para--accepted {
  background: rgba(67, 160, 71, 0.06);
}

.para-index {
  color: var(--text-muted, #9ca3af);
  flex-shrink: 0;
  font-size: 11px;
  text-align: right;
  width: 22px;
}

.para-text {
  color: var(--text-primary, #1a1d23);
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.para-text--deleted {
  color: var(--text-muted, #9ca3af);
  font-style: italic;
  text-decoration: line-through;
}

.seg-delete {
  background: var(--diff-del-bg, #FFEBEE);
  border-radius: 2px;
  color: var(--diff-del-text, #C62828);
  padding: 0 2px;
  text-decoration: line-through;
}

.seg-insert {
  background: var(--diff-add-bg, #E8F5E9);
  border-radius: 2px;
  color: var(--diff-add-text, #2E7D32);
  padding: 0 2px;
  text-decoration: none;
}

/* Ask AI 浮动工具栏 */
.ask-ai-bar {
  align-items: center;
  background: var(--bg-white, #fff);
  border: 1px solid var(--border-normal, #d0d5dd);
  border-radius: var(--radius-md, 8px);
  box-shadow: var(--shadow-sm, 0 2px 8px rgba(0,0,0,0.12));
  display: flex;
  gap: 8px;
  padding: 6px 10px;
  position: sticky;
  bottom: 12px;
  z-index: 10;
}

.ask-ai-bar__selection {
  color: var(--text-secondary, #5b626c);
  flex: 1;
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ask-ai-bar__actions {
  display: flex;
  gap: 4px;
}

.ask-ai-btn {
  background: var(--bg-subtle, #f5f7fa);
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-sm, 4px);
  color: var(--text-secondary, #5b626c);
  cursor: pointer;
  font-size: 11px;
  padding: 4px 10px;
}

.ask-ai-btn--primary {
  background: var(--ai-badge, #7C4DFF);
  border-color: var(--ai-badge, #7C4DFF);
  color: var(--text-white, #fff);
  font-weight: 600;
}

/* Ask AI 面板 */
.ask-ai-panel {
  background: var(--bg-white, #fff);
  border: 1px solid var(--border-normal, #d0d5dd);
  border-radius: var(--radius-md, 8px);
  box-shadow: var(--shadow-sm, 0 4px 12px rgba(0,0,0,0.1));
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  position: sticky;
  bottom: 12px;
  z-index: 20;
}

.ask-ai-panel__head {
  align-items: center;
  display: flex;
  justify-content: space-between;
}

.ask-ai-panel__head strong {
  color: var(--ai-badge, #7C4DFF);
  font-size: 13px;
}

.ask-ai-panel__close {
  background: none;
  border: none;
  color: var(--text-muted, #9ca3af);
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
  padding: 0;
}

.ask-ai-panel__context {
  color: var(--text-secondary, #5b626c);
  font-size: 11px;
  line-height: 1.5;
  margin: 0;
}

.ask-ai-panel__quick {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.quick-instruction {
  background: rgba(124, 77, 255, 0.08);
  border: 1px solid rgba(124, 77, 255, 0.2);
  border-radius: 999px;
  color: var(--ai-badge, #7C4DFF);
  cursor: pointer;
  font-size: 11px;
  padding: 4px 10px;
}

.ask-ai-panel__input {
  display: flex;
  gap: 6px;
}

.ask-ai-panel__input input {
  background: var(--bg-subtle, #f5f7fa);
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-sm, 4px);
  color: var(--text-primary, #1a1d23);
  flex: 1;
  font-size: 12px;
  padding: 6px 8px;
}

.primary-soft-button {
  background: var(--ai-badge, #7C4DFF);
  border: none;
  border-radius: var(--radius-sm, 4px);
  color: var(--text-white, #fff);
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  padding: 6px 14px;
}

.primary-soft-button:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

/* 右栏：改稿区 */
.instruction-box {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.instruction-input {
  background: var(--bg-subtle, #f5f7fa);
  border: 1px solid var(--border-normal, #d0d5dd);
  border-radius: var(--radius-md, 8px);
  color: var(--text-primary, #1a1d23);
  font-family: inherit;
  font-size: 13px;
  line-height: 1.5;
  padding: 8px 10px;
  resize: vertical;
}

.instruction-input:focus {
  border-color: var(--brand-cyan, #0f9ed5);
  outline: none;
}

.instruction-input:disabled {
  opacity: 0.5;
}

.generate-btn {
  align-items: center;
  background: var(--brand-cyan, #0f9ed5);
  border: none;
  border-radius: var(--radius-md, 8px);
  color: var(--text-white, #fff);
  cursor: pointer;
  display: flex;
  font-size: 13px;
  font-weight: 600;
  gap: 6px;
  justify-content: center;
  padding: 9px 14px;
}

.generate-btn:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

/* 审阅状态 */
.review-status {
  align-items: center;
  display: flex;
  font-size: 12px;
  gap: 6px;
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

/* 批量操作 */
.batch-bar {
  background: var(--bg-subtle, #f5f7fa);
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-md, 8px);
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px 10px;
}

.batch-stats {
  display: flex;
  font-size: 11px;
  gap: 10px;
}

.batch-stats--high {
  color: var(--risk-high, #E53935);
  font-weight: 600;
}

.batch-actions {
  display: flex;
  gap: 4px;
}

.batch-btn {
  background: var(--bg-white, #fff);
  border: 1px solid var(--border-normal, #d0d5dd);
  border-radius: var(--radius-sm, 4px);
  color: var(--text-secondary, #5b626c);
  cursor: pointer;
  flex: 1;
  font-size: 10px;
  padding: 4px 6px;
}

.batch-btn:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

.batch-btn--primary {
  background: var(--brand-cyan, #0f9ed5);
  border-color: var(--brand-cyan, #0f9ed5);
  color: var(--text-white, #fff);
  font-weight: 600;
}

.batch-select {
  display: flex;
  gap: 4px;
}

.mini-btn {
  background: var(--bg-white, #fff);
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-sm, 4px);
  color: var(--text-secondary, #5b626c);
  cursor: pointer;
  flex: 1;
  font-size: 10px;
  padding: 3px 6px;
}

.mini-btn:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

/* 筛选标签 */
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
  flex: 1;
  font-size: 10px;
  padding: 3px 4px;
}

.filter-tab--active {
  background: var(--brand-cyan, #0f9ed5);
  border-color: var(--brand-cyan, #0f9ed5);
  color: var(--text-white, #fff);
}

/* 建议列表 */
.suggestion-list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  overflow-y: auto;
}

/* 底部操作 */
.worklist-actions {
  display: flex;
  gap: 6px;
}

.act-btn {
  border: none;
  border-radius: var(--radius-sm, 4px);
  cursor: pointer;
  flex: 1;
  font-size: 11px;
  font-weight: 600;
  padding: 7px 4px;
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
  color: var(--text-secondary, #5b626c);
}

/* 空状态 */
.review-empty {
  align-items: center;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 24px 12px;
  text-align: center;
}

.review-empty__lead {
  color: var(--text-primary, #1a1d23);
  font-size: 13px;
  font-weight: 600;
  margin: 0;
}

.review-empty__hint {
  color: var(--text-secondary, #5b626c);
  font-size: 11px;
  margin: 0;
}

/* Spinner */
.spinner {
  animation: spin 0.6s linear infinite;
  border: 2px solid rgba(15, 158, 213, 0.25);
  border-radius: 50%;
  border-top-color: var(--brand-cyan, #0f9ed5);
  display: inline-block;
  height: 14px;
  width: 14px;
}

.spinner--large {
  border-width: 3px;
  height: 30px;
  width: 30px;
}

.spinner--small {
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: currentColor;
  height: 12px;
  width: 12px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* 过渡动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 200ms ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 200ms ease;
}

.slide-up-enter-from,
.slide-up-leave-to {
  opacity: 0;
  transform: translateY(10px);
}
</style>
