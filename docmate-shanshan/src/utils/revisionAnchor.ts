import type { StickyRange } from '@/composables/useStickySelection'

export function cloneAnchor(range: StickyRange): StickyRange {
  return { from: range.from, to: range.to, text: range.text }
}

export function isValidAnchor(range: StickyRange | null | undefined, docSize: number): range is StickyRange {
  return !!range && range.from >= 0 && range.from <= range.to && range.to <= docSize
}
