<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import SkeletonLoader from '../components/common/SkeletonLoader.vue'
import {
  askRag,
  deleteRagDocument,
  getRagStats,
  listRagDocuments,
  queryRag,
  uploadRagDocument,
} from '../services/chitungApi'
import type { RagAskResponse, RagDocument, RagQueryMatch, RagStats } from '../types/domain'

const documents = ref<RagDocument[]>([])
const results = ref<RagQueryMatch[]>([])
const stats = ref<RagStats | null>(null)
const queryText = ref('')
const isDragging = ref(false)
const isUploading = ref(false)
const isLoading = ref(true)
const isSearching = ref(false)
const isAnswering = ref(false)
const deletingId = ref('')
const error = ref('')
const lastMessage = ref('')
const ragAnswer = ref<RagAskResponse | null>(null)
const hasRawSearch = ref(false)
const uploadProgress = ref({ current: 0, total: 0, name: '' })
let refreshSeq = 0

const isFeedMode = computed(() => location.hash.includes('/feed'))
const activeCollection = computed(() => (isFeedMode.value ? 'feed' : 'safety'))
const mode = computed(() => (isFeedMode.value ? '舆情规范知识库' : '耀耀知识'))
const modeDescription = computed(() =>
  isFeedMode.value
    ? '上传舆情规范、外部讯息资料和白名单来源说明，使用本地 ChromaDB 做语义检索。'
    : '《中建香港安全管理辦法彙編》(202605+版) 已作为内置制度入库，也可继续上传项目制度、规范、报告，AI 会基于知识库回答。',
)

const promptSuggestions = computed(() =>
  isFeedMode.value
    ? ['舆情白名单来源如何定义？', '外部讯息采集规范有哪些要求？', '风险卡片分级标准是什么？']
    : [
        '临边作业和高处作业有哪些要求？',
        '机械作业半径和警戒线如何设置？',
        'PPE 个人防护用品管理要求是什么？',
        '隐患整改闭环流程是怎样的？',
      ],
)

const sortedDocuments = computed(() => {
  const items = [...documents.value]
  return items.sort((a, b) => {
    const aBuiltin = isBuiltin(a) ? 1 : 0
    const bBuiltin = isBuiltin(b) ? 1 : 0
    if (aBuiltin !== bBuiltin) return bBuiltin - aBuiltin
    return String(b.created_at || '').localeCompare(String(a.created_at || ''))
  })
})

