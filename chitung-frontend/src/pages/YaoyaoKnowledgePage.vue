<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
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
const isSearching = ref(false)
const isAnswering = ref(false)
const deletingId = ref('')
const error = ref('')
const lastMessage = ref('')
const ragAnswer = ref<RagAskResponse | null>(null)
const hasRawSearch = ref(false)
let refreshSeq = 0

const isFeedMode = computed(() => location.hash.includes('/feed'))
const activeCollection = computed(() => (isFeedMode.value ? 'feed' : 'safety'))
const mode = computed(() => (isFeedMode.value ? '舆情规范知识库' : '耀耀知识'))
const modeDescription = computed(() =>
  isFeedMode.value
    ? '上传舆情规范、外部讯息资料和白名单来源说明，使用本地 ChromaDB 做语义检索。'
    : '内置安全管理规定已自动入库，也可继续上传项目制度、规范、报告，AI 会基于知识库回答。',
)
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
  return fallback.filter((item) => {
    const key = `${item.source_file_name}-${item.chunk_index}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  }).slice(0, 5)
})

async function refresh() {
  const seq = ++refreshSeq
  error.value = ''
  try {
    const docItems = await listRagDocuments(activeCollection.value)
    if (seq !== refreshSeq) return
    documents.value = docItems
    const statResult = await getRagStats(activeCollection.value)
    if (seq !== refreshSeq) return
    stats.value = statResult
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
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
  try {
    let totalChunks = 0
    for (const file of accepted) {
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
  }
}

async function handleInput(event: Event) {
  const input = event.target as HTMLInputElement
  if (input.files) await uploadFiles(input.files)
  input.value = ''
}

async function handleDrop(event: DragEvent) {
  event.preventDefault()
  if (event.dataTransfer?.files) await uploadFiles(event.dataTransfer.files)
}

async function removeDocument(docId: string) {
  deletingId.value = docId
  error.value = ''
  try {
    await deleteRagDocument(docId)
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

function formatDate(value: string) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

function canDeleteDocument(doc: RagDocument) {
  return !doc.doc_id.startsWith('builtin-')
}

function upsertUploadedDocument(doc: RagDocument) {
  const index = documents.value.findIndex((item) => item.doc_id === doc.doc_id)
  if (index >= 0) documents.value.splice(index, 1, doc)
  else documents.value.unshift(doc)
}

onMounted(refresh)
</script>

<template>
  <main class="workbench">
    <section class="hero-panel">
      <div>
        <p class="eyebrow">Yaoyao Knowledge</p>
        <h1>{{ mode }}</h1>
        <p>{{ modeDescription }}</p>
      </div>
      <button class="primary-soft-button" @click="refresh">刷新</button>
    </section>

    <section class="rag-stats">
      <article class="status-card status-card--blue">
        <span>文档数</span>
        <strong>{{ stats?.document_count ?? 0 }}</strong>
        <small>已入库文件</small>
      </article>
      <article class="status-card status-card--green">
        <span>分块数</span>
        <strong>{{ stats?.chunk_count ?? 0 }}</strong>
        <small>可检索文本片段</small>
      </article>
      <article class="status-card status-card--orange">
        <span>向量数</span>
        <strong>{{ stats?.vector_count ?? 0 }}</strong>
        <small>ChromaDB 本地向量</small>
      </article>
    </section>

    <section class="panel">
      <div class="panel__header">
        <div>
          <h2>上传资料</h2>
          <p>支持 PDF、Word、TXT、Markdown、HTML。上传后自动解析、分块和向量化。</p>
        </div>
      </div>
      <label
        class="rag-dropzone"
        :class="{ 'rag-dropzone--active': isDragging }"
        @dragover.prevent="isDragging = true"
        @dragleave.prevent="isDragging = false"
        @drop="handleDrop"
      >
        <input type="file" multiple accept=".pdf,.docx,.txt,.md,.markdown,.html,.htm" @change="handleInput" />
        <span>{{ isUploading ? '正在上传并向量化...' : '拖拽文件到这里，或点击选择文件' }}</span>
      </label>
      <p v-if="lastMessage" class="rag-success">{{ lastMessage }}</p>
      <p v-if="error" class="knowledge-error">{{ error }}</p>
    </section>

    <section class="workbench-grid">
      <section class="panel">
        <div class="panel__header">
          <div>
            <h2>已上传文档</h2>
            <p>{{ documents.length }} 个文件</p>
          </div>
        </div>
        <div class="rag-document-list">
          <article v-for="doc in documents" :key="doc.doc_id" class="rag-document-row">
            <div>
              <strong>{{ doc.file_name }}</strong>
              <p>{{ doc.file_type }} · {{ doc.chunk_count }} 个分块 · {{ formatDate(doc.created_at) }}</p>
            </div>
            <button
              class="mini-button"
              :disabled="deletingId === doc.doc_id || !canDeleteDocument(doc)"
              @click="removeDocument(doc.doc_id)"
            >
              {{ !canDeleteDocument(doc) ? '内置' : deletingId === doc.doc_id ? '删除中...' : '删除' }}
            </button>
          </article>
          <p v-if="!documents.length" class="smart-form-empty">暂无文档。上传制度文件后会显示在这里。</p>
        </div>
      </section>

      <section class="panel">
        <div class="panel__header">
          <div>
            <h2>知识库问答</h2>
            <p>基于内置安全管理规定和已上传资料回答，并展示引用片段。</p>
          </div>
        </div>
        <div class="knowledge-box">
          <textarea
            v-model="queryText"
            rows="4"
            placeholder="例如：临边作业、机械作业半径、PPE 和整改闭环要求是什么？"
            @keydown.ctrl.enter="answerQuestion"
          />
          <div class="knowledge-actions">
            <button class="primary-soft-button" :disabled="isAnswering || !queryText.trim()" @click="answerQuestion">
              {{ isAnswering ? '回答中...' : '生成回答' }}
            </button>
            <button class="secondary-soft-button" :disabled="isSearching || !queryText.trim()" @click="search">
              {{ isSearching ? '检索中...' : '仅检索原文' }}
            </button>
          </div>
        </div>
        <section v-if="ragAnswer" class="rag-answer">
          <div class="rag-answer__header">
            <strong>知识库回答</strong>
            <span>{{ ragAnswer.citations.length }} 个引用</span>
          </div>
          <p>{{ ragAnswer.answer }}</p>
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
        <details v-if="results.length" class="rag-raw-results" open>
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
        <p v-if="hasRawSearch && !results.length && !isSearching" class="smart-form-empty">暂无原文检索结果。</p>
      </section>
    </section>
  </main>
</template>

<style scoped>
.rag-stats {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-bottom: 16px;
}

.rag-dropzone {
  align-items: center;
  background: linear-gradient(135deg, #111827, #1f2937);
  border: 1px dashed rgba(96, 165, 250, 0.5);
  border-radius: 14px;
  color: #dbeafe;
  display: flex;
  justify-content: center;
  min-height: 150px;
  padding: 24px;
  text-align: center;
}

.rag-dropzone input {
  display: none;
}

.rag-dropzone--active {
  border-color: #60a5fa;
  box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.15);
}

.rag-success {
  color: var(--color-success);
  margin-top: 10px;
}

.knowledge-box {
  display: grid;
  gap: 10px;
}

.knowledge-actions {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.knowledge-box textarea {
  border: 1px solid var(--border-light);
  border-radius: 10px;
  padding: 12px;
  resize: vertical;
}

.rag-answer {
  background: #f8fafc;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  display: grid;
  gap: 10px;
  margin-top: 12px;
  padding: 12px;
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

.rag-answer p {
  line-height: 1.7;
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
  border-radius: 8px;
  padding: 8px 10px;
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
}

.secondary-soft-button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.rag-document-list,
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

.rag-document-row,
.rag-result-card {
  border: 1px solid var(--border-light);
  border-radius: 10px;
  padding: 12px;
}

.rag-document-row {
  align-items: center;
  display: flex;
  justify-content: space-between;
}

.rag-document-row p {
  color: var(--text-secondary);
}

.rag-result-card {
  background: var(--bg-subtle);
}

.rag-result-card--garbled {
  background: #fff7ed;
  border-color: rgba(245, 158, 11, 0.38);
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

@media (max-width: 900px) {
  .rag-stats {
    grid-template-columns: 1fr;
  }
}
</style>
