import { computed, reactive } from 'vue'
import { docmateCommit, docmateGenerate, docmateRead, docmateRetry, docmateUpload } from '../services/chitungApi'
import type { DocmateChange, DocmateDocumentStructure, DocmatePreviewCard } from '../types/domain'

/**
 * Shared DocMate (闪闪文档) editing session — work-list model.
 *
 * Loading a document (upload) and the diff work-list are shared between the
 * global assistant (where the user issues instructions and processes diffs) and
 * the document workspace page (which previews the doc and highlights pending
 * diffs inline). Diffs are processed one item/batch at a time: accepted edits
 * accumulate into an intermediate set; rejected ones are discarded; when the
 * work-list is empty the accepted set is committed ONCE and offered for download.
 */

export type DocmateStep =
  | 'idle'
  | 'loading'
  | 'loaded'
  | 'generating'
  | 'reviewing'
  | 'committing'
  | 'done'
  | 'error'

export interface WorkItem {
  changeId: string
  card: DocmatePreviewCard
  change: DocmateChange
  selected: boolean
}

interface AcceptedEdit {
  type: string
  target: string
  replacement: string
}

interface DocmateSessionState {
  step: DocmateStep
  filePath: string
  docId: string
  sourcePath: string
  structure: DocmateDocumentStructure | null
  instruction: string
  workItems: WorkItem[]
  acceptedEdits: AcceptedEdit[]
  completedCount: number
  outputPath: string
  outputResultPath: string
  error: string
}

const state = reactive<DocmateSessionState>({
  step: 'idle',
  filePath: '',
  docId: '',
  sourcePath: '',
  structure: null,
  instruction: '',
  workItems: [],
  acceptedEdits: [],
  completedCount: 0,
  outputPath: '',
  outputResultPath: '',
  error: '',
})

const isLoaded = computed(() => !!state.docId)
const hasWork = computed(() => state.workItems.length > 0)
const pendingCount = computed(() => state.workItems.length)
const selectedCount = computed(() => state.workItems.filter((w) => w.selected).length)
const pendingChanges = computed(() => state.workItems.map((w) => w.change))
const isDone = computed(() => state.step === 'done')

export interface PreviewParagraph {
  index: number
  text: string
  accepted: boolean
  deleted: boolean
}

/**
 * Paragraphs as they should appear in the live preview: the original text with
 * every ALREADY-ACCEPTED edit applied (replace/delete). Pending diffs are NOT
 * applied here — the page overlays those on top. This is what makes an accepted
 * diff immediately show up in the document preview instead of reverting to the
 * original text once it leaves the work-list.
 */
const previewParagraphs = computed<PreviewParagraph[]>(() => {
  const paras = state.structure?.structure.paragraphs ?? []
  return paras.map((p) => {
    let text = p.text
    let accepted = false
    for (const edit of state.acceptedEdits) {
      if (!edit.target || !text.includes(edit.target)) continue
      text =
        edit.type === 'text_delete'
          ? text.split(edit.target).join('')
          : text.split(edit.target).join(edit.replacement)
      accepted = true
    }
    return { index: p.index, text, accepted, deleted: accepted && !text.trim() }
  })
})

// Accepted "append" edits become committed new lines at the end of the preview.
const acceptedAppends = computed(() =>
  state.acceptedEdits.filter((e) => e.type === 'text_append' && e.replacement),
)

const docName = computed(() => {
  const path = state.sourcePath || state.filePath
  if (!path) return ''
  return path.split(/[\\/]/).pop() || path
})

const docStats = computed(
  () => state.structure?.stats ?? { paragraph_count: 0, table_count: 0, image_count: 0 },
)

function defaultOutputPath(): string {
  const source = state.sourcePath
  if (!source) return ''
  return source.replace(/\.docx$/i, '_modified.docx')
}

function resetWork() {
  state.workItems = []
  state.acceptedEdits = []
  state.completedCount = 0
  state.outputResultPath = ''
  state.instruction = ''
}

function applyReadResult(data: DocmateDocumentStructure, fallbackName: string) {
  state.docId = data.doc_id ?? ''
  state.sourcePath = data.source_path ?? ''
  state.filePath = fallbackName
  state.structure = data
  state.outputPath = defaultOutputPath()
  resetWork()
  state.step = 'loaded'
}

async function uploadDocument(file: File): Promise<{ ok: boolean; error?: string }> {
  if (!file) return { ok: false, error: '请选择文件' }
  if (!file.name.toLowerCase().endsWith('.docx')) {
    return { ok: false, error: '仅支持 .docx 文件' }
  }
  state.step = 'loading'
  state.error = ''
  try {
    const result = await docmateUpload(file)
    if (!result.ok || !result.data?.doc_id) {
      throw new Error(result.error ?? '文档上传失败或未返回 doc_id')
    }
    applyReadResult(result.data, file.name)
    return { ok: true }
  } catch (err) {
    state.error = err instanceof Error ? err.message : '未知错误'
    state.step = 'error'
    return { ok: false, error: state.error }
  }
}

async function loadDocument(path: string): Promise<{ ok: boolean; error?: string }> {
  const target = path.trim()
  if (!target) return { ok: false, error: '请提供 .docx 文件路径' }
  state.step = 'loading'
  state.error = ''
  try {
    const result = await docmateRead(target)
    if (!result.ok || !result.data?.doc_id) {
      throw new Error(result.error ?? '文档读取失败或未返回 doc_id')
    }
    applyReadResult(result.data, target)
    return { ok: true }
  } catch (err) {
    state.error = err instanceof Error ? err.message : '未知错误'
    state.step = 'error'
    return { ok: false, error: state.error }
  }
}

