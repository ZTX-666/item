import { Extension } from '@tiptap/core'
import { Plugin, PluginKey } from '@tiptap/pm/state'
import { Decoration, DecorationSet } from '@tiptap/pm/view'

export interface StickyHighlightRange {
  from: number
  to: number
}

export const stickyHighlightKey = new PluginKey<DecorationSet>('stickySelectionHighlight')

export const StickySelectionHighlight = Extension.create({
  name: 'stickySelectionHighlight',

  addCommands() {
    return {
      setStickyHighlight:
        (from: number, to: number) =>
        ({ tr, dispatch }) => {
          if (from >= to) return false
          if (dispatch) {
            dispatch(
              tr.setMeta(stickyHighlightKey, {
                from,
                to,
              } satisfies StickyHighlightRange),
            )
          }
          return true
        },
      clearStickyHighlight:
        () =>
        ({ tr, dispatch }) => {
          if (dispatch) dispatch(tr.setMeta(stickyHighlightKey, null))
          return true
        },
    }
  },

  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: stickyHighlightKey,
        state: {
          init: () => DecorationSet.empty,
          apply(tr, oldSet) {
            const meta = tr.getMeta(stickyHighlightKey) as StickyHighlightRange | null | undefined
            if (meta === null) return DecorationSet.empty
            if (meta && meta.from < meta.to) {
              return DecorationSet.create(tr.doc, [
                Decoration.inline(meta.from, meta.to, { class: 'sticky-selection-deco' }),
              ])
            }
            return oldSet.map(tr.mapping, tr.doc)
          },
        },
        props: {
          decorations(state) {
            return stickyHighlightKey.getState(state) ?? DecorationSet.empty
          },
        },
      }),
    ]
  },
})

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    stickySelectionHighlight: {
      setStickyHighlight: (from: number, to: number) => ReturnType
      clearStickyHighlight: () => ReturnType
    }
  }
}
