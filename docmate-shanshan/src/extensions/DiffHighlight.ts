import { Mark, mergeAttributes } from '@tiptap/core'

export const DiffDeletion = Mark.create({
  name: 'diffDeletion',
  parseHTML() {
    return [{ tag: 'span[data-diff-deletion]' }]
  },
  renderHTML({ HTMLAttributes }) {
    return [
      'span',
      mergeAttributes(HTMLAttributes, {
        'data-diff-deletion': '',
        class: 'diff-deletion',
      }),
      0,
    ]
  },
})

export const DiffInsertion = Mark.create({
  name: 'diffInsertion',
  parseHTML() {
    return [{ tag: 'span[data-diff-insertion]' }]
  },
  renderHTML({ HTMLAttributes }) {
    return [
      'span',
      mergeAttributes(HTMLAttributes, {
        'data-diff-insertion': '',
        class: 'diff-insertion',
      }),
      0,
    ]
  },
})
