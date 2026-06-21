<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import { useDocmateSession } from '../composables/useDocmateSession'
import { openChatbotKey } from '../composables/useAppNavigation'
import type { DocmateChange } from '../types/domain'

const { state, isLoaded, docName, docStats, pendingChanges, previewParagraphs, acceptedAppends, uploadDocument, unload } =
  useDocmateSession()
const openChatbot = inject(openChatbotKey)

const fileInput = ref<HTMLInputElement | null>(null)
const dragOver = ref(false)

function pickFile() {
  fileInput.value?.click()
}

async function ingest(file: File) {
  const result = await uploadDocument(file)
  if (result.ok) openChatbot?.()
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

// ── inline diff highlighting in the preview ──
interface Seg {
  kind: 'ctx' | 'del' | 'ins'
  text: string
}

const appendChanges = computed(() =>
  pendingChanges.value.filter((c) => c.type === 'text_append' && c.replacement),
)

// Match purely by target text within the paragraph. Paragraph indices from the
// backend are original-docx indices (with gaps for blank lines) and don't line
// up with the compact preview list, so we rely on the verbatim target instead.
// Supports MULTIPLE changes within the same paragraph.
function changesForText(text: string): DocmateChange[] {
  return pendingChanges.value.filter(
    (c) => c.type !== 'text_append' && !!c.target && text.includes(c.target),
  )
}

function segmentsFor(text: string): Seg[] {
  const applicable = changesForText(text)
  if (!applicable.length) return [{ kind: 'ctx', text }]

  const hits = applicable
    .map((c) => ({ change: c, at: text.indexOf(c.target as string) }))
    .filter((h) => h.at >= 0)
    .sort((a, b) => a.at - b.at)

  const segs: Seg[] = []
  let cursor = 0
  for (const { change, at } of hits) {
    if (at < cursor) continue // overlapping change already covered — skip
    if (at > cursor) segs.push({ kind: 'ctx', text: text.slice(cursor, at) })
    const target = change.target as string
    segs.push({ kind: 'del', text: target })
    if (change.type !== 'text_delete' && change.replacement) {
      segs.push({ kind: 'ins', text: change.replacement })
    }
    cursor = at + target.length
  }
  if (cursor < text.length) segs.push({ kind: 'ctx', text: text.slice(cursor) })
  return segs
}

function paragraphChanged(text: string): boolean {
  return changesForText(text).length > 0
}
</script>

<template>
  <div class="shanshan-doc">
    <!-- Left: upload + doc info -->
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
          <span class="spinner spinner--lg"></span>
          <p>正在解析文档...</p>
        </template>
        <template v-else>
          <span class="dropzone__icon">📄⬆️</span>
          <p class="dropzone__lead">点击或拖拽上传 .docx 文档</p>
          <p class="dropzone__hint">无需文件路径，选好文件即可开始</p>
        </template>
      </div>
      <input ref="fileInput" type="file" accept=".docx" class="hidden-input" @change="onFileChange" />

      <p class="hint">上传后，在<strong>左下角「🤖 赤瞳 AI」</strong>助手中用自然语言改稿。</p>

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
        <span>⚠️</span>
        <p>{{ state.error }}</p>
      </div>
    </aside>

    <!-- Center: document preview with inline diff highlights -->
    <main class="sd-panel sd-panel--center">
      <div class="sd-center-head">
        <h2 class="sd-title">文档预览</h2>
        <span v-if="pendingChanges.length" class="diff-legend">
          <span class="legend legend--del">删除</span>
          <span class="legend legend--ins">新增</span>
          待审阅 {{ pendingChanges.length }} 处
        </span>
      </div>

      <div v-if="!isLoaded && state.step !== 'loading'" class="empty-state">
        <span class="empty-state__icon">📄</span>
        <p>上传一份 .docx 文档后在此预览</p>
      </div>
      <div v-else-if="state.step === 'loading'" class="empty-state">
        <span class="spinner spinner--lg"></span>
        <p>正在解析文档...</p>
      </div>
      <div v-else-if="state.structure" class="doc-preview">
        <div
          v-for="(p, idx) in previewParagraphs"
          :key="idx"
          class="doc-para"
          :class="{ 'doc-para--changed': paragraphChanged(p.text) }"
        >
          <span class="para-index">{{ idx + 1 }}</span>
          <span v-if="p.deleted" class="para-text para-text--deleted">（本段已删除）</span>
          <span v-else class="para-text">
            <template v-for="(seg, i) in segmentsFor(p.text)" :key="i">
              <del v-if="seg.kind === 'del'" class="seg-del">{{ seg.text }}</del>
              <ins v-else-if="seg.kind === 'ins'" class="seg-ins">{{ seg.text }}</ins>
              <span v-else>{{ seg.text }}</span>
            </template>
          </span>
        </div>

        <!-- accepted appends: now part of the document, shown as plain text -->
        <div v-for="(c, i) in acceptedAppends" :key="`acc-${i}`" class="doc-para">
          <span class="para-index">·</span>
          <span class="para-text">{{ c.replacement }}</span>
        </div>

        <!-- pending appends shown as proposed green lines -->
        <div v-for="(c, i) in appendChanges" :key="`app-${i}`" class="doc-para doc-para--changed">
          <span class="para-index">＋</span>
          <span class="para-text"><ins class="seg-ins">{{ c.replacement }}</ins></span>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.shanshan-doc {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 16px;
  height: calc(100vh - 56px);
  padding: 16px;
  overflow: hidden;
}

.sd-panel {
  background: var(--bg-white);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-sm);
  padding: 16px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sd-title {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-secondary);
  letter-spacing: 0.4px;
  text-transform: uppercase;
  margin: 0;
}

.sd-center-head {
  align-items: center;
  display: flex;
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

.legend--del {
  background: var(--brand-red-light);
  color: var(--brand-red);
  text-decoration: line-through;
}

.legend--ins {
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
  transition: all 0.15s;
}

.dropzone:hover {
  border-color: var(--brand-cyan);
  background: var(--bg-active);
}

.dropzone--over {
  border-color: var(--brand-cyan);
  background: var(--bg-active);
}

.dropzone--busy {
  cursor: default;
  opacity: 0.7;
}

.dropzone__icon {
  font-size: 28px;
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

.hint {
  color: var(--text-secondary);
  font-size: 11px;
  line-height: 1.6;
  margin: 0;
}

.hint strong {
  color: var(--brand-red);
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

.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(15, 158, 213, 0.25);
  border-top-color: var(--brand-cyan);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  display: inline-block;
}

.spinner--lg {
  width: 30px;
  height: 30px;
  border-width: 3px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.doc-info {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.doc-info__title {
  color: var(--text-secondary);
  font-size: 12px;
  margin: 0 0 4px 0;
}

.doc-info__stat {
  display: flex;
  gap: 8px;
  justify-content: space-between;
  font-size: 12px;
  padding: 3px 0;
}

.stat-label { color: var(--text-secondary); flex-shrink: 0; }
.stat-value {
  color: var(--text-primary);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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

.error-card p { margin: 0; }

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

.empty-state__icon { font-size: 32px; }

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

.para-text--deleted {
  color: var(--text-muted);
  font-style: italic;
  text-decoration: line-through;
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

.seg-del {
  background: var(--brand-red-light);
  color: var(--brand-red);
  border-radius: 2px;
  padding: 0 2px;
  text-decoration: line-through;
}

.seg-ins {
  background: #edf7e8;
  color: var(--brand-green);
  border-radius: 2px;
  padding: 0 2px;
  text-decoration: none;
}
</style>
