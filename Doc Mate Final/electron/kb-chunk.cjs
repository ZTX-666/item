const CHUNK_SYSTEM = `你是一个文档分析专家。请将以下文档按语义主题切分为独立的知识块。
每个知识块应该是完整、自包含的信息单元，方便后续检索。

输出 JSON 格式：
{
  "chunks": [
    {
      "title": "知识块标题（简短概括，10字以内）",
      "keywords": ["关键词1", "关键词2", "关键词3"],
      "summary": "一句话概括此块核心内容（50字以内）",
      "content": "完整原文内容（必须保持原文，不得改写、缩写或省略）"
    }
  ]
}

切分规则：
1. 每个知识块聚焦一个主题/要点，保持语义完整
2. content 必须保留原文，逐字不差，不得改写或省略
3. keywords 提取 3-8 个专业术语或核心词
4. summary 不超过 50 字
5. 单个知识块 content 控制在 200-600 字之间
6. 如果原文本身不足 600 字，可以只输出 1 个 chunk
7. 如果某个段落超过 600 字且包含多个主题，应拆分为多个 chunk
8. 只输出 JSON，不要输出其他内容`

const { parseJson } = require('./utils.cjs')

function mechanicalSplit(content, docName) {
  const parts = content
    .split(/\n{2,}|(?=^[一二三四五六七八九十]+、)|(?=^\d+[.．、])/m)
    .map((p) => p.trim())
    .filter(Boolean)

  if (!parts.length) {
    return [{ title: docName.slice(0, 10) || '文档', keywords: [], summary: '', content: content.trim() }]
  }

  return parts.map((part, i) => ({
    title: part.slice(0, 10) || `片段${i + 1}`,
    keywords: [],
    summary: part.slice(0, 50),
    content: part,
  }))
}

function splitIntoBatches(text, maxLength = 8000, overlap = 200) {
  const blocks = text
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter(Boolean)
  const batches = []
  let current = ''

  for (const block of blocks.length ? blocks : text.split('\n')) {
    const next = current ? `${current}\n\n${block}` : block
    if (next.length > maxLength && current.trim()) {
      batches.push(current.trim())
      const tail = current.slice(Math.max(0, current.length - overlap))
      current = `${tail}\n\n${block}`
    } else {
      current = next
    }
  }
  if (current.trim()) batches.push(current.trim())
  return batches
}

async function chunkBatch(callChat, settings, docName, batchText, signal) {
  const content = await callChat(
    settings,
    [
      { role: 'system', content: CHUNK_SYSTEM },
      { role: 'user', content: `请切分以下文档：\n\n文档名称：${docName}\n---\n${batchText}\n---` },
    ],
    { json: true, temperature: 0.2, signal },
  )
  const parsed = parseJson(content, '知识库切块 JSON')
  if (!Array.isArray(parsed.chunks) || !parsed.chunks.length) {
    throw new Error('切分结果为空')
  }
  return parsed.chunks
}

async function chunkDocument(callChat, settings, docName, content, signal, onProgress) {
  const text = String(content || '').trim()
  if (!text) throw new Error('文档内容为空')

  if (text.length <= 10000) {
    try {
      onProgress?.({ current: 1, total: 1, message: '正在切分第 1/1 批' })
      return await chunkBatch(callChat, settings, docName, text, signal)
    } catch {
      return mechanicalSplit(text, docName)
    }
  }

  const batches = splitIntoBatches(text)

  const merged = []
  for (const [index, batch] of batches.entries()) {
    onProgress?.({ current: index + 1, total: batches.length, message: `正在切分第 ${index + 1}/${batches.length} 批` })
    try {
      const chunks = await chunkBatch(callChat, settings, docName, batch, signal)
      merged.push(...chunks)
    } catch {
      merged.push(...mechanicalSplit(batch, docName))
    }
  }
  return merged.length ? merged : mechanicalSplit(text, docName)
}

module.exports = { chunkDocument, mechanicalSplit, splitIntoBatches }
