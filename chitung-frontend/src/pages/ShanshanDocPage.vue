<script setup lang="ts">
import { computed, ref } from 'vue'
import { useDocmateSession } from '../composables/useDocmateSession'
import type { DocmateChange } from '../types/domain'

const {
  state,
  isLoaded,
  docName,
  docStats,
  pendingChanges,
  previewParagraphs,
  acceptedAppends,
  uploadDocument,
  unload,
} = useDocmateSession()

const fileInput = ref<HTMLInputElement | null>(null)
const dragOver = ref(false)

function pickFile() {
  fileInput.value?.click()
}

async function ingest(file: File) {
  await uploadDocument(file)
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
  pendingChanges.value.filter((change) => change.type === 'text_append' && change.replacement),
)

function changesForText(text: string): DocmateChange[] {
  return pendingChanges.value.filter(
    (change) => change.type !== 'text_append' && Boolean(change.target) && text.includes(change.target as string),
  )
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
          <p class="dropzone__hint">文档加载后，可在 AI 助手里用自然语言改稿。</p>
        </template>
      </div>
      <input ref="fileInput" type="file" accept=".docx" class="hidden-input" @change="onFileChange" />

      <div class="assistant-hint">
        <strong>DocMate Skill</strong>
        <p>打开赤瞳 AI，选择“文档改稿”，或直接输入“帮我润色当前文档”。审阅、重试和下载会共享当前文档会话。</p>
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
        <button class="ghost-btn" @click="unload">移除文档</button>
      </div>

      <div v-if="state.step === 'error' && state.error" class="error-card">
        <span>!</span>
        <p>{{ state.error }}</p>
      </div>
    </aside>

    <main class="sd-panel sd-panel--center">
      <div class="sd-center-head">
        <h2 class="sd-title">文档预览</h2>
        <span v-if="pendingChanges.length" class="diff-legend">
          <span class="legend legend--delete">删除</span>
          <span class="legend legend--insert">新增</span>
          待审阅 {{ pendingChanges.length }} 处
        </span>
      </div>

      <div v-if="!isLoaded && state.step !== 'loading'" class="empty-state">
        <span class="empty-state__icon">DOCX</span>
        <p>上传一份 .docx 文档后在此预览。</p>
      </div>
      <div v-else-if="state.step === 'loading'" class="empty-state">
        <span class="spinner spinner--large"></span>
        <p>正在解析文档...</p>
      </div>
      <div v-else-if="state.structure" class="doc-preview">
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
  gap: 16px;
  grid-template-columns: 280px minmax(0, 1fr);
  height: calc(100vh - 56px);
  overflow: hidden;
  padding: 16px;
}

.sd-panel {
  background: var(--bg-white);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-sm);
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  padding: 16px;
}

.sd-title {
  color: var(--text-secondary);
  font-size: 13px;
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
  color: var(--text-secondary);
  display: flex;
  font-size: 11px;
  gap: 6px;
}

.legend {
  border-radius: var(--radius-xs);
  font-size: 10px;
  padding: 1px 6px;
}

.legend--delete {
  background: var(--brand-red-light);
  color: var(--brand-red);
  text-decoration: line-through;
}

.legend--insert {
  background: #edf7e8;
  color: var(--brand-green);
}

.dropzone {
  align-items: center;
  background: var(--bg-subtle);
  border: 1.5px dashed var(--border-normal);
  border-radius: var(--radius-lg);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 6px;
  justify-content: center;
  padding: 24px 12px;
  text-align: center;
  transition: background var(--dur-fast, 120ms) var(--ease, ease), border-color var(--dur-fast, 120ms) var(--ease, ease);
}

.dropzone:hover,
.dropzone--over {
  background: var(--bg-active);
  border-color: var(--brand-cyan);
}

.dropzone--busy {
  cursor: default;
  opacity: 0.72;
}

.dropzone__icon,
.empty-state__icon {
  color: var(--brand-cyan);
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.6px;
}

.dropzone__lead {
  color: var(--text-primary);
  font-size: 13px;
  margin: 0;
}

.dropzone__hint {
  color: var(--text-secondary);
  font-size: 11px;
  margin: 0;
}

.hidden-input {
  display: none;
}

.assistant-hint {
  background: var(--bg-subtle);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  padding: 10px 12px;
}

.assistant-hint strong {
  color: var(--brand-red);
  display: block;
  font-size: 12px;
  margin-bottom: 4px;
}

.assistant-hint p {
  color: var(--text-secondary);
  font-size: 11px;
  line-height: 1.6;
  margin: 0;
}

.doc-info {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.doc-info__title {
  color: var(--text-secondary);
  font-size: 12px;
  margin: 0 0 4px;
}

.doc-info__stat {
  display: flex;
  font-size: 12px;
  gap: 8px;
  justify-content: space-between;
  padding: 3px 0;
}

.stat-label {
  color: var(--text-secondary);
  flex-shrink: 0;
}

.stat-value {
  color: var(--text-primary);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ghost-btn {
  background: var(--bg-white);
  border: 1px solid var(--border-normal);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 12px;
  padding: 7px 12px;
  width: 100%;
}

.ghost-btn:hover {
  border-color: var(--border-strong);
  color: var(--text-primary);
}

.error-card {
  align-items: flex-start;
  background: var(--brand-red-light);
  border: 1px solid rgb(231 0 18 / 18%);
  border-radius: var(--radius-md);
  color: var(--brand-red);
  display: flex;
  font-size: 13px;
  gap: 8px;
  padding: 10px 12px;
}

.error-card p {
  margin: 0;
}

.empty-state {
  align-items: center;
  color: var(--text-secondary);
  display: flex;
  flex: 1;
  flex-direction: column;
  font-size: 13px;
  gap: 12px;
  justify-content: center;
}

.doc-preview {
  flex: 1;
  overflow-y: auto;
}

.doc-para {
  border-bottom: 1px solid var(--border-light);
  display: flex;
  gap: 8px;
  padding: 6px 4px;
}

.doc-para--changed {
  background: rgb(15 158 213 / 5%);
  border-radius: var(--radius-sm);
}

.doc-para--accepted {
  background: rgb(78 167 46 / 7%);
}

.para-index {
  color: var(--text-muted);
  flex-shrink: 0;
  font-size: 11px;
  text-align: right;
  width: 22px;
}

.para-text {
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.para-text--deleted {
  color: var(--text-muted);
  font-style: italic;
  text-decoration: line-through;
}

.seg-delete {
  background: var(--brand-red-light);
  border-radius: 2px;
  color: var(--brand-red);
  padding: 0 2px;
  text-decoration: line-through;
}

.seg-insert {
  background: #edf7e8;
  border-radius: 2px;
  color: var(--brand-green);
  padding: 0 2px;
  text-decoration: none;
}

.spinner {
  animation: spin 0.6s linear infinite;
  border: 2px solid rgba(15, 158, 213, 0.25);
  border-radius: 50%;
  border-top-color: var(--brand-cyan);
  display: inline-block;
  height: 14px;
  width: 14px;
}

.spinner--large {
  border-width: 3px;
  height: 30px;
  width: 30px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
