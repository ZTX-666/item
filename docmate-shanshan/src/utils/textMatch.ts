export function normalizeText(text: string): string {
  return text
    .replace(/\uFEFF/g, '')
    .replace(/[\u200B-\u200D\u2060]/g, '')
    .replace(/[\uFF01-\uFF5E]/g, (ch) => String.fromCharCode(ch.charCodeAt(0) - 0xfee0))
    .replace(/[\u2018\u2019]/g, "'")
    .replace(/[\u201C\u201D]/g, '"')
    .replace(/[\u2013\u2014]/g, '-')
    .replace(/\s+/g, ' ')
    .trim()
}

export const DOC_BLOCK_SEPARATOR = '\n'

export interface TextMatchResult {
  from: number
  to: number
  matchedText: string
  confidence: 'exact' | 'trim' | 'normalized' | 'fuzzy'
}

export interface DocTextRange {
  from: number
  to: number
  text: string
}

type ProseDoc = {
  content: { size: number }
  textBetween: (from: number, to: number, blockSeparator?: string) => string
  nodesBetween: (
    from: number,
    to: number,
    f: (
      node: { isBlock: boolean; isText: boolean; text?: string | null },
      pos: number,
    ) => void | boolean,
  ) => void
}

export function getDocumentPlainText(doc: ProseDoc, blockSeparator = DOC_BLOCK_SEPARATOR): string {
  return doc.textBetween(0, doc.content.size, blockSeparator)
}

export function mapPlainTextOffsetsToRange(
  doc: ProseDoc,
  textFrom: number,
  textTo: number,
  blockSeparator = DOC_BLOCK_SEPARATOR,
): { from: number; to: number } | null {
  const docFrom = 0
  const docTo = doc.content.size
  let textLen = 0
  let fromPos: number | null = null
  let toPos: number | null = null

  doc.nodesBetween(docFrom, docTo, (node, pos) => {
    if (node.isBlock && pos > docFrom) {
      textLen += blockSeparator.length
    }
    if (node.isText && node.text) {
      const nodeStart = textLen
      const nodeEnd = textLen + node.text.length

      if (fromPos === null && textFrom >= nodeStart && textFrom < nodeEnd) {
        fromPos = pos + (textFrom - nodeStart)
      }
      if (textTo > nodeStart && textTo <= nodeEnd) {
        toPos = pos + (textTo - nodeStart)
      }
      textLen = nodeEnd
    }
  })

  if (fromPos === null || toPos === null || toPos <= fromPos) return null
  return { from: fromPos, to: toPos }
}

export function findTextInDoc(
  docText: string,
  searchText: string,
  charOffset = 0,
): TextMatchResult | null {
  if (!searchText.trim()) return null

  const attempts: { text: string; confidence: TextMatchResult['confidence'] }[] = [
    { text: searchText, confidence: 'exact' },
    { text: searchText.trim(), confidence: 'trim' },
    { text: normalizeText(searchText), confidence: 'normalized' },
  ]

  for (const { text, confidence } of attempts) {
    const index = docText.indexOf(text)
    if (index !== -1) {
      return {
        from: charOffset + index,
        to: charOffset + index + text.length,
        matchedText: text,
        confidence,
      }
    }
  }

  const normalizedDoc = normalizeText(docText)
  const normalizedSearch = normalizeText(searchText)
  const normIndex = normalizedDoc.indexOf(normalizedSearch)
  if (normIndex === -1) return null

  let oi = 0
  let ni = 0
  let start = -1
  let end = -1

  while (oi < docText.length && ni <= normIndex + normalizedSearch.length) {
    const normChunk = normalizeText(docText[oi])
    if (normChunk.length === 0) {
      oi += 1
      continue
    }
    if (ni === normIndex && start === -1) start = oi
    ni += normChunk.length
    if (ni >= normIndex + normalizedSearch.length && end === -1) {
      end = oi + 1
      break
    }
    oi += 1
  }

  if (start === -1 || end === -1) return null
  return {
    from: charOffset + start,
    to: charOffset + end,
    matchedText: docText.slice(start, end),
    confidence: 'fuzzy',
  }
}

function findInPlainText(
  doc: ProseDoc,
  plain: string,
  searchText: string,
  blockSeparator: string,
): DocTextRange | null {
  const match = findTextInDoc(plain, searchText)
  if (!match) return null
  const range = mapPlainTextOffsetsToRange(doc, match.from, match.to, blockSeparator)
  if (!range) return null
  return { ...range, text: doc.textBetween(range.from, range.to, blockSeparator) || match.matchedText }
}

export function findRangeInDocument(
  doc: ProseDoc,
  searchText: string,
  extraCandidates: string[] = [],
): DocTextRange | null {
  if (!searchText.trim() && extraCandidates.every((t) => !t?.trim())) return null

  const candidates = [...new Set([searchText, ...extraCandidates].map((t) => t?.trim()).filter(Boolean))]

  for (const candidate of candidates) {
    for (const separator of [DOC_BLOCK_SEPARATOR, '\n\n']) {
      const plain = getDocumentPlainText(doc, separator)
      const found = findInPlainText(doc, plain, candidate, separator)
      if (found) return found
    }
  }

  return null
}