const answerReferences = computed(() => {
  const answer = ragAnswer.value
  if (!answer) return []
  const matches = answer.matches ?? []
  const citations = answer.citations ?? []
  const selected = citations
    .map((citation) =>
      matches.find(
        (match) =>
          match.source_file_name === citation.source_file_name && match.chunk_index === citation.chunk_index,
      ),
    )
    .filter((item): item is RagQueryMatch => Boolean(item))
  const fallback = selected.length ? selected : matches.slice(0, 5)
  const seen = new Set<string>()
  return fallback
    .filter((item) => {
      const key = `${item.source_file_name}-${item.chunk_index}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
    .slice(0, 5)
})

const isQueryBusy = computed(() => isSearching.value || isAnswering.value)

async function refresh() {
  const seq = ++refreshSeq
  error.value = ''
  if (!documents.value.length) isLoading.value = true
  try {
    const [docItems, statResult] = await Promise.all([
      listRagDocuments(activeCollection.value),
      getRagStats(activeCollection.value),
    ])
    if (seq !== refreshSeq) return
    documents.value = docItems
    stats.value = statResult
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    if (seq === refreshSeq) isLoading.value = false
  }
}

async function uploadFiles(files: FileList | File[]) {
  const accepted = Array.from(files).filter((file) => /\.(pdf|docx|txt|md|markdown|html?)$/i.test(file.name))
  if (!accepted.length) {
    error.value = '请选择 PDF、Word、TXT、Markdown 或 HTML 文件。'
    return
  }
  isUploading.value = true
  error.value = ''
  lastMessage.value = ''
  uploadProgress.value = { current: 0, total: accepted.length, name: '' }
  try {
    let totalChunks = 0
    for (let index = 0; index < accepted.length; index += 1) {
      const file = accepted[index]
      uploadProgress.value = { current: index + 1, total: accepted.length, name: file.name }
      const result = await uploadRagDocument(file, activeCollection.value)
      totalChunks += result.chunk_count
      upsertUploadedDocument({
        doc_id: result.doc_id,
        file_name: result.file_name,
        file_type: result.file_type || file.name.split('.').pop() || 'file',
        chunk_count: result.chunk_count,
        collection: result.collection || activeCollection.value,
        created_at: result.created_at || new Date().toISOString(),
      })
    }
    lastMessage.value = `已上传 ${accepted.length} 个文件，新增 ${totalChunks} 个分块。`
    await refresh()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    isUploading.value = false
    isDragging.value = false
    uploadProgress.value = { current: 0, total: 0, name: '' }
  }
}

async function handleInput(event: Event) {
  const input = event.target as HTMLInputElement
  if (input.files) await uploadFiles(input.files)
  input.value = ''
}

async function handleDrop(event: DragEvent) {
  event.preventDefault()
  isDragging.value = false
  if (event.dataTransfer?.files) await uploadFiles(event.dataTransfer.files)
}

async function removeDocument(docId: string) {
  deletingId.value = docId
  error.value = ''
  try {
    await deleteRagDocument(docId)
    documents.value = documents.value.filter((item) => item.doc_id !== docId)
    await refresh()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    deletingId.value = ''
  }
}

async function search() {
  const value = queryText.value.trim()
  if (!value || isSearching.value) return
  isSearching.value = true
  hasRawSearch.value = true
  error.value = ''
  ragAnswer.value = null
  results.value = []
  try {
    results.value = await queryRag({
      query: value,
      topK: 5,
      collection: activeCollection.value,
    })
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    isSearching.value = false
  }
}

async function answerQuestion() {
  const value = queryText.value.trim()
  if (!value || isAnswering.value) return
  isAnswering.value = true
  error.value = ''
  ragAnswer.value = null
  results.value = []
  hasRawSearch.value = false
  try {
    const answer = await askRag({
      query: value,
      topK: 5,
      collection: activeCollection.value,
    })
    ragAnswer.value = answer
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    isAnswering.value = false
  }
}

function applyPrompt(prompt: string) {
  queryText.value = prompt
}

function handleQueryKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter' || (!event.ctrlKey && !event.metaKey)) return
  event.preventDefault()
  answerQuestion()
}

function formatDate(value: string) {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

function isBuiltin(doc: RagDocument) {
  return doc.doc_id.startsWith('builtin-') || doc.file_type === 'builtin'
}

function canDeleteDocument(doc: RagDocument) {
  return !isBuiltin(doc)
}

function fileTypeLabel(doc: RagDocument) {
  if (isBuiltin(doc)) return '内置制度'
  return (doc.file_type || 'file').toUpperCase()
}

function upsertUploadedDocument(doc: RagDocument) {
  const index = documents.value.findIndex((item) => item.doc_id === doc.doc_id)
  if (index >= 0) documents.value.splice(index, 1, doc)
  else documents.value.unshift(doc)
}

onMounted(refresh)
</script>

<template>
  <main class="workbench rag-page">
    <section class="hero-panel">
      <div>
        <p class="eyebrow">Yaoyao Knowledge</p>
        <h1>{{ mode }}</h1>
        <p>{{ modeDescription }}</p>
      </div>
      <button class="primary-soft-button" :disabled="isLoading" @click="refresh">
        {{ isLoading ? '加载中...' : '刷新' }}
      </button>
    </section>

    <section class="rag-stats">
      <template v-if="isLoading && !stats">
        <article v-for="i in 3" :key="i" class="status-card status-card--skeleton">
          <div class="rag-stat-skeleton">
            <div class="rag-stat-skeleton__line rag-stat-skeleton__line--short" />
            <div class="rag-stat-skeleton__line rag-stat-skeleton__line--value" />
            <div class="rag-stat-skeleton__line rag-stat-skeleton__line--medium" />
          </div>
        </article>
      </template>
      <template v-else>
        <article class="status-card status-card--blue">
          <span class="status-card__label">文档数</span>
          <div class="status-card__value">{{ stats?.document_count ?? 0 }}</div>
          <span class="status-card__helper">已入库文件</span>
        </article>
        <article class="status-card status-card--green">
          <span class="status-card__label">分块数</span>
          <div class="status-card__value">{{ stats?.chunk_count ?? 0 }}</div>
          <span class="status-card__helper">可检索文本片段</span>
        </article>
        <article class="status-card status-card--orange">
          <span class="status-card__label">向量数</span>
          <div class="status-card__value">{{ stats?.vector_count ?? 0 }}</div>
          <span class="status-card__helper">ChromaDB 本地向量</span>
        </article>
      </template>
    </section>

    <section class="panel rag-upload-panel">
      <div class="panel__header">
        <div>
          <h2>上传资料</h2>
          <p>支持 PDF、Word、TXT、Markdown、HTML。上传后自动解析、分块和向量化。</p>
        </div>
      </div>
      <label
        class="rag-dropzone"
        :class="{
          'rag-dropzone--active': isDragging,
          'rag-dropzone--uploading': isUploading,
        }"
        @dragover.prevent="isDragging = true"
        @dragleave.prevent="isDragging = false"
        @drop="handleDrop"
      >
        <input type="file" multiple accept=".pdf,.docx,.txt,.md,.markdown,.html,.htm" @change="handleInput" />
        <div class="rag-dropzone__content">
          <span class="rag-dropzone__icon" aria-hidden="true">{{ isUploading ? '⏳' : '📄' }}</span>
          <strong v-if="isUploading">
            正在上传 {{ uploadProgress.current }}/{{ uploadProgress.total }}
            <template v-if="uploadProgress.name"> · {{ uploadProgress.name }}</template>
          </strong>
          <strong v-else>拖拽文件到这里，或点击选择文件</strong>
          <span>支持多文件批量上传</span>
        </div>
        <div v-if="isUploading" class="rag-dropzone__progress">
          <div
            class="rag-dropzone__progress-bar"
            :style="{ width: `${(uploadProgress.current / Math.max(uploadProgress.total, 1)) * 100}%` }"
          />
        </div>
      </label>
      <Transition name="rag-toast">
        <p v-if="lastMessage" class="rag-success">{{ lastMessage }}</p>
      </Transition>
      <Transition name="rag-toast">
        <p v-if="error" class="knowledge-error">{{ error }}</p>
      </Transition>
    </section>

    <section class="workbench-grid rag-grid">
      <section class="panel rag-doc-panel">
        <div class="panel__header">
          <div>
            <h2>已上传文档</h2>
            <p>{{ documents.length }} 个文件 · 内置制度置顶</p>
          </div>
        </div>
        <SkeletonLoader v-if="isLoading && !documents.length" type="cards" :count="4" />
        <TransitionGroup v-else name="rag-list" tag="div" class="rag-document-list">
          <article
            v-for="doc in sortedDocuments"
            :key="doc.doc_id"
            class="rag-document-row"
            :class="{ 'rag-document-row--builtin': isBuiltin(doc) }"
          >
            <div class="rag-document-row__main">
              <div class="rag-document-row__title">
                <strong :title="doc.file_name">{{ doc.file_name }}</strong>
                <span v-if="isBuiltin(doc)" class="rag-badge rag-badge--builtin">内置</span>
              </div>
              <p>
                <span class="rag-doc-chip">{{ fileTypeLabel(doc) }}</span>
                {{ doc.chunk_count }} 个分块 · {{ formatDate(doc.created_at) }}
              </p>
            </div>
            <button
              v-if="canDeleteDocument(doc)"
              class="mini-button rag-delete-btn"
              :disabled="deletingId === doc.doc_id"
              @click="removeDocument(doc.doc_id)"
            >
              {{ deletingId === doc.doc_id ? '删除中...' : '删除' }}
            </button>
            <span v-else class="rag-badge rag-badge--locked">不可删除</span>
          </article>
        </TransitionGroup>
        <p v-if="!isLoading && !documents.length" class="smart-form-empty">暂无文档。上传制度文件后会显示在这里。</p>
      </section>

      <section class="panel rag-qa-panel">
        <div class="panel__header">
          <div>
            <h2>知识库问答</h2>
            <p>基于内置安全管理辦法彙編和已上传资料回答，并展示引用片段。</p>
          </div>
        </div>

        <div class="rag-prompts">
          <button
            v-for="prompt in promptSuggestions"
            :key="prompt"
            class="rag-prompt-chip"
            :disabled="isQueryBusy"
            @click="applyPrompt(prompt)"
          >
            {{ prompt }}
          </button>
        </div>

        <div class="knowledge-box" :class="{ 'knowledge-box--busy': isQueryBusy }">
          <textarea
            v-model="queryText"
            rows="4"
            placeholder="例如：临边作业、机械作业半径、PPE 和整改闭环要求是什么？"
            @keydown="handleQueryKeydown"
          />
          <div class="knowledge-actions">
            <button class="primary-soft-button" :disabled="isAnswering || !queryText.trim()" @click="answerQuestion">
              <span v-if="isAnswering" class="rag-spinner rag-spinner--primary" aria-hidden="true" />
              {{ isAnswering ? '回答中...' : '生成回答' }}
            </button>
            <button class="secondary-soft-button" :disabled="isSearching || !queryText.trim()" @click="search">
              <span v-if="isSearching" class="rag-spinner rag-spinner--muted" aria-hidden="true" />
              {{ isSearching ? '检索中...' : '仅检索原文' }}
            </button>
          </div>
          <p class="knowledge-hint">按 Ctrl+Enter 快速生成回答</p>
        </div>

        <Transition name="rag-fade-up">
          <section v-if="isAnswering" class="rag-answer rag-answer--loading">
            <div class="rag-answer__header">
              <strong>正在生成回答</strong>
              <span class="rag-spinner" aria-hidden="true" />
            </div>
            <SkeletonLoader type="paragraphs" :count="3" />
          </section>
        </Transition>

        <Transition name="rag-fade-up">
          <section v-if="ragAnswer && !isAnswering" class="rag-answer">
            <div class="rag-answer__header">
              <strong>知识库回答</strong>
              <span>{{ ragAnswer.citations.length }} 个引用</span>
            </div>
            <p class="rag-answer__body">{{ ragAnswer.answer }}</p>
            <div v-if="answerReferences.length" class="rag-answer__references">
              <details
                v-for="reference in answerReferences"
                :key="`${reference.source_file_name}-${reference.chunk_index}`"
                class="rag-reference"
              >
                <summary>
                  <strong>{{ reference.source_file_name }}</strong>
                  <span>chunk {{ reference.chunk_index }}</span>
                </summary>
                <p>{{ reference.display_text || reference.text }}</p>
              </details>
            </div>
            <p v-if="ragAnswer.llm_error" class="knowledge-error">{{ ragAnswer.llm_error }}</p>
          </section>
        </Transition>

        <Transition name="rag-fade-up">
          <details v-if="results.length && !isAnswering" class="rag-raw-results" open>
            <summary>原文检索结果（{{ results.length }}）</summary>
            <div class="rag-results">
              <article
                v-for="(item, index) in results"
                :key="`${item.doc_id}-${item.chunk_index}-${index}`"
                class="rag-result-card"
                :class="{ 'rag-result-card--garbled': item.text_quality === 'garbled' }"
              >
                <div class="rag-result-card__meta">
                  <strong>{{ item.source_file_name || '未知来源' }}</strong>
                  <span>chunk {{ item.chunk_index }}</span>
                </div>
                <p>{{ item.display_text || item.text }}</p>
                <small v-if="item.text_quality === 'garbled'">原始 PDF 片段解析质量较低，未直接展示乱码。</small>
              </article>
            </div>
          </details>
        </Transition>

        <p v-if="hasRawSearch && !results.length && !isSearching" class="smart-form-empty">暂无原文检索结果。</p>
      </section>
    </section>
  </main>
</template>

<style scoped>
.rag-page {
  --rag-ease: cubic-bezier(0.16, 1, 0.3, 1);
}

.rag-stats {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-bottom: 16px;
}

.status-card--skeleton {
  pointer-events: none;
}

.rag-stat-skeleton {
  display: grid;
  gap: 8px;
}

.rag-stat-skeleton__line {
  animation: rag-shimmer 1.4s ease-in-out infinite;
  background: linear-gradient(90deg, #f0f2f5 25%, #e4e8ee 50%, #f0f2f5 75%);
  background-size: 200% 100%;
  border-radius: 6px;
  height: 12px;
}

.rag-stat-skeleton__line--short {
  width: 42%;
}

.rag-stat-skeleton__line--value {
  height: 28px;
  width: 36%;
}

.rag-stat-skeleton__line--medium {
  width: 58%;
}

@keyframes rag-shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

.rag-dropzone {
  background: linear-gradient(135deg, #fbfcfe 0%, #f4f8fc 100%);
  border: 1.5px dashed rgb(15 158 213 / 35%);
  border-radius: 14px;
  color: var(--text-primary);
  cursor: pointer;
  display: block;
  overflow: hidden;
  position: relative;
  transition:
    border-color 180ms var(--rag-ease),
    box-shadow 180ms var(--rag-ease),
    transform 180ms var(--rag-ease);
}

.rag-dropzone input {
  display: none;
}

.rag-dropzone__content {
  align-items: center;
  display: flex;
  flex-direction: column;
  gap: 6px;
  justify-content: center;
  min-height: 140px;
  padding: 24px;
  text-align: center;
}

.rag-dropzone__icon {
  font-size: 28px;
  line-height: 1;
}

.rag-dropzone__content strong {
  font-size: 15px;
}

.rag-dropzone__content span:last-child {
  color: var(--text-secondary);
  font-size: 13px;
}

.rag-dropzone:hover {
  border-color: rgb(15 158 213 / 55%);
  box-shadow: 0 8px 24px rgb(15 158 213 / 8%);
  transform: translateY(-1px);
}

.rag-dropzone--active {
  border-color: var(--brand-cyan);
  box-shadow: 0 0 0 4px rgb(15 158 213 / 12%);
  transform: translateY(-1px);
}

.rag-dropzone--uploading {
  cursor: wait;
  pointer-events: none;
}

.rag-dropzone__progress {
  background: rgb(15 158 213 / 10%);
  height: 4px;
}

.rag-dropzone__progress-bar {
  background: linear-gradient(90deg, var(--brand-cyan), #38bdf8);
  height: 100%;
  transition: width 280ms var(--rag-ease);
}

.rag-success {
  color: var(--color-success);
  margin-top: 10px;
}

.rag-grid {
  align-items: start;
}

.rag-doc-panel {
  max-height: calc(100vh - 220px);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.rag-document-list {
  display: grid;
  gap: 10px;
  max-height: calc(100vh - 340px);
  overflow-y: auto;
  padding-right: 4px;
  scrollbar-gutter: stable;
}

.rag-document-row {
  align-items: center;
  background: var(--bg-white);
  border: 1px solid var(--border-light);
  border-radius: 12px;
  display: flex;
  gap: 12px;
  justify-content: space-between;
  padding: 12px 14px;
  transition:
    border-color 180ms var(--rag-ease),
    box-shadow 180ms var(--rag-ease),
    transform 180ms var(--rag-ease);
}

.rag-document-row:hover {
  border-color: rgb(15 158 213 / 28%);
  box-shadow: var(--shadow-sm);
}

.rag-document-row--builtin {
  background: linear-gradient(135deg, #ffffff 0%, #f8fbff 100%);
  border-color: rgb(15 158 213 / 28%);
  border-left: 4px solid var(--brand-cyan);
}

.rag-document-row__main {
  min-width: 0;
}

.rag-document-row__title {
  align-items: center;
  display: flex;
  gap: 8px;
  min-width: 0;
}

.rag-document-row__title strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rag-document-row p {
  color: var(--text-secondary);
  font-size: 12px;
  margin-top: 4px;
}

.rag-doc-chip {
  background: var(--bg-subtle);
  border-radius: 999px;
  color: var(--text-secondary);
  display: inline-block;
  font-size: 11px;
  font-weight: 700;
  margin-right: 6px;
  padding: 2px 8px;
}

.rag-badge {
  border-radius: 999px;
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
}

.rag-badge--builtin {
  background: rgb(15 158 213 / 12%);
  color: #0369a1;
}

.rag-badge--locked {
  background: var(--bg-subtle);
  color: var(--text-muted);
}

.rag-delete-btn:disabled {
  opacity: 0.65;
}

.rag-prompts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.rag-prompt-chip {
  background: var(--bg-subtle);
  border: 1px solid var(--border-light);
  border-radius: 999px;
  color: var(--text-secondary);
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  line-height: 1.3;
  padding: 7px 12px;
  transition:
    background 160ms var(--rag-ease),
    border-color 160ms var(--rag-ease),
    color 160ms var(--rag-ease),
    transform 160ms var(--rag-ease);
}

.rag-prompt-chip:hover:not(:disabled) {
  background: #eef8fd;
  border-color: rgb(15 158 213 / 35%);
  color: var(--text-primary);
  transform: translateY(-1px);
}

.rag-prompt-chip:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.knowledge-box {
  background: var(--bg-white);
  border: 1px solid var(--border-light);
  border-radius: 12px;
  display: grid;
  gap: 10px;
  padding: 12px;
  transition:
    border-color 180ms var(--rag-ease),
    box-shadow 180ms var(--rag-ease);
}

.knowledge-box:focus-within {
  border-color: rgb(15 158 213 / 45%);
  box-shadow: 0 0 0 4px rgb(15 158 213 / 10%);
}

.knowledge-box--busy {
  opacity: 0.92;
}

.knowledge-actions {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.knowledge-box textarea {
  border: 0;
  font: inherit;
  line-height: 1.6;
  min-height: 96px;
  outline: none;
  padding: 0;
  resize: vertical;
}

.knowledge-hint {
  color: var(--text-muted);
  font-size: 12px;
  margin: 0;
}

.rag-spinner {
  animation: rag-spin 0.8s linear infinite;
  border: 2px solid rgb(255 255 255 / 35%);
  border-radius: 50%;
  border-top-color: #fff;
  display: inline-block;
  height: 14px;
  margin-right: 6px;
  vertical-align: -2px;
  width: 14px;
}

.rag-spinner--muted {
  border-color: rgb(15 158 213 / 18%);
  border-top-color: var(--brand-cyan);
}

.rag-spinner--primary {
  border-color: rgb(231 0 18 / 18%);
  border-top-color: var(--brand-red);
}

.primary-soft-button,
.secondary-soft-button {
  align-items: center;
  display: inline-flex;
  justify-content: center;
}

@keyframes rag-spin {
  to {
    transform: rotate(360deg);
  }
}

.rag-answer {
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
  border: 1px solid rgb(15 158 213 / 18%);
  border-radius: 12px;
  display: grid;
  gap: 12px;
  margin-top: 14px;
  padding: 14px;
}

.rag-answer--loading {
  border-style: dashed;
}

.rag-answer__header {
  align-items: center;
  display: flex;
  justify-content: space-between;
}

.rag-answer__header span {
  color: var(--text-secondary);
  font-size: 12px;
}

.rag-answer__body {
  line-height: 1.75;
  margin: 0;
  white-space: pre-wrap;
}

.rag-answer__references {
  display: grid;
  gap: 8px;
}

.rag-reference {
  background: #ffffff;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  padding: 8px 10px;
  transition: border-color 160ms var(--rag-ease);
}

.rag-reference[open] {
  border-color: rgb(15 158 213 / 24%);
}

.rag-reference summary {
  align-items: center;
  cursor: pointer;
  display: flex;
  gap: 10px;
  justify-content: space-between;
}

.rag-reference summary span {
  color: var(--text-secondary);
  font-size: 12px;
}

.rag-reference p {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
  margin-top: 8px;
}

.secondary-soft-button {
  background: #f8fafc;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  color: var(--text-secondary);
  cursor: pointer;
  font: inherit;
  padding: 10px 12px;
  transition:
    background 160ms var(--rag-ease),
    border-color 160ms var(--rag-ease),
    transform 160ms var(--rag-ease);
}

.secondary-soft-button:hover:not(:disabled) {
  background: #ffffff;
  border-color: rgb(15 158 213 / 28%);
  transform: translateY(-1px);
}

.secondary-soft-button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.rag-results {
  display: grid;
  gap: 10px;
}

.rag-raw-results {
  margin-top: 12px;
}

.rag-raw-results > summary {
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 13px;
  margin-bottom: 10px;
}

.rag-result-card {
  background: var(--bg-subtle);
  border: 1px solid var(--border-light);
  border-radius: 10px;
  padding: 12px;
  transition: border-color 160ms var(--rag-ease);
}

.rag-result-card:hover {
  border-color: rgb(15 158 213 / 22%);
}

.rag-result-card--garbled {
  background: #fff7ed;
  border-color: rgb(245 158 11 / 38%);
}

.rag-result-card small {
  color: var(--text-secondary);
  display: block;
  margin-top: 8px;
}

.rag-result-card__meta {
  align-items: center;
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.rag-result-card__meta span {
  color: var(--text-muted);
  font-size: 12px;
}

.knowledge-error {
  color: var(--color-error);
  margin-top: 12px;
}

.rag-list-enter-active,
.rag-list-leave-active {
  transition:
    opacity 220ms var(--rag-ease),
    transform 220ms var(--rag-ease);
}

.rag-list-enter-from,
.rag-list-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

.rag-list-move {
  transition: transform 220ms var(--rag-ease);
}

.rag-fade-up-enter-active,
.rag-fade-up-leave-active {
  transition:
    opacity 260ms var(--rag-ease),
    transform 260ms var(--rag-ease);
}

.rag-fade-up-enter-from,
.rag-fade-up-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

.rag-toast-enter-active,
.rag-toast-leave-active {
  transition:
    opacity 180ms var(--rag-ease),
    transform 180ms var(--rag-ease);
}

.rag-toast-enter-from,
.rag-toast-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

@media (max-width: 900px) {
  .rag-stats {
    grid-template-columns: 1fr;
  }

  .rag-doc-panel {
    max-height: none;
  }

  .rag-document-list {
    max-height: none;
  }

  .knowledge-actions {
    grid-template-columns: 1fr;
  }
}
</style>
