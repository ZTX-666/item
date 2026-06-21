const { parseParagraphHint, rankParagraphs, getParagraph } = require('./doc-index.cjs')

function findTargetText(documentText, selectedText, command) {
  if (selectedText && selectedText.trim()) {
    return selectedText.trim()
  }

  const { paragraphs, ranked } = rankParagraphs(documentText, command)
  const hint = parseParagraphHint(command)
  if (hint && getParagraph(paragraphs, hint)) {
    return getParagraph(paragraphs, hint).text
  }

  const top = ranked[0]
  if (top && top.score >= 40) return top.text

  if (paragraphs.length > 0) return paragraphs[0].text
  return null
}

async function testLlmConnection(settings) {
  if (!settings.useApi) {
    return { ok: true, message: '当前为本地模拟模式，无需连接 API' }
  }
  if (!settings.apiKey) {
    return { ok: false, message: '请先填写 API Key' }
  }
  if (!settings.apiUrl) {
    return { ok: false, message: '请先填写 API 地址' }
  }

  try {
    const response = await fetch(settings.apiUrl, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${settings.apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: settings.model,
        messages: [{ role: 'user', content: '回复 OK' }],
        max_tokens: 5,
      }),
      signal: AbortSignal.timeout(15000),
    })

    if (response.ok) {
      return { ok: true, message: '连接成功！' }
    }
    const err = await response.text().catch(() => '')
    return { ok: false, message: `连接失败 (${response.status}): ${err.slice(0, 100)}` }
  } catch (e) {
    return { ok: false, message: `连接失败: ${e.message}` }
  }
}

module.exports = { testLlmConnection, findTargetText }
