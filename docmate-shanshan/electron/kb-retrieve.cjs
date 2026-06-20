const SYNONYM_MAP = {
  安全保障: ['安全措施', '安全防护', '安全管理', '安全责任'],
  安全措施: ['安全保障', '安全防护', '安全管理'],
  人才: ['人力资源', '人员', '职工', '员工', '队伍建设'],
  人才引进: ['招聘', '引才', '人力资源', '队伍建设'],
  合规: ['合法', '规范性', '法规', '制度要求', '风险控制'],
  薪酬: ['工资', '待遇', '报酬', '薪资'],
  党建: ['党委', '党组织', '组织生活', '主题党日'],
  考核: ['绩效', '评价', '评估', '考评'],
  培训: ['学习', '培养', '赋能', '能力建设'],
}

function expandTerms(command) {
  const terms = new Set(command.match(/[\u4e00-\u9fff]{2,}/g) || [])
  for (const [term, aliases] of Object.entries(SYNONYM_MAP)) {
    if (command.includes(term) || aliases.some((a) => command.includes(a))) {
      terms.add(term)
      aliases.forEach((a) => terms.add(a))
    }
  }
  return [...terms]
}

function truncateBySentence(content, limit = 500) {
  const text = String(content || '').trim()
  if (text.length <= limit) return text
  const slice = text.slice(0, limit)
  const cut = Math.max(slice.lastIndexOf('。'), slice.lastIndexOf('；'), slice.lastIndexOf('\n'))
  return `${slice.slice(0, cut > 180 ? cut + 1 : limit)}…`
}

function retrieveChunks(command, allChunks, topK = 3) {
  if (!command?.trim() || !allChunks?.length) return []

  const cmdLower = command.toLowerCase()
  const cmdSegments = expandTerms(command)

  const scored = allChunks.map((chunk) => {
    let score = 0

    for (const kw of chunk.keywords || []) {
      if (command.includes(kw)) score += 20
      else if (cmdLower.includes(String(kw).toLowerCase())) score += 15
    }

    if (chunk.title && command.includes(chunk.title)) score += 25

    for (const seg of cmdSegments) {
      if (chunk.summary?.includes(seg)) score += 6
      if (chunk.title?.includes(seg)) score += 8
      if (seg.length >= 2 && chunk.content?.includes(seg)) score += seg.length >= 3 ? 4 : 2
    }

    if (chunk.doc_name && command.includes(chunk.doc_name)) score += 15

    return { ...chunk, score }
  })

  return scored
    .filter((c) => c.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, topK)
}

function kbContext(command, allChunks) {
  if (!allChunks?.length) return ''

  const relevant = retrieveChunks(command, allChunks, 3)
  if (!relevant.length) return ''

  const blocks = relevant.map((c) => {
    const content = truncateBySentence(c.content, 500)
    return `【${c.title}】（来源：${c.doc_name}）\n${content}`
  }).join('\n\n')

  return `以下是相关的知识库内容，请参考（仅参考，不要照搬）：\n---\n${blocks}\n---\n\n`
}

module.exports = { retrieveChunks, kbContext }