async function generateChanges(
  instruction: string,
): Promise<{ ok: boolean; count: number; error?: string }> {
  const text = instruction.trim()
  if (!text) return { ok: false, count: 0, error: '请输入修改指令' }
  if (!state.docId) return { ok: false, count: 0, error: '请先加载一个文档' }

  state.instruction = text
  state.step = 'generating'
  state.error = ''
  try {
    const result = await docmateGenerate({ docId: state.docId, instruction: text })
    if (!result.ok) throw new Error(result.error ?? '生成修改方案失败')
    const changeById = new Map(result.data.changes.map((c) => [c.change_id, c]))
    state.workItems = result.data.preview_cards.map((card) => ({
      changeId: card.change_id,
      card,
      change: changeById.get(card.change_id) ?? {
        change_id: card.change_id,
        type: card.type,
        target: '',
        replacement: '',
        risk_level: card.risk_level,
        confidence: card.confidence,
      },
      selected: true,
    }))
    state.step = state.workItems.length > 0 ? 'reviewing' : 'loaded'
    return { ok: true, count: state.workItems.length }
  } catch (err) {
    state.error = err instanceof Error ? err.message : '未知错误'
    state.step = 'error'
    return { ok: false, count: 0, error: state.error }
  }
}

function toggleSelect(changeId: string) {
  const item = state.workItems.find((w) => w.changeId === changeId)
  if (item) item.selected = !item.selected
}

function selectAll() {
  state.workItems.forEach((w) => {
    w.selected = true
  })
}

function clearSelection() {
  state.workItems.forEach((w) => {
    w.selected = false
  })
}

function takeSelected(): WorkItem[] {
  const selected = state.workItems.filter((w) => w.selected)
  return selected.length ? selected : []
}

async function maybeFinalize() {
  if (state.workItems.length > 0) return
  // All diffs processed — commit the accepted set once.
  if (state.acceptedEdits.length === 0) {
    state.step = 'done'
    state.outputResultPath = ''
    return
  }
  state.step = 'committing'
  try {
    const result = await docmateCommit({
      docId: state.docId,
      edits: state.acceptedEdits.map((e) => ({
        type: e.type,
        target: e.target,
        replacement: e.replacement,
      })),
      saveAs: state.outputPath || defaultOutputPath(),
    })
    if (!result.ok) throw new Error(result.error ?? '写入文档失败')
    state.outputResultPath = result.data.output_path
    state.step = 'done'
  } catch (err) {
    state.error = err instanceof Error ? err.message : '写入文档失败'
    state.step = 'error'
  }
}

async function acceptSelected() {
  const selected = takeSelected()
  if (!selected.length) return
  for (const item of selected) {
    state.acceptedEdits.push({
      type: item.change.type,
      target: item.change.target ?? '',
      replacement: item.change.replacement ?? '',
    })
    state.completedCount += 1
  }
  const ids = new Set(selected.map((w) => w.changeId))
  state.workItems = state.workItems.filter((w) => !ids.has(w.changeId))
  await maybeFinalize()
}

async function rejectSelected() {
  const selected = takeSelected()
  if (!selected.length) return
  const ids = new Set(selected.map((w) => w.changeId))
  state.workItems = state.workItems.filter((w) => !ids.has(w.changeId))
  await maybeFinalize()
}

async function retryAll(): Promise<{ ok: boolean; count: number; error?: string }> {
  // Re-ask the model for ALTERNATIVE suggestions for ALL pending diffs, replacing
  // the entire work-list. Already-accepted edits and selection state don't matter.
  if (!state.workItems.length) return { ok: false, count: 0, error: '没有可重试的修改' }

  state.step = 'generating'
  state.error = ''
  try {
    const items = state.workItems.map((w) => ({
      type: w.change.type,
      target: w.change.target ?? '',
      replacement: w.change.replacement ?? '',
    }))
    const result = await docmateRetry({
      docId: state.docId,
      instruction: state.instruction,
      items,
    })
    if (!result.ok) throw new Error(result.error ?? '重试失败')

    const changeById = new Map(result.data.changes.map((c) => [c.change_id, c]))
    state.workItems = result.data.preview_cards.map((card) => ({
      changeId: card.change_id,
      card,
      change: changeById.get(card.change_id) ?? {
        change_id: card.change_id,
        type: card.type,
        target: '',
        replacement: '',
        risk_level: card.risk_level,
        confidence: card.confidence,
      },
      selected: true,
    }))
    state.step = 'reviewing'
    return { ok: true, count: state.workItems.length }
  } catch (err) {
    state.error = err instanceof Error ? err.message : '重试失败'
    state.step = 'reviewing' // keep the existing work-list intact
    return { ok: false, count: 0, error: state.error }
  }
}

function startNewInstruction() {
  // After a commit, allow issuing another instruction on the same document.
  state.workItems = []
  state.step = 'loaded'
}

function unload() {
  state.step = 'idle'
  state.filePath = ''
  state.docId = ''
  state.sourcePath = ''
  state.structure = null
  state.outputPath = ''
  state.outputResultPath = ''
  state.error = ''
  resetWork()
}

export function useDocmateSession() {
  return {
    state,
    isLoaded,
    hasWork,
    isDone,
    pendingCount,
    selectedCount,
    pendingChanges,
    previewParagraphs,
    acceptedAppends,
    docName,
    docStats,
    uploadDocument,
    loadDocument,
    generateChanges,
    toggleSelect,
    selectAll,
    clearSelection,
    acceptSelected,
    rejectSelected,
    retryAll,
    startNewInstruction,
    unload,
  }
}
