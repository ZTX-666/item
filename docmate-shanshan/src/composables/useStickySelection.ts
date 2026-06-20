import { ref, type Ref } from 'vue'
import type { Editor } from '@tiptap/vue-3'
import { findRangeInDocument, DOC_BLOCK_SEPARATOR } from '@/utils/textMatch'

export interface StickyRange {
  from: number
  to: number
  text: string
}

export function useStickySelection(editor: Ref<Editor | undefined>) {
  const stickyRange = ref<StickyRange | null>(null)
  let pendingVisual: ReturnType<typeof requestAnimationFrame> | null = null
  let lastVisualKey = ''

  function getEd() {
    return editor.value
  }

  function visualKey(from: number, to: number) {
    return `${from}:${to}`
  }

  function applyVisual(from: number, to: number) {
    const ed = getEd()
    if (!ed || from > to) return

    const key = visualKey(from, to)
    if (key === lastVisualKey) return
    lastVisualKey = key

    if (from === to) {
      ed.commands.setStickyHighlight(from, from)
    } else {
      ed.commands.setStickyHighlight(from, to)
    }
  }

  function clearVisual() {
    lastVisualKey = ''
    getEd()?.commands.clearStickyHighlight()
  }

  function scheduleVisual(from: number, to: number) {
    if (pendingVisual !== null) cancelAnimationFrame(pendingVisual)
    pendingVisual = requestAnimationFrame(() => {
      pendingVisual = null
      applyVisual(from, to)
    })
  }

  function setStickyRange(from: number, to: number): StickyRange | null {
    const ed = getEd()
    if (!ed || from > to) return null

    const text = ed.state.doc.textBetween(from, to, DOC_BLOCK_SEPARATOR)
    if (!text.trim() && from === to) return null
    if (!text.trim()) return null

    if (
      stickyRange.value?.from === from &&
      stickyRange.value?.to === to &&
      stickyRange.value?.text === text
    ) {
      return stickyRange.value
    }

    stickyRange.value = { from, to, text }
    scheduleVisual(from, to)
    return stickyRange.value
  }

  /** 文本锚优先：先用保存的 text 在文档中查找，再回退坐标 */
  function getStickyRange(): StickyRange | null {
    const ed = getEd()
    if (!ed || !stickyRange.value) return null

    const { from, to, text } = stickyRange.value

    if (text.trim()) {
      const recovered = findRangeInDocument(ed.state.doc, text)
      if (recovered) {
        if (
          recovered.from !== from ||
          recovered.to !== to ||
          recovered.text !== stickyRange.value.text
        ) {
          stickyRange.value = recovered
          scheduleVisual(recovered.from, recovered.to)
        }
        return stickyRange.value
      }
    }

    if (to > ed.state.doc.content.size) {
      stickyRange.value = null
      clearVisual()
      return null
    }

    const current = ed.state.doc.textBetween(from, to, DOC_BLOCK_SEPARATOR)
    if (!current && text.trim()) {
      stickyRange.value = null
      clearVisual()
      return null
    }

    if (current && current !== text) {
      stickyRange.value = { from, to, text: current }
    }
    return stickyRange.value
  }

  function restoreStickyVisual() {
    const range = getStickyRange()
    if (!range) return null
    scheduleVisual(range.from, range.to)
    return range
  }

  function clearStickyRange() {
    stickyRange.value = null
    clearVisual()
  }

  function validateAfterDocChange() {
    if (!stickyRange.value) return null
    return getStickyRange()
  }

  function handleMouseUp(canChange: () => boolean) {
    if (!canChange()) return
    const ed = getEd()
    if (!ed) return

    const { from, to } = ed.state.selection
    if (from !== to) {
      setStickyRange(from, to)
    }
  }

  function handleEditorClick(pos: number, canChange: () => boolean): boolean {
    if (!canChange()) return false

    const range = getStickyRange()
    if (!range) return false

    if (pos >= range.from && pos <= range.to) {
      clearStickyRange()
      getEd()?.chain().setTextSelection(pos).run()
      return true
    }

    return false
  }

  function handleBlur() {
    restoreStickyVisual()
  }

  function locateByText(text: string): StickyRange | null {
    const ed = getEd()
    if (!ed) return null
    const found = findRangeInDocument(ed.state.doc, text)
    if (!found) return null
    stickyRange.value = found
    scheduleVisual(found.from, found.to)
    ed.chain().focus().setTextSelection({ from: found.from, to: found.to }).scrollIntoView().run()
    return found
  }

  return {
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
  }
}
