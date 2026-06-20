import { ref, type Ref } from 'vue'
import type { Editor } from '@tiptap/vue-3'
import { DOC_BLOCK_SEPARATOR, findRangeInDocument } from '@/utils/textMatch'
import {
  buildDiffInsertHtml,
  resolveReplaceRange,
  replaceDocumentRange,
  resolveInsertPosition,
  clearMarksInEditor,
} from '@/utils/editorReplace'
import type { RevisionHistoryEntry, RevisionResult } from '@/types'
import { processRoute, processRevision, processRisk } from '@/api/ai'
import { useStickySelection, type StickyRange } from '@/composables/useStickySelection'
import { cloneAnchor, isValidAnchor } from '@/utils/revisionAnchor'

export type EditorAiState = 'idle' | 'selected' | 'thinking' | 'reviewing'

export type LockedRange = StickyRange

export interface ReviewState {
  oldText: string
  newText: string
  command: string
  insertFrom: number
  insertTo: number
  lockFrom: number
  lockTo: number
  operation: 'replace' | 'insert' | 'delete'
}

const REVIEW_MARKS = ['diffDeletion', 'diffInsertion']

function inferRevisionOperation(result: RevisionResult): 'replace' | 'insert' | 'delete' {
  if (result.operation) return result.operation
  const optionText = result.options?.[0]?.text?.trim() ?? ''
  const oldText = result.old_text?.trim() ?? ''
  if (oldText && !optionText) return 'delete'
  if (!oldText && optionText) return 'insert'
  return 'replace'
}
const MAX_REGENERATE = 3

