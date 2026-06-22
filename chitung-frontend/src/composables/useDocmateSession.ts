import { computed, reactive } from 'vue'
import { docmateCommit, docmateGenerate, docmateRead, docmateRetry, docmateUpload } from '../services/chitungApi'
import type { DocmateChange, DocmateDocumentStructure, DocmatePreviewCard } from '../types/domain'

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

const isLoaded = computed(() => Boolean(state.docId))
const hasWork = computed(() => state.workItems.length > 0)
const pendingCount = computed(() => state.workItems.length)
const selectedCount = computed(() => state.workItems.filter((item) => item.selected).length)
const pendingChanges = computed(() => state.workItems.map((item) => item.change))
const isDone = computed(() => state.step === 'done')

export interface PreviewParagraph {
  index: number
  text: string
  accepted: boolean
  deleted: boolean
}

const previewParagraphs = computed<PreviewParagraph[]>(() => {
  const paragraphs = state.structure?.structure.paragraphs ?? []
  return paragraphs.map((paragraph) => {
    let text = paragraph.text
    let accepted = false

    for (const edit of state.acceptedEdits) {
      if (!edit.target || !text.includes(edit.target)) continue
      text =
        edit.type === 'text_delete'
          ? text.split(edit.target).join('')
          : text.split(edit.target).join(edit.replacement)
      accepted = true
    }

    return {
      index: paragraph.index,
      text,
      accepted,
      deleted: accepted && !text.trim(),
    }
  })
})

const acceptedAppends = computed(() =>
  state.acceptedEdits.filter((edit) => edit.type === 'text_append' && edit.replacement),
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
  if (!state.sourcePath) return ''
  return state.sourcePath.replace(/\.docx$/i, '_modified.docx')
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
  state.error = ''
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
    const uploaded = await docmateUpload(file)
    if (!uploaded.ok || !uploaded.file_path) {
      throw new Error(uploaded.error ?? '文档上传失败或未返回文件路径')
    }
    const result = await docmateRead(uploaded.file_path)
    if (!result.ok || !result.data?.doc_id) {
      throw new Error(result.error ?? '文档上传失败或未返回 doc_id')
    }
    applyReadResult(result.data, uploaded.file_name || file.name)
    return { ok: true }
  } catch (error) {
    state.error = error instanceof Error ? error.message : '未知错误'
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
  } catch (error) {
    state.error = error instanceof Error ? error.message : '未知错误'
    state.step = 'error'
    return { ok: false, error: state.error }
  }
}

async function generateChanges(instruction: string): Promise<{ ok: boolean; count: number; error?: string }> {
  const text = instruction.trim()
  if (!text) return { ok: false, count: 0, error: '请输入修改指令' }
  if (!state.docId) return { ok: false, count: 0, error: '请先加载一个文档' }

  state.instruction = text
  state.step = 'generating'
  state.error = ''
  try {
    const result = await docmateGenerate({ docId: state.docId, instruction: text })
    if (!result.ok) throw new Error(result.error ?? '生成修改方案失败')

    const changeById = new Map(result.data.changes.map((change) => [change.change_id, change]))
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
  } catch (error) {
    state.error = error instanceof Error ? error.message : '未知错误'
    state.step = 'error'
    return { ok: false, count: 0, error: state.error }
  }
}

function toggleSelect(changeId: string) {
  const item = state.workItems.find((candidate) => candidate.changeId === changeId)
  if (item) item.selected = !item.selected
}

function selectAll() {
  state.workItems.forEach((item) => {
    item.selected = true
  })
}

function clearSelection() {
  state.workItems.forEach((item) => {
    item.selected = false
  })
}

function takeSelected(): WorkItem[] {
  return state.workItems.filter((item) => item.selected)
}

async function maybeFinalize() {
  if (state.workItems.length > 0) return

  if (state.acceptedEdits.length === 0) {
    state.step = 'done'
    state.outputResultPath = ''
    return
  }

  state.step = 'committing'
  try {
    const result = await docmateCommit({
      docId: state.docId,
      edits: state.acceptedEdits.map((edit) => ({
        type: edit.type,
        target: edit.target,
        replacement: edit.replacement,
      })),
      saveAs: state.outputPath || defaultOutputPath(),
    })
    if (!result.ok) throw new Error(result.error ?? '写入文档失败')
    state.outputResultPath = result.data.download_url || result.data.file_id || result.data.output_path
    state.step = 'done'
  } catch (error) {
    state.error = error instanceof Error ? error.message : '写入文档失败'
    state.step = 'error'
  }
}

async function acceptSelected() {
  const selected = takeSelected()
  if (!selected.length) return

  selected.forEach((item) => {
    state.acceptedEdits.push({
      type: item.change.type,
      target: item.change.target ?? '',
      replacement: item.change.replacement ?? '',
    })
    state.completedCount += 1
  })

  const ids = new Set(selected.map((item) => item.changeId))
  state.workItems = state.workItems.filter((item) => !ids.has(item.changeId))
  await maybeFinalize()
}

async function rejectSelected() {
  const selected = takeSelected()
  if (!selected.length) return

  const ids = new Set(selected.map((item) => item.changeId))
  state.workItems = state.workItems.filter((item) => !ids.has(item.changeId))
  await maybeFinalize()
}

async function retryAll(): Promise<{ ok: boolean; count: number; error?: string }> {
  if (!state.workItems.length) return { ok: false, count: 0, error: '没有可重试的修改' }

  state.step = 'generating'
  state.error = ''
  try {
    const result = await docmateRetry({
      docId: state.docId,
      instruction: state.instruction,
      items: state.workItems.map((item) => ({
        type: item.change.type,
        target: item.change.target ?? '',
        replacement: item.change.replacement ?? '',
      })),
    })
    if (!result.ok) throw new Error(result.error ?? '重试失败')

    const changeById = new Map(result.data.changes.map((change) => [change.change_id, change]))
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
  } catch (error) {
    state.error = error instanceof Error ? error.message : '重试失败'
    state.step = 'reviewing'
    return { ok: false, count: 0, error: state.error }
  }
}

function startNewInstruction() {
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
