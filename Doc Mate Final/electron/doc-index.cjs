const { findInDocument, normalizeText } = require('./text-match.cjs')

const CN_NUM = {
  一: 1, 二: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9, 十: 10, 两: 2,
}

function splitParagraphs(documentText) {
  return (documentText || '')
    .split(/\n+/)
    .map((p) => p.trim())
    .filter(Boolean)
    .map((text, i) => ({
      index: i + 1,
      text,
      preview: text.length > 100 ? `${text.slice(0, 100)}…` : text,
      length: text.length,
    }))
}

function formatOutline(paragraphs, previewLen = 96) {
  if (paragraphs.length === 0) return '（文档无段落）'
  return paragraphs
    .map((p) => {
      const preview = p.text.length > previewLen ? `${p.text.slice(0, previewLen)}…` : p.text
      return `[${p.index}] ${preview}`
    })
    .join('\n')
}

function parseParagraphHint(command) {
  const m = command.match(/第([一二三四五六七八九十两\d]+)[段部分节条]/)
  if (!m) return null
  const token = m[1]
  if (CN_NUM[token] !== undefined) return CN_NUM[token]
  const n = parseInt(token, 10)
  return Number.isNaN(n) ? null : n
}

function extractQuotedText(command) {
  const patterns = [
    /[「『"'](.+?)[」』"']/,
    /【(.+?)】/,
    /《(.+?)》/,
  ]
  for (const p of patterns) {
    const m = command.match(p)
    if (m?.[1]?.trim()) return m[1].trim()
  }
  return null
}

function countOccurrences(haystack, needle) {
  if (!needle?.trim()) return 0
  let count = 0
  let pos = 0
  while (pos < haystack.length) {
    const idx = haystack.indexOf(needle, pos)
    if (idx === -1) break
    count += 1
    pos = idx + Math.max(1, needle.length)
  }
  return count
}

function scoreParagraph(command, paragraph, totalParagraphs) {
  let score = 0
  const cmd = command.trim()
  const text = paragraph.text

  const hint = parseParagraphHint(cmd)
  if (hint === paragraph.index) score += 120

  const sectionHints = [
    { keys: ['标题', '题目', '开头', '开篇'], index: 1, boost: 40 },
    { keys: ['目标'], boost: 35 },
    { keys: ['任务', '重点'], boost: 35 },
    { keys: ['保障', '措施'], boost: 35 },
    { keys: ['结尾', '最后', '总结', '结语'], last: true, boost: 40 },
  ]

  for (const rule of sectionHints) {
    if (!rule.keys.some((k) => cmd.includes(k))) continue
    if (rule.last) {
      // handled externally with paragraph count
      continue
    }
    if (rule.index === paragraph.index) score += rule.boost
    if (rule.keys.some((k) => text.includes(k))) score += 15
  }

  if (/结尾|最后|总结|结语/.test(cmd) && totalParagraphs && paragraph.index === totalParagraphs) {
    score += 50
  }

  const quote = extractQuotedText(cmd)
  if (quote) {
    if (text.includes(quote)) score += 100
    else if (normalizeText(text).includes(normalizeText(quote))) score += 85
  }

  // keyword overlap: 4+ char runs from command appearing in paragraph
  const chunks = cmd.match(/[\u4e00-\u9fff]{4,}/g) || []
  for (const chunk of chunks) {
    if (text.includes(chunk)) score += 20
  }

  const shortChunks = cmd.match(/[\u4e00-\u9fff]{2,3}/g) || []
  for (const chunk of shortChunks) {
    if (text.includes(chunk)) score += 8
  }

  if (text.length > 0 && cmd.length > 4) {
    const normCmd = normalizeText(cmd)
    const normText = normalizeText(text)
    if (normText.length > 20 && normCmd.includes(normText.slice(0, Math.min(24, normText.length)))) {
      score += 25
    }
  }

  return score
}

function rankParagraphs(documentText, command) {
  const paragraphs = splitParagraphs(documentText)
  if (paragraphs.length === 0) return { paragraphs, ranked: [] }

  const scored = paragraphs.map((p) => {
    const score = scoreParagraph(command, p, paragraphs.length)
    return { ...p, score }
  })

  scored.sort((a, b) => b.score - a.score)
  return { paragraphs, ranked: scored }
}

function getParagraph(paragraphs, index) {
  if (!index || index < 1 || index > paragraphs.length) return null
  return paragraphs[index - 1]
}

function verifyTargetText(documentText, targetText, paragraphIndex, paragraphs) {
  const para = getParagraph(paragraphs, paragraphIndex)

  if (!targetText?.trim()) {
    if (para) {
      return {
        matchedText: para.text,
        confidence: 'paragraph',
        unique: true,
        paragraphIndex,
      }
    }
    return null
  }

  let aligned = targetText.trim()
  if (!documentText.includes(aligned)) {
    const found = findInDocument(documentText, aligned)
    if (found) aligned = found.matchedText
  }

  if (!documentText.includes(aligned)) {
    if (para) {
      const inPara = findInDocument(para.text, aligned)
      if (inPara) {
        return {
          matchedText: inPara.matchedText,
          confidence: 'paragraph-fuzzy',
          unique: true,
          paragraphIndex,
        }
      }
    }
    return null
  }

  const total = countOccurrences(documentText, aligned)
  if (total === 1) {
    return {
      matchedText: aligned,
      confidence: 'unique',
      unique: true,
      paragraphIndex: para ? paragraphIndex : undefined,
    }
  }

  if (para) {
    const inPara = countOccurrences(para.text, aligned)
    if (inPara >= 1) {
      return {
        matchedText: aligned,
        confidence: 'paragraph-scoped',
        unique: true,
        paragraphIndex,
      }
    }
    if (para.text.includes(aligned) || normalizeText(para.text).includes(normalizeText(aligned))) {
      return {
        matchedText: aligned,
        confidence: 'paragraph-scoped',
        unique: true,
        paragraphIndex,
      }
    }
  }

  return {
    matchedText: aligned,
    confidence: 'ambiguous',
    unique: false,
    occurrences: total,
    paragraphIndex,
  }
}

function resolveTargetFromParagraphIndex(paragraphs, paragraphIndex, targetText) {
  const para = getParagraph(paragraphs, paragraphIndex)
  if (!para) return null

  if (!targetText?.trim()) return para.text

  if (para.text.includes(targetText.trim())) return targetText.trim()

  const found = findInDocument(para.text, targetText)
  if (found) return found.matchedText

  // LLM 给的 target 与段落不完全一致时，以整段为修改范围更安全
  return para.text
}

function buildLocateClarifyQuestion(ranked, max = 3) {
  const top = ranked.filter((p) => p.score > 0).slice(0, max)
  if (top.length === 0) {
    return {
      question: '无法确定要修改的位置。请选中文字，或说明「第几段 / 标题 / 关键词」。',
      candidates: ranked.slice(0, max).map((p) => ({ index: p.index, preview: p.preview })),
    }
  }
  const lines = top.map((p) => `第 ${p.index} 段：${p.preview}`).join('\n')
  return {
    question: `我找到了多个可能的位置，请确认要改哪一段（回复「第 N 段」或选中文字）：\n${lines}`,
    candidates: top.map((p) => ({ index: p.index, preview: p.preview })),
  }
}

module.exports = {
  splitParagraphs,
  formatOutline,
  parseParagraphHint,
  rankParagraphs,
  getParagraph,
  verifyTargetText,
  resolveTargetFromParagraphIndex,
  buildLocateClarifyQuestion,
  extractQuotedText,
}
