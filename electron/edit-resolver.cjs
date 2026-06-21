const { findTargetText } = require('./llm.cjs')
const { findInDocument } = require('./text-match.cjs')
const { parseJson } = require('./utils.cjs')
const {
  formatOutline,
  rankParagraphs,
  verifyTargetText,
  resolveTargetFromParagraphIndex,
  buildLocateClarifyQuestion,
  parseParagraphHint,
  extractQuotedText,
} = require('./doc-index.cjs')

const DELETE_PATTERNS = [/删/, /去掉/, /移除/, /去除/, /删除/]
const INSERT_PATTERNS = [/新增/, /增加/, /添加/, /补充/, /插入/, /加上/, /写一段/, /加一段/]

function detectLocalAction(command) {
  const text = command.trim()
  if (DELETE_PATTERNS.some((p) => p.test(text))) return 'delete'
  if (INSERT_PATTERNS.some((p) => p.test(text))) return 'insert'
  return 'replace'
}

function tryLocalResolve(documentText, command) {
  const { paragraphs, ranked } = rankParagraphs(documentText, command)
  if (paragraphs.length === 0) return null

  const quoted = extractQuotedText(command)
  if (quoted) {
    const found = findInDocument(documentText, quoted)
    if (found) {
      return {
        action: detectLocalAction(command),
        target_text: found.matchedText,
        confidence: 'quote',
        reason: '根据您引号中的原文定位',
      }
    }
  }

  const hint = parseParagraphHint(command)
  if (hint) {
    const para = paragraphs[hint - 1]
    if (para) {
      return {
        action: detectLocalAction(command),
        target_text: para.text,
        paragraph_index: hint,
        confidence: 'paragraph-hint',
        reason: `定位到第 ${hint} 段`,
      }
    }
  }

  const top = ranked[0]
  const second = ranked[1]
  if (top && top.score >= 60 && (!second || top.score - second.score >= 20)) {
    return {
      action: detectLocalAction(command),
      target_text: top.text,
      paragraph_index: top.index,
      confidence: 'local-score',
      reason: `根据关键词匹配到第 ${top.index} 段`,
    }
  }

  return { paragraphs, ranked, localFallback: findTargetText(documentText, '', command) }
}

