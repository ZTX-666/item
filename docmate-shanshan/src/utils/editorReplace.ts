import type { Editor } from '@tiptap/vue-3'
import { findRangeInDocument, DOC_BLOCK_SEPARATOR } from '@/utils/textMatch'

export interface ReplaceRange {
  from: number
  to: number
  text: string
}

export function buildDiffInsertHtml(newText: string): string {
  if (!newText.includes('\n')) {
    return `<span data-diff-insertion="" class="diff-insertion">${escapeHtml(newText)}</span>`
  }
  return newText
    .split('\n')
    .map((line) =>
      `<p><span data-diff-insertion="" class="diff-insertion">${line ? escapeHtml(line) : '<br>'}</span></p>`,
    )
    .join('')
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function textToEditorContent(text: string): string {
  if (!text.includes('\n')) return text
  return text
    .split('\n')
    .map((line) => `<p>${line ? escapeHtml(line) : '<br>'}</p>`)
    .join('')
}

export function resolveReplaceRange(
  editor: Editor,
  preferredText: string,
  hint?: { from: number; to: number } | null,
): ReplaceRange | null {
  const text = preferredText?.trim()
  if (!text && !(hint && hint.from < hint.to)) return null

  const doc = editor.state.doc

  if (hint && hint.from < hint.to && hint.to <= doc.content.size) {
    const slice = doc.textBetween(hint.from, hint.to, DOC_BLOCK_SEPARATOR)
    if (slice.length > 0) {
      return { from: hint.from, to: hint.to, text: slice }
    }
  }

  if (text) {
    const found = findRangeInDocument(doc, text)
    if (found) return found
  }

  if (hint && hint.from < hint.to && hint.to <= doc.content.size) {
    const slice = doc.textBetween(hint.from, hint.to, DOC_BLOCK_SEPARATOR)
    if (slice.trim()) return { from: hint.from, to: hint.to, text: slice }
  }

  return null
}

export function replaceDocumentRange(
  editor: Editor,
  from: number,
  to: number,
  newText: string,
): boolean {
  const size = editor.state.doc.content.size
  if (from < 0 || to > size || from > to) return false

  if (from === to) {
    if (!newText?.trim()) return false
    const content = textToEditorContent(newText)
    return editor.chain().focus().insertContentAt(from, content, { updateSelection: false }).run()
  }

  if (!newText?.trim()) {
    return editor.chain().focus().deleteRange({ from, to }).run()
  }

  const content = textToEditorContent(newText)

  return editor
    .chain()
    .focus()
    .deleteRange({ from, to })
    .insertContentAt(from, content, { updateSelection: false })
    .run()
}

export function resolveInsertPosition(
  editor: Editor,
  anchorText?: string,
  position: 'start' | 'end' | 'after' = 'end',
): number | null {
  const doc = editor.state.doc
  const size = doc.content.size

  if (position === 'start') return Math.min(1, size)
  if (position === 'end' || !anchorText?.trim()) return Math.max(1, size - 1)

  const found = findRangeInDocument(doc, anchorText.trim())
  if (found) return found.to
  if (position === 'after') return Math.max(1, size - 1)
  return null
}

export function clearMarksInEditor(editor: Editor, names: string[]) {
  const { state } = editor
  const tr = state.tr
  let changed = false

  state.doc.descendants((node, pos) => {
    if (!node.isText) return
    for (const name of names) {
      const markType = state.schema.marks[name]
      if (!markType) continue
      if (node.marks.some((m) => m.type.name === name)) {
        tr.removeMark(pos, pos + node.nodeSize, markType)
        changed = true
      }
    }
  })

  if (changed) editor.view.dispatch(tr)
}
