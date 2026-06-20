import { Mark, mergeAttributes } from '@tiptap/core'

export const LockedSelection = Mark.create({
  name: 'lockedSelection',
  inclusive: false,
  parseHTML() {
    return [{ tag: 'span[data-locked-selection]' }]
  },
  renderHTML({ HTMLAttributes }) {
    return [
      'span',
      mergeAttributes(HTMLAttributes, {
        'data-locked-selection': '',
        class: 'locked-selection',
      }),
      0,
    ]
  },
})