async function resolveEditTarget(settings, callChat, documentText, selectedText, command, history, knowledgeBase) {
  const selected = selectedText?.trim()
  if (selected) {
    return {
      action: detectLocalAction(command),
      target_text: selected,
      confidence: 'selection',
    }
  }

  const doc = documentText?.trim() || ''
  if (!doc) {
    if (INSERT_PATTERNS.some((p) => p.test(command))) {
      return { action: 'insert', target_text: '', insert_position: 'start', confidence: 'empty-doc' }
    }
    return {
      action: 'clarify',
      clarify_question: '当前文档为空。请说明要新增的内容，或先在编辑器中输入文稿后再修改。',
      confidence: 'empty-doc',
    }
  }

  const localTry = tryLocalResolve(doc, command)
  if (localTry?.target_text && localTry.confidence !== undefined && !localTry.paragraphs) {
    const verified = verifyTargetText(doc, localTry.target_text, localTry.paragraph_index, rankParagraphs(doc, command).paragraphs)
    if (verified?.unique !== false) {
      return { ...localTry, target_text: verified?.matchedText || localTry.target_text }
    }
  }

  const { paragraphs, ranked } = localTry?.paragraphs
    ? localTry
    : rankParagraphs(doc, command)

  if (!settings.useApi || !settings.apiKey) {
    const fallback = localTry?.localFallback || findTargetText(doc, '', command)
    if (fallback) {
      return {
        action: detectLocalAction(command),
        target_text: fallback,
        confidence: 'offline',
      }
    }
    const clarify = buildLocateClarifyQuestion(ranked)
    return {
      action: 'clarify',
      clarify_question: clarify.question,
      candidates: clarify.candidates,
      confidence: 'offline',
    }
  }

  const historyBlock = history.length
    ? `对话上下文：\n${history.slice(-8).map((h) => `${h.role}: ${h.content}`).join('\n')}\n\n`
    : ''

  const kbPrefix = knowledgeBase?.trim()
    ? `知识库：\n---\n${knowledgeBase.trim()}\n---\n\n`
    : ''

  const outline = formatOutline(paragraphs)

  const prompt = `你是 Cursor 风格的文稿编辑定位助手。先准确判断用户要改文档的哪一段，再输出 JSON（只输出 JSON）：
{
  "action": "replace|insert|delete|qa|clarify",
  "paragraph_index": 1,
  "target_text": "必须从对应段落中逐字复制的原文（可整段或其中连续片段）",
  "insert_after_text": "插入锚点（insert 时）",
  "insert_position": "start|end|after_anchor",
  "clarify_question": "中文追问（action=clarify 时）",
  "reason": "一句话说明为何选该段"
}

规则：
1. 优先用 paragraph_index 选段，target_text 必须来自该段原文
2. 用户说「第 N 段 / 标题 / 目标 / 保障措施 / 结尾」等，对照段落索引表
3. 用户引号内原文 → target_text 用引号内文字
4. 删除 → delete；新增 → insert；修改润色 → replace
5. 纯问答 → qa
6. 多个段落都可能且无法判断 → clarify，并在 clarify_question 里列出候选段号
7. target_text 不要编造，必须能在文稿中找到`

  try {
    const content = await callChat(
      settings,
      [
        { role: 'system', content: prompt },
        {
          role: 'user',
          content: `${kbPrefix}${historyBlock}【段落索引表】\n${outline}\n\n【全文】\n---\n${doc.slice(0, 14000)}\n---\n\n【用户指令】\n${command}`,
        },
      ],
      { json: true },
    )

    const parsed = parseJson(content, '编辑定位 JSON')

    const action = parsed.action || 'replace'

    if (action === 'clarify') {
      return {
        action: 'clarify',
        clarify_question: parsed.clarify_question || '请说明要修改第几段，或选中文字。',
        candidates: ranked.slice(0, 3).map((p) => ({ index: p.index, preview: p.preview })),
        reason: parsed.reason,
      }
    }

    if (action === 'qa') {
      return { action: 'qa', reason: parsed.reason }
    }

    const paragraphIndex = parseInt(parsed.paragraph_index, 10) || parseParagraphHint(command) || null
    let targetText = parsed.target_text?.trim() || ''

    if (action === 'insert') {
      let insertAfter = parsed.insert_after_text?.trim() || ''
      if (insertAfter && !doc.includes(insertAfter)) {
        const f = findInDocument(doc, insertAfter)
        if (f) insertAfter = f.matchedText
      }
      if (paragraphIndex && !insertAfter) {
        const para = paragraphs[paragraphIndex - 1]
        if (para) insertAfter = para.text.slice(-Math.min(40, para.text.length))
      }
      return {
        action: 'insert',
        target_text: '',
        insert_after_text: insertAfter,
        insert_position: parsed.insert_position || (paragraphIndex ? 'after_anchor' : 'end'),
        paragraph_index: paragraphIndex,
        reason: parsed.reason,
        confidence: 'llm',
      }
    }

    if (paragraphIndex && paragraphs[paragraphIndex - 1]) {
      targetText = resolveTargetFromParagraphIndex(paragraphs, paragraphIndex, targetText)
    } else if (targetText) {
      const found = findInDocument(doc, targetText)
      if (found) targetText = found.matchedText
    } else {
      const fallback = findTargetText(doc, '', command)
      if (fallback) targetText = fallback
    }

    if (action === 'delete') {
      if (!targetText) {
        const clarify = buildLocateClarifyQuestion(ranked)
        return { action: 'clarify', ...clarify }
      }
      const paragraph = paragraphIndex ? paragraphs[paragraphIndex - 1] : null
      if (paragraph && targetText.length < paragraph.text.length * 0.45 && !extractQuotedText(command)) {
        return {
          action: 'delete',
          target_text: paragraph.text,
          paragraph_index: paragraphIndex,
          confidence: 'paragraph-confirmed',
          reason: '删除指令已按段落索引确认整段删除',
        }
      }
      const verified = verifyTargetText(doc, targetText, paragraphIndex, paragraphs)
      if (!verified) {
        if (paragraphIndex && paragraphs[paragraphIndex - 1]) {
          return {
            action: 'delete',
            target_text: paragraphs[paragraphIndex - 1].text,
            paragraph_index: paragraphIndex,
            confidence: 'paragraph-fallback',
            reason: 'LLM 定位文本与原文不匹配，已按段落索引兜底',
          }
        }
        const clarify = buildLocateClarifyQuestion(ranked)
        return {
          action: 'clarify',
          clarify_question: `无法在文档中找到「${targetText.slice(0, 30)}…」，请选中要删除的文字，或说明「第几段」。`,
          candidates: clarify.candidates,
        }
      }
      if (verified.unique === false) {
        const clarify = buildLocateClarifyQuestion(ranked)
        return {
          action: 'clarify',
          clarify_question: `「${targetText.slice(0, 30)}…」在文中出现多处。${clarify.question}`,
          candidates: clarify.candidates,
        }
      }
      return {
        action: 'delete',
        target_text: verified.matchedText,
        paragraph_index: paragraphIndex,
        reason: parsed.reason,
        confidence: verified.confidence || 'llm',
      }
    }

    if (!targetText) {
      const clarify = buildLocateClarifyQuestion(ranked)
      return { action: 'clarify', ...clarify, reason: parsed.reason }
    }

    const verified = verifyTargetText(doc, targetText, paragraphIndex, paragraphs)
    if (!verified) {
      const clarify = buildLocateClarifyQuestion(ranked)
      return { action: 'clarify', ...clarify }
    }

    if (verified.unique === false) {
      const clarify = buildLocateClarifyQuestion(ranked)
      return {
        action: 'clarify',
        clarify_question: `定位到的文字在文中出现 ${verified.occurrences || '多'} 次，请确认段落：\n${clarify.candidates.map((c) => `第 ${c.index} 段：${c.preview}`).join('\n')}`,
        candidates: clarify.candidates,
      }
    }

    return {
      action: 'replace',
      target_text: verified.matchedText,
      paragraph_index: paragraphIndex || verified.paragraphIndex,
      reason: parsed.reason,
      confidence: verified.confidence || 'llm',
    }
  } catch {
    const top = ranked[0]
    if (top?.score >= 50) {
      return {
        action: detectLocalAction(command),
        target_text: top.text,
        paragraph_index: top.index,
        confidence: 'fallback-score',
        reason: `已按关键词匹配到第 ${top.index} 段`,
      }
    }
    const clarify = buildLocateClarifyQuestion(ranked)
    return { action: 'clarify', ...clarify, confidence: 'fallback' }
  }
}

module.exports = { resolveEditTarget, detectLocalAction }
