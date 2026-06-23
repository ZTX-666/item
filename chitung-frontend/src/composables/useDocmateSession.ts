import { computed, reactive } from 'vue'
import { docmateCommit, docmateGenerate, docmateRead, docmateRetry, docmateUpload } from '../services/chitungApi'
import type { AuditEntry, DocmateChange, DocmateDocumentStructure, DocmatePreviewCard, RejectReason } from '../types/domain'

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
  changeId: string
  type: string
  target: string
  replacement: string
}

interface DocmateSessionState {
  step: DocmateStep
  filePath: string
  docId: string
  changesetId: string
  sourcePath: string
  structure: DocmateDocumentStructure | null
  instruction: string
  workItems: WorkItem[]
  acceptedEdits: AcceptedEdit[]
  completedCount: number
  outputPath: string
  outputResultPath: string
  error: string
  auditLog: AuditEntry[]
  rejectReasons: Record<string, string>
}

const state = reactive<DocmateSessionState>({
  step: 'idle',
  filePath: '',
  docId: '',
  changesetId: '',
  sourcePath: '',
  structure: null,
  instruction: '',
  workItems: [],
  acceptedEdits: [],
  completedCount: 0,
  outputPath: '',
  outputResultPath: '',
  error: '',
  auditLog: [],
  rejectReasons: {},
})

const isLoaded = computed(() => Boolean(state.docId))
const hasWork = computed(() => state.workItems.length > 0)
const pendingCount = computed(() => state.workItems.length)
const selectedCount = computed(() => state.workItems.filter((item) => item.selected).length)
const pendingChanges = computed(() => state.workItems.map((item) => item.change))
const isDone = computed(() => state.step === 'done')

/** 按风险等级分组的工作项 */
const workItemsByRisk = computed(() => {
  const groups: { high: WorkItem[]; medium: WorkItem[]; low: WorkItem[] } = {
    high: [],
    medium: [],
    low: [],
  }
  for (const item of state.workItems) {
    const level = item.card.risk_level
    if (level === 'high' || level === 'critical') {
      groups.high.push(item)
    } else if (level === 'medium') {
      groups.medium.push(item)
    } else {
      groups.low.push(item)
    }
  }
  return groups
})

/** 高风险工作项数量 */
const highRiskCount = computed(() => workItemsByRisk.value.high.length)

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

