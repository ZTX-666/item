function normalizeText(text) {
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

function findInDocument(documentText, searchText) {
  if (!searchText?.trim()) return null

  const attempts = [
    searchText,
    searchText.trim(),
    normalizeText(searchText),
  ]

  const unique = [...new Set(attempts.filter(Boolean))]

  for (const candidate of unique) {
    const index = documentText.indexOf(candidate)
    if (index !== -1) {
      return { matchedText: candidate, index, confidence: 'exact' }
    }
  }

  const normalizedDoc = normalizeText(documentText)
  for (const candidate of unique) {
    const normalizedCandidate = normalizeText(candidate)
    const index = normalizedDoc.indexOf(normalizedCandidate)
    if (index !== -1) {
      return recoverOriginalSpan(documentText, normalizedDoc, index, normalizedCandidate.length)
    }
  }

  const meaningfulParts = unique
    .flatMap((candidate) => normalizeText(candidate).split(/[，。；、,.!?！？;：:\s]+/))
    .map((p) => p.trim())
    .filter((p) => p.length >= 8)
    .sort((a, b) => b.length - a.length)

  for (const part of meaningfulParts.slice(0, 8)) {
    const index = normalizedDoc.indexOf(part)
    if (index !== -1) {
      const recovered = recoverOriginalSpan(documentText, normalizedDoc, index, part.length)
      if (recovered) return { ...recovered, confidence: 'substring' }
    }
  }

  return null
}

function recoverOriginalSpan(original, normalized, normIndex, normLength) {
  let oi = 0
  let ni = 0
  let start = -1
  let end = -1

  while (oi < original.length && ni <= normIndex + normLength) {
    const ch = original[oi]
    const normChunk = normalizeText(ch)
    if (normChunk.length === 0) {
      oi += 1
      continue
    }
    if (ni === normIndex && start === -1) start = oi
    ni += normChunk.length
    if (ni >= normIndex + normLength && end === -1) {
      end = oi + 1
      break
    }
    oi += 1
  }

  if (start === -1 || end === -1) return null
  const matchedText = original.slice(start, end)
  return { matchedText, index: start, confidence: 'fuzzy' }
}

function alignOldText(documentText, oldText) {
  if (!oldText?.trim()) return oldText
  if (documentText.includes(oldText)) return oldText

  const found = findInDocument(documentText, oldText)
  if (found) return found.matchedText
  return oldText
}

module.exports = { normalizeText, findInDocument, alignOldText }