export function useEditorAi(editor: Ref<Editor | undefined>) {
  const aiState = ref<EditorAiState>('idle')
  const review = ref<ReviewState | null>(null)
  const revisionHistory = ref<RevisionHistoryEntry[]>([])
  const chatHistory = ref<{ role: string; content: string }[]>([])
  const frozenAnchor = ref<StickyRange | null>(null)
  const lastCommand = ref('')
  const regenerateCount = ref(0)
  const regenerating = ref(false)
  const thinkingLog = ref('')
  const pendingReviewAction = ref(false)
  let taskGeneration = 0

  const {
    stickyRange,
    setStickyRange,
    getStickyRange,
    restoreStickyVisual,
    clearStickyRange,
    validateAfterDocChange,
    handleMouseUp,
    handleEditorClick,
    handleBlur,
    locateByText,
  } = useStickySelection(editor)

  function getEd() {
    return editor.value
  }

  function syncAiState() {
    if (aiState.value === 'thinking' || aiState.value === 'reviewing') return
    aiState.value = getStickyRange() ? 'selected' : 'idle'
  }

  function getLockedRange(): LockedRange | null {
    return getStickyRange()
  }

  function lockSelection(from?: number, to?: number): LockedRange | null {
    const ed = getEd()
    if (!ed) return null

    let f = from
    let t = to
    if (f === undefined || t === undefined) {
      const sel = ed.state.selection
      f = sel.from
      t = sel.to
    }
    if (f === t) {
      const existing = getStickyRange()
      syncAiState()
      return existing
    }

    const range = setStickyRange(f, t)
    syncAiState()
    return range
  }

  function captureSelectionAnchor(): StickyRange | null {
    const range = restoreStickyVisual() || getStickyRange()
    if (!range) return null
    frozenAnchor.value = cloneAnchor(range)
    return frozenAnchor.value
  }

  function resolveActiveAnchor(preferredText?: string): LockedRange | null {
    const ed = getEd()
    if (!ed) return null

    const candidates: StickyRange[] = []
    if (frozenAnchor.value) candidates.push(frozenAnchor.value)
    const sticky = getStickyRange()
    if (sticky) candidates.push(sticky)
    if (preferredText?.trim()) {
      const found = resolveRangeForText(preferredText)
      if (found) candidates.push(found)
    }

    for (const candidate of candidates) {
      if (!isValidAnchor(candidate, ed.state.doc.content.size)) continue
      const text =
        ed.state.doc.textBetween(candidate.from, candidate.to, DOC_BLOCK_SEPARATOR) ||
        candidate.text
      if (!text.trim()) continue
      return { from: candidate.from, to: candidate.to, text }
    }

    return null
  }

  function clearFrozenAnchor() {
    frozenAnchor.value = null
  }

  function clearLock() {
    clearStickyRange()
    syncAiState()
  }

  function removePreviewInsert() {
    const ed = getEd()
    if (!ed || !review.value) return
    const { insertFrom, insertTo } = review.value
    if (insertFrom >= insertTo || insertTo > ed.state.doc.content.size) return
    ed.chain().deleteRange({ from: insertFrom, to: insertTo }).run()
    review.value.insertFrom = review.value.insertTo
  }

  function resolveRangeForText(text: string, hint?: { from: number; to: number } | null) {
    const ed = getEd()
    if (!ed) return null
    const sticky = getStickyRange()
    return (
      resolveReplaceRange(ed, sticky?.text || text, sticky ? { from: sticky.from, to: sticky.to } : hint) ||
      resolveReplaceRange(ed, text, hint)
    )
  }

  function applyDiffDeletionMark(from: number, to: number): boolean {
    const ed = getEd()
    if (!ed || from >= to) return false
    return ed
      .chain()
      .focus()
      .setTextSelection({ from, to })
      .setMark('diffDeletion')
      .scrollIntoView()
      .run()
  }

  function findParagraphStart(ed: NonNullable<ReturnType<typeof getEd>>, pos: number): number {
    const doc = ed.state.doc
    const safePos = Math.max(0, Math.min(pos, doc.content.size))
    const $pos = doc.resolve(safePos)
    for (let d = $pos.depth; d > 0; d--) {
      if ($pos.node(d).isBlock) return $pos.start(d)
    }
    return 0
  }

  function findParagraphEnd(ed: NonNullable<ReturnType<typeof getEd>>, pos: number): number {
    const doc = ed.state.doc
    const safePos = Math.max(0, Math.min(pos, doc.content.size))
    const $pos = doc.resolve(safePos)
    for (let d = $pos.depth; d > 0; d--) {
      if ($pos.node(d).isBlock) return $pos.end(d)
    }
    return doc.content.size
  }

  function commitLocatedRange(
    ed: NonNullable<ReturnType<typeof getEd>>,
    from: number,
    to: number,
    text?: string,
  ): LockedRange {
    const range = {
      from,
      to,
      text: text || ed.state.doc.textBetween(from, to, DOC_BLOCK_SEPARATOR),
    }
    stickyRange.value = range
    frozenAnchor.value = cloneAnchor(range)
    ed.commands.setStickyHighlight(from, to)
    ed.chain().focus().setTextSelection({ from, to }).scrollIntoView().run()
    return range
  }

  function locateRangeFromDocText(ed: NonNullable<ReturnType<typeof getEd>>, searchText: string): LockedRange | null {
    const found = findRangeInDocument(ed.state.doc, searchText)
    if (!found) return null
    return commitLocatedRange(ed, found.from, found.to, found.text || searchText)
  }

  function resolveTargetForResult(result: RevisionResult): LockedRange | null {
    const ed = getEd()
    if (!ed) return null

    const prepared = prepareAgentTarget(result)
    if (prepared) return prepared

    if (result.paragraph_index) {
      const byIndex = locateByParagraphIndex(result.paragraph_index)
      if (byIndex) return byIndex
    }

    const paragraphText = result.paragraph_text?.trim()
    if (paragraphText) {
      const byParaText = locateRangeFromDocText(ed, paragraphText)
      if (byParaText) return byParaText
    }

    const oldText = result.old_text?.trim()
    if (oldText) {
      const direct = locateRangeFromDocText(ed, oldText)
      if (direct) return direct

      if (oldText.length > 16) {
        const prefix = findRangeInDocument(ed.state.doc, oldText.slice(0, Math.min(80, oldText.length)))
        if (prefix) {
          return commitLocatedRange(
            ed,
            prefix.from,
            prefix.to,
            ed.state.doc.textBetween(prefix.from, prefix.to, DOC_BLOCK_SEPARATOR) || oldText,
          )
        }
      }

      const chunks = oldText.match(/[\u4e00-\u9fff]{4,}/g) || []
      for (const chunk of chunks) {
        const found = findRangeInDocument(ed.state.doc, chunk)
        if (found) {
          const paraStart = findParagraphStart(ed, found.from)
          const paraEnd = findParagraphEnd(ed, found.to)
          if (paraStart <= paraEnd) {
            return commitLocatedRange(
              ed,
              paraStart,
              paraEnd,
              ed.state.doc.textBetween(paraStart, paraEnd, DOC_BLOCK_SEPARATOR),
            )
          }
        }
      }
    }

    const fallback = resolveActiveAnchor(oldText)
    if (!fallback) {
      console.warn('[DocMate] 前端定位失败:', {
        old_text: result.old_text?.slice(0, 80),
        paragraph_index: result.paragraph_index,
        paragraph_text: result.paragraph_text?.slice(0, 80),
        operation: result.operation,
      })
    }
    return fallback
  }

  function finalizeAcceptedChange(command: string, oldText: string, newText: string) {
    revisionHistory.value.unshift({
      id: `rev-${Date.now()}`,
      time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
      command,
      oldText,
      newText,
      status: 'accepted',
    })
    window.electronAPI?.logInteraction?.({
      command,
      old_text: oldText,
      new_text: newText,
      action: 'accept',
    }).catch(() => {})
    review.value = null
    clearFrozenAnchor()
    lastCommand.value = ''
    regenerateCount.value = 0
    aiState.value = 'idle'
    clearStickyRange()
  }

  function applyRevisionDirect(result: RevisionResult, command: string): boolean {
    const ed = getEd()
    if (!ed) return false

    const option = result.options?.[0]
    const op = inferRevisionOperation(result)
    const newText = option?.text ?? ''
    const oldTextPref = result.old_text?.trim() || ''

    clearReview()
    let ok = false
    let oldText = oldTextPref

    if (op === 'insert') {
      const pos =
        resolveInsertPosition(
          ed,
          result.insert_anchor,
          result.insert_position === 'start' ? 'start' : result.insert_position === 'after' ? 'after' : 'end',
        ) ?? resolveInsertPosition(ed, undefined, 'end')
      if (pos === null) return false
      ok = replaceDocumentRange(ed, pos, pos, newText)
      oldText = ''
    } else if (op === 'delete') {
      const target = resolveTargetForResult(result)
      if (target) {
        clearMarksInEditor(ed, REVIEW_MARKS)
        ok = replaceDocumentRange(ed, target.from, target.to, '')
        oldText =
          ed.state.doc.textBetween(target.from, target.to, DOC_BLOCK_SEPARATOR) || target.text || oldTextPref
      } else {
        ok = applyReplacement(oldTextPref, '', null)
      }
    } else {
      const target = resolveTargetForResult(result)
      if (target) {
        clearMarksInEditor(ed, REVIEW_MARKS)
        ok = replaceDocumentRange(ed, target.from, target.to, newText)
        oldText =
          ed.state.doc.textBetween(target.from, target.to, DOC_BLOCK_SEPARATOR) || target.text || oldTextPref
      } else {
        ok = applyReplacement(oldTextPref, newText, null)
      }
    }

    if (!ok) return false
    finalizeAcceptedChange(command, oldText, newText)
    return true
  }

  /** Agent Apply：展示 Diff 后立即采纳；预览失败则直接改稿 */
  function applyRevisionResult(result: RevisionResult, command: string): boolean {
    clearReview()
    const previewOk = showReviewFromResult(result, command)
    if (previewOk && review.value) {
      return acceptReview()
    }
    return applyRevisionDirect(result, command)
  }

  function applyReplacement(oldText: string, newText: string, hint?: { from: number; to: number } | null): boolean {
    const ed = getEd()
    if (!ed) return false

    const range = resolveRangeForText(oldText, hint)
    if (!range) return false

    clearMarksInEditor(ed, REVIEW_MARKS)
    const ok = replaceDocumentRange(ed, range.from, range.to, newText)
    if (ok) clearStickyRange()
    return ok
  }

  function showInlineReview(
    oldText: string,
    newText: string,
    command: string,
    range?: LockedRange | null,
    operation: ReviewState['operation'] = 'replace',
  ) {
    const ed = getEd()
    if (!ed) return false

    if (operation === 'insert') {
      return showInsertReview(newText, command, range)
    }

    const target = range || resolveActiveAnchor(oldText)
    if (!target || !isValidAnchor(target, ed.state.doc.content.size)) return false

    const actualOldText =
      ed.state.doc.textBetween(target.from, target.to, DOC_BLOCK_SEPARATOR) || target.text || oldText

    clearReview()
    stickyRange.value = { from: target.from, to: target.to, text: actualOldText }
    frozenAnchor.value = cloneAnchor(stickyRange.value)
    ed.commands.setStickyHighlight(target.from, target.to)

    if (operation === 'delete') {
      applyDiffDeletionMark(target.from, target.to)
      review.value = {
        oldText: actualOldText,
        newText: '',
        command,
        insertFrom: target.to,
        insertTo: target.to,
        lockFrom: target.from,
        lockTo: target.to,
        operation: 'delete',
      }
      lastCommand.value = command
      regenerateCount.value = 0
      aiState.value = 'reviewing'
      return true
    }

    applyDiffDeletionMark(target.from, target.to)

    const insertHtml = buildDiffInsertHtml(newText)
    const insertFrom = target.to
    const sizeBefore = ed.state.doc.content.size
    ed.chain().insertContentAt(insertFrom, insertHtml, { updateSelection: false }).run()
    const insertTo = insertFrom + (ed.state.doc.content.size - sizeBefore)

    review.value = {
      oldText: actualOldText,
      newText,
      command,
      insertFrom,
      insertTo,
      lockFrom: target.from,
      lockTo: target.to,
      operation: 'replace',
    }
    lastCommand.value = command
    regenerateCount.value = 0
    aiState.value = 'reviewing'
    return true
  }

  function showInsertReview(
    newText: string,
    command: string,
    range?: LockedRange | null,
    anchor?: string,
    position: 'start' | 'end' | 'after' = 'end',
  ) {
    const ed = getEd()
    if (!ed || !newText.trim()) return false

    const pos =
      range?.from ??
      resolveInsertPosition(ed, anchor, position) ??
      resolveInsertPosition(ed, undefined, 'end')
    if (pos === null) return false

    clearReview()
    const insertHtml = buildDiffInsertHtml(newText)
    const sizeBefore = ed.state.doc.content.size
    ed.chain().focus().insertContentAt(pos, insertHtml, { updateSelection: false }).run()
    const insertTo = pos + (ed.state.doc.content.size - sizeBefore)

    stickyRange.value = { from: pos, to: pos, text: '' }
    frozenAnchor.value = cloneAnchor(stickyRange.value)
    ed.commands.setStickyHighlight(pos, pos)

    review.value = {
      oldText: '',
      newText,
      command,
      insertFrom: pos,
      insertTo,
      lockFrom: pos,
      lockTo: pos,
      operation: 'insert',
    }
    lastCommand.value = command
    regenerateCount.value = 0
    aiState.value = 'reviewing'
    return true
  }

  function acceptReview(): boolean {
    const ed = getEd()
    if (!ed || !review.value || pendingReviewAction.value) return false

    pendingReviewAction.value = true
    ed.view.dom.classList.add('diff-accepting')
    setTimeout(() => {
      ed.view.dom.classList.remove('diff-accepting')
      performAcceptReview()
      pendingReviewAction.value = false
    }, 350)
    return true
  }

  function performAcceptReview(): boolean {
    const ed = getEd()
    if (!ed || !review.value) return false

    const { newText, command, lockFrom, lockTo } = review.value
    const oldText =
      ed.state.doc.textBetween(lockFrom, lockTo, DOC_BLOCK_SEPARATOR) || review.value.oldText

    removePreviewInsert()
    clearMarksInEditor(ed, REVIEW_MARKS)

    const op = review.value.operation || 'replace'
    let ok = false

    if (op === 'insert') {
      ok = replaceDocumentRange(ed, lockFrom, lockFrom, newText)
    } else if (op === 'delete') {
      ok = replaceDocumentRange(ed, lockFrom, lockTo, '')
    } else if (lockFrom < lockTo && lockTo <= ed.state.doc.content.size) {
      ok = replaceDocumentRange(ed, lockFrom, lockTo, newText)
    }
    if (!ok) {
      ok = applyReplacement(oldText, newText, { from: lockFrom, to: lockTo })
    }
    if (!ok) return false

    finalizeAcceptedChange(command, oldText, newText)
    return true
  }

  function rejectReview(rejectReason = '') {
    const ed = getEd()
    if (ed && review.value && !pendingReviewAction.value) {
      pendingReviewAction.value = true
      ed.view.dom.classList.add('diff-rejecting')
      setTimeout(() => {
        ed.view.dom.classList.remove('diff-rejecting')
        performRejectReview(rejectReason)
        pendingReviewAction.value = false
      }, 280)
      return
    }
    if (pendingReviewAction.value) return
    performRejectReview(rejectReason)
  }

  function performRejectReview(rejectReason = '') {
    if (review.value) {
      revisionHistory.value.unshift({
        id: `rev-${Date.now()}`,
        time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
        command: review.value.command,
        oldText: review.value.oldText,
        newText: review.value.newText,
        status: 'rejected',
      })
      window.electronAPI?.logInteraction?.({
        command: review.value.command,
        old_text: review.value.oldText,
        new_text: review.value.newText,
        action: 'reject',
        reject_reason: rejectReason,
      }).catch(() => {})
    }
    removePreviewInsert()
    const ed = getEd()
    if (ed) clearMarksInEditor(ed, REVIEW_MARKS)
    review.value = null
    restoreStickyVisual()
    aiState.value = getStickyRange() ? 'selected' : 'idle'
  }

  function clearReview() {
    pendingReviewAction.value = false
    removePreviewInsert()
    const ed = getEd()
    if (ed) clearMarksInEditor(ed, ['diffDeletion', 'diffInsertion'])
    review.value = null
    clearFrozenAnchor()
    syncAiState()
  }

  function cancelThinking() {
    pendingReviewAction.value = false
    taskGeneration += 1
    thinkingLog.value = ''
    window.electronAPI?.cancelAI?.().catch(() => {})
    aiState.value = getStickyRange() ? 'selected' : 'idle'
    restoreStickyVisual()
  }

  async function submitCommand(command: string): Promise<{ ok: boolean; error?: string }> {
    const ed = getEd()
    if (!ed || aiState.value === 'thinking' || aiState.value === 'reviewing') {
      return { ok: false, error: '请等待当前任务完成，或点击停止' }
    }

    let locked = captureSelectionAnchor() || lockSelection()

    if (!locked) {
      const doc = ed.getText({ blockSeparator: DOC_BLOCK_SEPARATOR })
      const gen = ++taskGeneration
      thinkingLog.value = ''
      aiState.value = 'thinking'

      try {
        const routeResult = await processRoute(doc, '', command, chatHistory.value, (chunk) => {
          if (gen !== taskGeneration) return
          thinkingLog.value += chunk
        })

        if (gen !== taskGeneration) return { ok: false, error: '已终止' }

        chatHistory.value.push({ role: 'user', content: command })

        if (!routeResult?.task || routeResult.result === undefined) {
          throw new Error('AI 返回格式异常')
        }

        const { task, result } = routeResult

        if (task === 'clarify') {
          thinkingLog.value = ''
          aiState.value = 'idle'
          return { ok: false, error: (result as { question: string }).question }
        }

        if (task === 'risk') {
          const risks = (result as { risks: unknown[] }).risks
          chatHistory.value.push({ role: 'assistant', content: `发现 ${risks.length} 项风险` })
          thinkingLog.value = ''
          aiState.value = 'idle'
          return { ok: true, error: `扫描完成，发现 ${risks.length} 项需关注（详见闪闪面板）` }
        }

        if (task === 'qa') {
          thinkingLog.value = ''
          aiState.value = 'idle'
          return { ok: true, error: '问答请在闪闪面板进行（Ctrl+K）' }
        }

        const rev = result as RevisionResult
        const shown = showReviewFromResult(rev, command)
        if (!shown) throw new Error('无法在文档中定位修改位置，请选中文字后再试')

        thinkingLog.value = ''
        chatHistory.value.push({ role: 'assistant', content: '已生成修改方案，Ctrl+Enter 采纳或 Esc 拒绝' })
        return { ok: true }
      } catch (err) {
        if (gen !== taskGeneration) return { ok: false, error: '已终止' }
        thinkingLog.value = ''
        aiState.value = 'idle'
        const msg = err instanceof Error ? err.message : String(err)
        return { ok: false, error: msg }
      }
    }

    const doc = ed.getText({ blockSeparator: DOC_BLOCK_SEPARATOR })
    const sel = locked.text
    const gen = ++taskGeneration
    thinkingLog.value = ''
    aiState.value = 'thinking'

    try {
      const routeResult = await processRoute(doc, sel, command, chatHistory.value, (chunk) => {
        if (gen !== taskGeneration) return
        thinkingLog.value += chunk
      })

      if (gen !== taskGeneration) {
        return { ok: false, error: '已终止' }
      }

      chatHistory.value.push({ role: 'user', content: command })

      if (!routeResult?.task || routeResult.result === undefined) {
        throw new Error('AI 返回格式异常')
      }

      const { task, result } = routeResult

      if (task === 'risk') {
        const risks = (result as { risks: unknown[] }).risks
        chatHistory.value.push({ role: 'assistant', content: `发现 ${risks.length} 项风险` })
        thinkingLog.value = ''
        aiState.value = 'selected'
        restoreStickyVisual()
        return { ok: true, error: `扫描完成，发现 ${risks.length} 项需关注（详见闪闪面板）` }
      }

      if (task === 'qa') {
        thinkingLog.value = ''
        aiState.value = 'selected'
        restoreStickyVisual()
        return { ok: true, error: '问答请在闪闪面板进行（Ctrl+K）' }
      }

      const rev = result as RevisionResult
      const option = rev.options?.[0]
      const op = inferRevisionOperation(rev)
      if (!option && op !== 'delete') throw new Error('未返回修改方案')
      if (option && !option.text && option.text !== '' && op !== 'delete') {
        throw new Error('未返回修改方案')
      }

      const currentLock = resolveActiveAnchor(rev.old_text || locked.text)
      if (!currentLock) throw new Error('选区已失效，请重新选中文字')

      const shown =
        op === 'delete'
          ? showInlineReview(currentLock.text, '', command, currentLock, 'delete')
          : showInlineReview(currentLock.text, option?.text ?? '', command, currentLock, op)
      if (!shown) throw new Error('无法在文档中定位修改位置，请重新选中文字后再试')

      thinkingLog.value = ''
      chatHistory.value.push({ role: 'assistant', content: '已生成修改方案，Ctrl+Enter 采纳或 Esc 拒绝' })
      return { ok: true }
    } catch (err) {
      if (gen !== taskGeneration) {
        return { ok: false, error: '已终止' }
      }
      thinkingLog.value = ''
      aiState.value = getStickyRange() ? 'selected' : 'idle'
      restoreStickyVisual()
      const msg = err instanceof Error ? err.message : String(err)
      return { ok: false, error: msg }
    }
  }

  async function submitRiskScan(): Promise<string> {
    const ed = getEd()
    if (!ed) return '编辑器未就绪'
    if (aiState.value === 'thinking' || aiState.value === 'reviewing') {
      return '请等待当前任务完成'
    }
    const gen = ++taskGeneration
    thinkingLog.value = ''
    aiState.value = 'thinking'
    try {
      const risks = await processRisk(
        ed.getText({ blockSeparator: DOC_BLOCK_SEPARATOR }),
        (chunk) => {
          if (gen === taskGeneration) thinkingLog.value += chunk
        },
      )
      if (gen !== taskGeneration) return '已终止'
      thinkingLog.value = ''
      aiState.value = getStickyRange() ? 'selected' : 'idle'
      restoreStickyVisual()
      return `扫描完成，发现 ${risks.length} 项需关注`
    } catch (err) {
      if (gen !== taskGeneration) return '已终止'
      thinkingLog.value = ''
      aiState.value = getStickyRange() ? 'selected' : 'idle'
      restoreStickyVisual()
      return err instanceof Error ? err.message : '扫描失败'
    }
  }

  function locateByParagraphIndex(index: number): LockedRange | null {
    const ed = getEd()
    if (!ed || index < 1) return null

    const docText = ed.getText({ blockSeparator: DOC_BLOCK_SEPARATOR })
    const paragraphs = docText
      .split(/\n+/)
      .map((p) => p.trim())
      .filter(Boolean)
    const para = paragraphs[index - 1]
    if (!para) return null
    return locateByText(para)
  }

  /** Cursor Agent：无鼠标选区时，根据 AI 返回的段落/原文自动锚定 */
  function prepareAgentTarget(result: RevisionResult): LockedRange | null {
    const ed = getEd()
    if (!ed) return null

    const operation = result.operation || 'replace'

    if (operation === 'insert') {
      if (result.insert_anchor?.trim()) {
        const anchored = locateByText(result.insert_anchor.trim())
        if (anchored) return anchored
      }
      const pos = resolveInsertPosition(
        ed,
        result.insert_anchor,
        result.insert_position === 'start' ? 'start' : result.insert_position === 'after' ? 'after' : 'end',
      )
      if (pos === null) return null
      const range = { from: pos, to: pos, text: '' }
      stickyRange.value = range
      frozenAnchor.value = cloneAnchor(range)
      ed.commands.setStickyHighlight(pos, pos)
      ed.chain().focus().setTextSelection(pos).scrollIntoView().run()
      return range
    }

    if (result.paragraph_index) {
      const byIndex = locateByParagraphIndex(result.paragraph_index)
      if (byIndex) return byIndex
    }

    const oldText = result.old_text?.trim()
    if (!oldText) return null

    const direct = locateByText(oldText)
    if (direct) return direct

    const resolved = resolveReplaceRange(ed, oldText, null)
    if (resolved) {
      stickyRange.value = { from: resolved.from, to: resolved.to, text: resolved.text }
      frozenAnchor.value = cloneAnchor(stickyRange.value)
      ed.commands.setStickyHighlight(resolved.from, resolved.to)
      ed.chain()
        .focus()
        .setTextSelection({ from: resolved.from, to: resolved.to })
        .scrollIntoView()
        .run()
      return stickyRange.value
    }

    if (oldText.length > 24) {
      const prefix = locateByText(oldText.slice(0, Math.min(80, oldText.length)))
      if (prefix) return prefix
    }

    return null
  }

  function showReviewFromResult(result: RevisionResult, command: string, resetRegenerate = true) {
    lastCommand.value = command
    if (resetRegenerate) regenerateCount.value = 0
    const option = result.options?.[0]
    const operation = inferRevisionOperation(result)

    if (getStickyRange()) {
      captureSelectionAnchor()
    }

    if (operation === 'delete') {
      const target = resolveTargetForResult(result)
      if (!target) return false
      return showInlineReview(target.text, '', command, target, 'delete')
    }

    if (operation === 'insert') {
      if (!option?.text?.trim()) return false
      const prepared = resolveTargetForResult(result)
      const pos = result.insert_position || 'end'
      return showInsertReview(option.text, command, prepared, result.insert_anchor, pos)
    }

    if (!option) return false

    const target = resolveTargetForResult(result)
    if (!target) return false

    return showInlineReview(target.text, option.text ?? '', command, target, 'replace')
  }

  async function regenerateCommand(): Promise<{ ok: boolean; error?: string; revision?: RevisionResult }> {
    if (regenerateCount.value >= MAX_REGENERATE) {
      return { ok: false, error: `最多重新生成 ${MAX_REGENERATE} 次，请修改指令后重试` }
    }

    const ed = getEd()
    if (!ed) return { ok: false, error: '编辑器未就绪' }

    if (!review.value && !lastCommand.value) {
      return { ok: false, error: '没有可重新生成的指令' }
    }

    const savedReview = review.value
      ? {
          oldText: review.value.oldText,
          newText: review.value.newText,
          command: review.value.command,
          lockFrom: review.value.lockFrom,
          lockTo: review.value.lockTo,
          operation: review.value.operation || 'replace',
        }
      : null

    const savedOldText =
      savedReview?.oldText || frozenAnchor.value?.text || getStickyRange()?.text || ''
    const cmd = lastCommand.value || savedReview?.command || ''
    const op = savedReview?.operation || 'replace'

    if (!cmd.trim()) {
      return { ok: false, error: '没有可重新生成的指令' }
    }

    // Cursor 式：立刻清掉旧 Diff，进入思考态
    regenerating.value = true
    thinkingLog.value = '正在重新生成修改方案…\n'
    removePreviewInsert()
    clearMarksInEditor(ed, REVIEW_MARKS)
    review.value = null
    aiState.value = 'thinking'

    let locked: LockedRange | null =
      resolveActiveAnchor(savedOldText) || getStickyRange()
    if (!locked && savedOldText.trim()) {
      locked = locateByText(savedOldText)
    }
    if (!locked && savedReview && savedReview.lockFrom <= savedReview.lockTo) {
      locked = {
        from: savedReview.lockFrom,
        to: savedReview.lockTo,
        text: savedOldText || savedReview.oldText,
      }
      stickyRange.value = locked
      frozenAnchor.value = cloneAnchor(locked)
    }
    if (!locked) {
      regenerating.value = false
      thinkingLog.value = ''
      aiState.value = getStickyRange() ? 'selected' : 'idle'
      return { ok: false, error: '选区已失效，请重新描述修改位置' }
    }

    regenerateCount.value += 1
    const savedCount = regenerateCount.value
    const temperature = 0.5 + regenerateCount.value * 0.15

    const doc = ed.getText({ blockSeparator: DOC_BLOCK_SEPARATOR })
    const sel = locked.text ?? ''

    try {
      if (op === 'delete') {
        const revision: RevisionResult = {
          old_text: locked.text,
          options: [{ id: 'opt1', label: '删除', text: '' }],
          reason: '重新确认删除',
          operation: 'delete',
        }
        const shown = showInlineReview(locked.text, '', cmd, locked, 'delete')
        if (!shown) throw new Error('无法在文档中展示删除预览')
        regenerateCount.value = savedCount
        lastCommand.value = cmd
        thinkingLog.value = ''
        aiState.value = 'reviewing'
        return { ok: true, revision }
      }

      const rev = await processRevision(
        doc,
        sel,
        cmd,
        chatHistory.value,
        (chunk) => {
          thinkingLog.value += chunk
        },
        { temperature },
      )
      const revOp = inferRevisionOperation({ ...rev, old_text: rev.old_text || locked.text })
      const option = rev.options?.[0]
      const merged: RevisionResult = {
        ...rev,
        old_text: rev.old_text || locked.text,
        operation: rev.operation || revOp,
      }

      if (revOp === 'insert') {
        if (!option?.text?.trim()) throw new Error('未返回修改方案')
        const shown = showInsertReview(
          option.text,
          cmd,
          locked,
          rev.insert_anchor,
          rev.insert_position || 'end',
        )
        if (!shown) throw new Error('无法在文档中展示修改预览')
      } else {
        if (!option?.text && option?.text !== '') throw new Error('未返回修改方案')
        const shown = showInlineReview(
          locked.text,
          option?.text ?? '',
          cmd,
          locked,
          revOp === 'delete' ? 'delete' : 'replace',
        )
        if (!shown) throw new Error('无法在文档中展示修改预览')
      }

      regenerateCount.value = savedCount
      lastCommand.value = cmd
      thinkingLog.value = ''
      aiState.value = 'reviewing'
      return { ok: true, revision: merged }
    } catch (err) {
      thinkingLog.value = ''
      if (savedReview) {
        showInlineReview(
          savedReview.oldText,
          savedReview.newText,
          savedReview.command,
          { from: savedReview.lockFrom, to: savedReview.lockTo, text: savedOldText || savedReview.oldText },
          savedReview.operation,
        )
        aiState.value = 'reviewing'
      } else {
        restoreStickyVisual()
        aiState.value = getStickyRange() ? 'selected' : 'idle'
      }
      regenerateCount.value = Math.max(0, savedCount - 1)
      const msg = err instanceof Error ? err.message : String(err)
      return { ok: false, error: msg }
    } finally {
      regenerating.value = false
    }
  }

  function getDiffAnchorRect(): DOMRect | null {
    const ed = getEd()
    if (!ed || !review.value) return getLockedRect()

    const pos = Math.min(review.value.lockFrom, ed.state.doc.content.size)
    const coords = ed.view.coordsAtPos(pos)
    const body = ed.view.dom.closest('.writing-body') as HTMLElement | null
    const topBound = body?.getBoundingClientRect().top ?? 0
    const bottomBound = body?.getBoundingClientRect().bottom ?? window.innerHeight

    let top = coords.bottom + 6
    if (coords.top < topBound) top = topBound + 8
    if (coords.bottom > bottomBound - 44) top = bottomBound - 44

    return new DOMRect(coords.left, top, 300, 40)
  }

  function getLockedRect(): DOMRect | null {
    const ed = getEd()
    if (!ed) return null

    let locked = getStickyRange()
    if (!locked && canChangeSelection()) {
      const { from, to } = ed.state.selection
      if (from !== to) {
        locked = setStickyRange(from, to)
      }
    }
    if (!locked && frozenAnchor.value) {
      locked = frozenAnchor.value
    }
    if (!locked) return null

    const start = ed.view.coordsAtPos(locked.from)
    const end = ed.view.coordsAtPos(Math.min(Math.max(locked.to, locked.from + 1), ed.state.doc.content.size))
    return new DOMRect(
      start.left,
      start.top,
      Math.max(end.right - start.left, 8),
      Math.max(end.bottom - start.top, 20),
    )
  }

  function canChangeSelection() {
    return aiState.value !== 'reviewing' && aiState.value !== 'thinking'
  }

  function onSelectionUpdate() {
    if (!canChangeSelection()) return
    const ed = getEd()
    if (!ed) return
    const { from, to } = ed.state.selection
    if (from !== to) {
      setStickyRange(from, to)
    }
    syncAiState()
  }

  function onDocumentUpdate() {
    if (review.value) return
    validateAfterDocChange()
    syncAiState()
  }

  function onEditorMouseUp() {
    requestAnimationFrame(() => {
      handleMouseUp(canChangeSelection)
      syncAiState()
    })
  }

  function onEditorClick(pos: number) {
    const cleared = handleEditorClick(pos, canChangeSelection)
    syncAiState()
    return cleared
  }

  function onEditorBlur() {
    handleBlur()
    syncAiState()
  }

  function locateText(text: string): boolean {
    return locateByText(text) !== null
  }

  function getLockedText(): string {
    return getStickyRange()?.text ?? ''
  }

  return {
    aiState,
    review,
    revisionHistory,
    chatHistory,
    stickyRange,
    regenerateCount,
    regenerating,
    lastCommand,
    thinkingLog,
    lockSelection,
    getLockedRange,
    getLockedText,
    clearLock,
    getLockedRect,
    getDiffAnchorRect,
    showInlineReview,
    showReviewFromResult,
    applyRevisionResult,
    captureSelectionAnchor,
    acceptReview,
    rejectReview,
    regenerateCommand,
    cancelThinking,
    submitCommand,
    submitRiskScan,
    applyReplacement,
    onSelectionUpdate,
    onDocumentUpdate,
    onEditorMouseUp,
    onEditorClick,
    onEditorBlur,
    getFullText: () => getEd()?.getText({ blockSeparator: DOC_BLOCK_SEPARATOR }) ?? '',
    locateText,
    locateByParagraphIndex,
    prepareAgentTarget,
  }
}