/** 添加审计日志条目 */
function addAuditEntry(
  action: AuditEntry['action'],
  target: string,
  detail?: string,
): void {
  const entry: AuditEntry = {
    id: `audit-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
    timestamp: new Date().toLocaleString('zh-CN', { hour12: false }),
    operator: '当前用户',
    action,
    target,
    detail,
  }
  state.auditLog.push(entry)
}

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
  state.changesetId = ''
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
  addAuditEntry('upload', fallbackName, `文档已加载，共 ${data.stats.paragraph_count} 段`)
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

/**
 * 生成修改方案
 * @param instruction 修改指令
 * @param context 可选的上下文（如用户选中的文本）
 */
async function generateChanges(
  instruction: string,
  context?: string,
): Promise<{ ok: boolean; count: number; error?: string }> {
  const text = instruction.trim()
  if (!text) return { ok: false, count: 0, error: '请输入修改指令' }
  if (!state.docId) return { ok: false, count: 0, error: '请先加载一个文档' }

  state.instruction = text
  state.step = 'generating'
  state.error = ''
  try {
    const result = await docmateGenerate({ docId: state.docId, instruction: text, context })
    if (!result.ok) throw new Error(formatDocmateError(result, '生成修改方案失败'))
    state.changesetId = result.data.changeset_id

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
    addAuditEntry('generate', text, `生成 ${state.workItems.length} 条修改建议`)
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

/** 按风险等级筛选选择 */
function selectByRisk(levels: string[]) {
  state.workItems.forEach((item) => {
    item.selected = levels.includes(item.card.risk_level)
  })
}

/** 仅选择低风险 */
function selectLowRiskOnly() {
  selectByRisk(['low'])
}

/** 选择非高风险（低+中） */
function selectExceptHigh() {
  selectByRisk(['low', 'medium'])
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
    if (!state.changesetId) throw new Error('缺少 changeset_id，无法写入文档。请重新生成修改方案。')
    const result = await docmateCommit({
      changesetId: state.changesetId,
      acceptedChangeIds: state.acceptedEdits.map((edit) => edit.changeId),
      saveAs: state.outputPath || defaultOutputPath(),
    })
    if (!result.ok) throw new Error(formatDocmateError(result, '写入文档失败'))
    state.outputResultPath = result.data.download_url || result.data.file_id || result.data.output_path
    state.step = 'done'
    addAuditEntry('download', state.outputResultPath, '文档已写入')
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
      changeId: item.changeId,
      type: item.change.type,
      target: item.change.target ?? '',
      replacement: item.change.replacement ?? '',
    })
    state.completedCount += 1
    addAuditEntry('accept', item.card.title, `置信度 ${Math.round(item.card.confidence * 100)}%`)
  })

  const ids = new Set(selected.map((item) => item.changeId))
  state.workItems = state.workItems.filter((item) => !ids.has(item.changeId))
  await maybeFinalize()
}

async function rejectSelected() {
  const selected = takeSelected()
  if (!selected.length) return

  selected.forEach((item) => {
    addAuditEntry('reject', item.card.title)
  })

  const ids = new Set(selected.map((item) => item.changeId))
  state.workItems = state.workItems.filter((item) => !ids.has(item.changeId))
  await maybeFinalize()
}

/**
 * 带理由拒绝单个修改建议
 * @param changeId 修改项ID
 * @param reason 拒绝理由
 */
async function rejectWithReason(changeId: string, reason: RejectReason | string): Promise<void> {
  const item = state.workItems.find((candidate) => candidate.changeId === changeId)
  if (!item) return

  state.rejectReasons[changeId] = reason
  addAuditEntry('reject', item.card.title, `拒绝理由：${reason}`)

  state.workItems = state.workItems.filter((candidate) => candidate.changeId !== changeId)
  await maybeFinalize()
}

/** 批量接受（高风险除外） */
async function acceptAllExceptHigh(): Promise<void> {
  const toAccept = state.workItems.filter(
    (item) => item.card.risk_level !== 'high' && item.card.risk_level !== 'critical',
  )
  if (!toAccept.length) return

  toAccept.forEach((item) => {
    state.acceptedEdits.push({
      changeId: item.changeId,
      type: item.change.type,
      target: item.change.target ?? '',
      replacement: item.change.replacement ?? '',
    })
    state.completedCount += 1
  })

  addAuditEntry('batch_accept', '全部接受（高风险除外）', `接受 ${toAccept.length} 项，保留高风险 ${state.workItems.length - toAccept.length} 项`)

  const ids = new Set(toAccept.map((item) => item.changeId))
  state.workItems = state.workItems.filter((item) => !ids.has(item.changeId))
  await maybeFinalize()
}

/** 仅接受低风险 */
async function acceptLowOnly(): Promise<void> {
  const toAccept = state.workItems.filter((item) => item.card.risk_level === 'low')
  if (!toAccept.length) return

  toAccept.forEach((item) => {
    state.acceptedEdits.push({
      changeId: item.changeId,
      type: item.change.type,
      target: item.change.target ?? '',
      replacement: item.change.replacement ?? '',
    })
    state.completedCount += 1
  })

  addAuditEntry('batch_accept', '仅接受低风险', `接受 ${toAccept.length} 项低风险修改`)

  const ids = new Set(toAccept.map((item) => item.changeId))
  state.workItems = state.workItems.filter((item) => !ids.has(item.changeId))
  await maybeFinalize()
}

async function retryAll(): Promise<{ ok: boolean; count: number; error?: string }> {
  if (!state.workItems.length) return { ok: false, count: 0, error: '没有可重试的修改' }

  state.step = 'generating'
  state.error = ''
  addAuditEntry('retry', state.instruction, `重试 ${state.workItems.length} 项修改`)
  try {
    const result = await docmateRetry({
      changesetId: state.changesetId,
      instruction: state.instruction,
    })
    if (!result.ok) throw new Error(formatDocmateError(result, '重试失败'))
    state.changesetId = result.data.changeset_id

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
  state.changesetId = ''
  state.sourcePath = ''
  state.structure = null
  state.outputPath = ''
  state.outputResultPath = ''
  state.error = ''
  resetWork()
}

function formatDocmateError(result: unknown, fallback: string): string {
  if (!result || typeof result !== 'object') return fallback
  const data = result as Record<string, unknown>
  for (const key of ['summary', 'error', 'message']) {
    const value = data[key]
    if (typeof value === 'string' && value.trim()) return value
  }
  const detail = data.detail
  if (detail && typeof detail === 'object') return formatDocmateError(detail, fallback)
  try {
    return JSON.stringify(data)
  } catch {
    return fallback
  }
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
    workItemsByRisk,
    highRiskCount,
    uploadDocument,
    loadDocument,
    generateChanges,
    toggleSelect,
    selectAll,
    clearSelection,
    selectByRisk,
    selectLowRiskOnly,
    selectExceptHigh,
    acceptSelected,
    rejectSelected,
    rejectWithReason,
    acceptAllExceptHigh,
    acceptLowOnly,
    retryAll,
    startNewInstruction,
    unload,
    addAuditEntry,
  }
}
