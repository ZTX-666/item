const fs = require('fs')
const path = require('path')
const { findTargetText } = require('./llm.cjs')
const { alignOldText } = require('./text-match.cjs')
const { classifyIntent } = require('./intent-router.cjs')
const { resolveEditTarget } = require('./edit-resolver.cjs')
const { splitParagraphs } = require('./doc-index.cjs')
const { kbContext } = require('./kb-retrieve.cjs')
const { preferencePrefix } = require('./preference-engine.cjs')
const { parseJson } = require('./utils.cjs')
const { logger } = require('./logger.cjs')

function getKnowledgeBasePath(userDataPath) {
  return path.join(userDataPath, 'knowledge-base.txt')
}

function readKnowledgeBase(userDataPath) {
  const fp = getKnowledgeBasePath(userDataPath)
  try {
    return fs.readFileSync(fp, 'utf-8')
  } catch {
    return ''
  }
}

function writeKnowledgeBase(userDataPath, content) {
  fs.writeFileSync(getKnowledgeBasePath(userDataPath), content, 'utf-8')
}

function kbPrefix(knowledgeBase) {
  if (!knowledgeBase?.trim()) return ''
  return `以下是用户提供的文档规范/知识库，请严格遵守：\n---\n${knowledgeBase.trim()}\n---\n\n`
}

const SHANSHAN_ROLE_PROMPT = `你是「闪闪文档」的文稿修改助手，服务于中国建筑国际集团的人力部门和党建部门。

## 身份
你是公文写作辅助工具，不是内容创作者。你的职责是：根据用户的修改指令，对已有文字进行润色、精简、正式化、风格转换或风险检查，然后展示修改建议供用户决策。你不会自动替换原文。

## 核心原则
1. 人做决策：每次修改必须以 Diff 形式展示，由用户采纳或拒绝
2. 保留原意：修改的是表达方式，不改变原文的核心意思和事实
3. 合规优先：涉及人事制度、党建表述时，措辞必须符合现行法规和党内规范
4. 不编造：不添加原文没有的事实、数据或观点

## 人力部门场景
- 常见文档：人事通知、招聘启事、绩效考核文件、培训方案、制度修订稿、劳动合同补充条款
- 修改风格：正式、规范、体面，避免口语化和模糊表述
- 特殊注意：涉及薪酬、职级、考核结果时，措辞须严谨无歧义；不擅自添加或删除法律相关条款

## 党建部门场景
- 常见文档：党委文件、学习通知、组织生活方案、述职报告、民主生活会材料、思想汇报、主题党日活动方案
- 修改风格：政治站位高、表述严谨、符合党内公文规范，使用标准政治术语
- 特殊注意：涉及方针政策引用时，必须与官方原文一致，不得擅自改写；政治术语不可替换为口语化表达

## 修改指令响应规则
- 「改正式」→ 转为公文语体，消除口语和冗余
- 「精简」→ 删减冗余表述，保留核心信息，不删实质内容
- 「润色」→ 优化表达流畅度，提升文字质感
- 「改公文」→ 口语转标准公文格式和措辞
- 「风险检查」→ 检查合规风险、歧义表述、遗漏要素，列出风险点而非直接修改
- 「展开」→ 补充细节和论述，但不编造事实
- 自由指令 → 按用户意图执行，遵循上述原则

## 输出规则
- 修改类指令：按调用方要求输出 JSON，修改后的文字放在 options[0].text 中，不得输出额外解释
- 风险检查：输出风险列表，每条包含风险等级、原文位置或片段、问题描述、修改建议
- 不确定时：主动说明不确定之处，不猜测`

function withShanshanRolePrompt(prompt) {
  return `${SHANSHAN_ROLE_PROMPT}\n\n${prompt}`
}

function simulateRevision(original, command) {
  const lower = command.toLowerCase()
  if (lower.includes('正式') || lower.includes('严肃')) {
    return original
      .replace(/打造/g, '构建')
      .replace(/搞定/g, '完成')
      .replace(/差不多/g, '基本')
      .replace(/弄/g, '推进')
      .replace(/加大/g, '持续强化')
      .replace(/加强/g, '持续深化')
      .replace(/推进/g, '深入推进')
      .replace(/建设/g, '体系建设')
      .replace(/提升/g, '全面提升')
      .replace(/完善/g, '建立健全')
      .replace(/确保/g, '切实保障')
  }
  if (lower.includes('简洁') || lower.includes('精简') || lower.includes('短')) {
    return original
      .replace(/，特制定本工作方案.*/, '')
      .replace(/深入贯彻落实/g, '贯彻')
      .replace(/加快推进/g, '推进')
      .replace(/核心竞争力和可持续发展能力/g, '核心竞争力')
      .replace(/全面提升/g, '提升')
  }
  if (lower.includes('展开') || lower.includes('详细') || lower.includes('具体')) {
    return original.replace(/；/g, '；\n').replace(/一是/g, '第一，').replace(/二是/g, '第二，').replace(/三是/g, '第三，').replace(/四是/g, '第四，')
  }
  return original.replace(/加大/g, '持续加大').replace(/加强/g, '进一步加强').replace(/提升/g, '着力提升')
}

function buildPromptContext(command, aiContext, task = 'revise') {
  const allChunks = aiContext?.allChunks || []
  const preferences = aiContext?.preferences
  const legacyKb = aiContext?.legacyKnowledgeBase || ''
  const pref = preferencePrefix(preferences, task)
  const kb = allChunks.length ? kbContext(command || '', allChunks) : kbPrefix(legacyKb)
  return `${pref}${kb}`
}

function classifyError(err) {
  const msg = err?.message || String(err)
  if (msg.includes('fetch failed') || msg.includes('ECONNREFUSED') || msg.includes('ETIMEDOUT')) {
    return { type: 'network', message: '网络连接失败，请检查网络后重试', retryable: true }
  }
  if (msg.includes('401') || msg.includes('403') || msg.includes('API Key')) {
    return { type: 'auth', message: 'API Key 无效或未配置，请在设置中检查', retryable: false }
  }
  if (msg.includes('JSON') || msg.includes('格式')) {
    return { type: 'format', message: 'AI 返回格式异常，请重试或调整指令', retryable: true }
  }
  if (msg === 'NOT_FOUND') {
    return { type: 'not_found', message: '未找到要修改的内容。请选中文字，或说明具体段落（如「第二段」「标题」）。', retryable: false }
  }
  if (msg === 'NO_SELECTION') {
    return { type: 'not_found', message: '表格转换需要先选中文字。', retryable: false }
  }
  if (msg === 'MATCH_FAILED') {
    return { type: 'match', message: 'AI 定位的文字与原文有偏差，请手动确认后再替换', retryable: false }
  }
  return { type: 'unknown', message: msg, retryable: true }
}

async function callChat(settings, messages, options = {}) {
  const { json = false, stream = false, onChunk = null, temperature: tempOverride, signal } = options

  if (!settings.useApi || !settings.apiKey) {
    return simulateChat(settings, messages, { json, stream, onChunk, signal: options.signal })
  }

  const body = {
    model: settings.model,
    messages,
    temperature: tempOverride ?? (json ? 0.3 : 0.6),
  }
  if (json) body.response_format = { type: 'json_object' }
  if (stream) body.stream = true

  const fetchSignal = signal
    ? AbortSignal.any([signal, AbortSignal.timeout(90000)])
    : AbortSignal.timeout(90000)

  const response = await fetch(settings.apiUrl, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${settings.apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
    signal: fetchSignal,
  })

  if (!response.ok) {
    const errText = await response.text().catch(() => '')
    throw new Error(`API 调用失败 (${response.status}): ${errText.slice(0, 200)}`)
  }

  if (stream && onChunk) {
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let full = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const chunk = decoder.decode(value, { stream: true })
      for (const line of chunk.split('\n')) {
        if (!line.startsWith('data: ') || line.includes('[DONE]')) continue
        try {
          const data = JSON.parse(line.slice(6))
          const content = data.choices?.[0]?.delta?.content
          if (content) {
            full += content
            onChunk(content)
          }
        } catch { /* skip */ }
      }
    }
    return full
  }

  const data = await response.json()
  return data.choices?.[0]?.message?.content || ''
}

async function simulateChat(settings, messages, { json, stream, onChunk, signal }) {
  if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
  await new Promise((r) => setTimeout(r, 400 + Math.random() * 400))
  const lastUser = [...messages].reverse().find((m) => m.role === 'user')?.content || ''

  if (json) {
    if (lastUser.includes('风险') || lastUser.includes('risk')) {
      return JSON.stringify({
        risks: [
          { level: 'high', excerpt: '不低于营收的1.5%', reason: '预算比例表述缺少依据，存在合规风险', suggestion: '建议补充「经集团董事会批准」等限定语' },
          { level: 'medium', excerpt: '覆盖率达到90%以上', reason: '指标表述过于绝对', suggestion: '改为「力争达到90%左右」' },
        ],
      })
    }
    if (lastUser.includes('表格') || lastUser.includes('table')) {
      return JSON.stringify({
        headers: ['任务', '内容'],
        rows: [['第一项', '建设统一数据平台'], ['第二项', '推进智慧工地建设']],
      })
    }
    const oldMatch = lastUser.match(/---\n([\s\S]*?)\n---/)
    const oldText = oldMatch ? oldMatch[1].split('\n').find((l) => l.trim()) || '示例段落' : '示例段落'
    const count = 1
    const options = []
    const labels = ['最终方案']
    for (let i = 0; i < count; i++) {
      options.push({
        id: 'final',
        label: '最终方案',
        text: simulateRevision(oldText, lastUser),
      })
    }
    return JSON.stringify({ old_text: oldText, options, reason: '本地模拟方案' })
  }

  let answer = '根据文档内容，这段文字主要阐述了工作目标和重点任务。如需更详细的解读，请指出具体段落。'
  if (lastUser.includes('目标')) answer = '文档的总体目标是以「数字中建」为引领，到2028年基本建成覆盖全业务链条的数字化管理体系。'
  if (lastUser.includes('保障')) answer = '保障措施包括：加强组织领导、加大资金投入、强化人才保障、完善考核机制四个方面。'

  if (stream && onChunk) {
    for (const ch of answer) {
      onChunk(ch)
      await new Promise((r) => setTimeout(r, 15))
    }
  }
  return answer
}

function normalizeRevisionResult(result, documentText, selectedText, optionCount = 1) {
  const selected = selectedText?.trim()
  if (selected) {
    result.old_text = selected
    result.match_confidence = documentText.includes(selected) ? 'ok' : 'failed'
  } else {
    const alignedOld = alignOldText(documentText, result.old_text || '')
    const matchFailed = alignedOld && documentText && !documentText.includes(alignedOld)
    result.old_text = alignedOld || result.old_text
    result.match_confidence = matchFailed ? 'failed' : 'ok'
    if (matchFailed) {
      console.warn('[DocMate] old_text 对齐失败:', {
        original: result.old_text?.slice(0, 80),
        aligned: alignedOld?.slice(0, 80),
        docIncludesAligned: documentText.includes(alignedOld),
      })
    }
  }

  const count = Math.min(3, Math.max(1, optionCount || 1))
  const rawOptions = (result.options || []).filter((opt) => opt.text || opt.new_text)
  result.options = rawOptions.slice(0, count).map((opt, i) => ({
    id: opt.id || `opt${i + 1}`,
    label: opt.label || (count === 1 ? '推荐方案' : `方案 ${i + 1}`),
    text: opt.text || opt.new_text || '',
  }))
  return result
}

function validateRevisionResult(result, command = '') {
  const op = result.operation || 'replace'
  const oldText = String(result.old_text || '').trim()
  const nextText = String(result.options?.[0]?.text || '').trim()
  if (op !== 'delete' && !nextText) {
    throw new Error('AI 返回的新文本为空，请重试')
  }
  if (op !== 'delete' && oldText && nextText === oldText) {
    throw new Error('AI 返回的新文本与原文相同，请调整指令后重试')
  }
  const isConcise = /精简|简洁|压缩|缩短|删减/.test(command)
  if (op === 'replace' && oldText.length > 80 && nextText.length < oldText.length * 0.15 && !isConcise) {
    result.match_confidence = 'failed'
    result.reason = [result.reason, '新文本长度明显偏短，建议采纳前重点核对。'].filter(Boolean).join('；')
  }
  return result
}

function revisionRetryHint(message) {
  if (message.includes('与原文相同')) {
    return '你上次输出与原文完全相同。请确保 options[0].text 与原文有明确差异，并严格执行用户的修改指令。'
  }
  if (message.includes('明显偏短') || message.includes('过短')) {
    return '你上次输出过短。请保留原文核心信息和关键事实，只优化表达，不要大幅删减。'
  }
  if (message.includes('为空')) {
    return '你上次输出为空。请给出可直接替换原文的完整文本。'
  }
  return `上一次输出存在问题：${message}。请重新生成，确保新文本有效且符合指令。`
}

async function processRevise(settings, payload, aiContext, onChunk, signal) {
  const { document_text, selected_text, command, history = [], temperature } = payload

  const legacyKb = aiContext?.legacyKnowledgeBase || ''

  const resolved = await resolveEditTarget(
    settings,
    callChat,
    document_text,
    selected_text,
    command,
    history,
    legacyKb,
  )

  if (resolved.action === 'clarify') {
    const err = new Error(resolved.clarify_question || '请补充说明要修改的位置')
    err.code = 'CLARIFY'
    err.candidates = resolved.candidates || []
    throw err
  }

  if (resolved.action === 'qa') {
    return processQA(settings, { document_text, question: command, history }, aiContext, onChunk, signal)
  }

  const operation = resolved.action || 'replace'
  let oldText = resolved.target_text?.trim() || ''

  if (operation === 'insert') {
    oldText = ''
  } else if (!oldText) {
    oldText = findTargetText(document_text, selected_text, command)
  }

  if (operation !== 'insert' && !oldText) {
    throw new Error('NOT_FOUND')
  }

  if (operation === 'delete') {
    const paragraphs = splitParagraphs(document_text)
    const paraText =
      resolved.paragraph_index && paragraphs[resolved.paragraph_index - 1]
        ? paragraphs[resolved.paragraph_index - 1].text
        : undefined
    return {
      old_text: oldText,
      options: [{ id: 'opt1', label: '删除', text: '' }],
      reason: resolved.reason || `删除：${oldText.slice(0, 60)}${oldText.length > 60 ? '…' : ''}`,
      operation: 'delete',
      paragraph_index: resolved.paragraph_index,
      paragraph_text: paraText || oldText,
      match_confidence: document_text.includes(oldText) ? 'ok' : 'failed',
    }
  }

  const opHint =
    operation === 'insert'
      ? '这是新增内容（insert），old_text 可为空字符串，options[0].text 为要插入的完整段落。'
      : operation === 'delete'
        ? '这是删除内容（delete），options[0].text 必须为空字符串 ""，old_text 为要删除的原文。'
        : '这是替换修改（replace）。'

  const optionCount = 1
  const optionsHint = 'options 数组只能 1 项。'

  const prompt = withShanshanRolePrompt(`按指令生成修改方案，严格 JSON 输出：
{"old_text":"原文(尽量与原文一致，insert 时可为空)","options":[{"id":"opt1","label":"方案名","text":"完整结果文本"}],"reason":"简要说明","operation":"replace|insert|delete"}
只输出 JSON。${optionsHint}${opHint}`)

  const historyBlock = history.length
    ? `最近对话：\n${history.slice(-8).map((h) => `${h.role}: ${h.content}`).join('\n')}\n\n`
    : ''

  const userContent = `${buildPromptContext(command, aiContext, 'revise')}${historyBlock}文稿全文：\n---\n${document_text}\n---\n${selected_text ? `选中文本：\n---\n${selected_text}\n---\n` : ''}${oldText ? `待处理原文：\n---\n${oldText}\n---\n` : ''}修改指令：${command}`

  if (onChunk) onChunk('正在分析修改方案…\n')

  let content = await callChat(settings, [
    { role: 'system', content: prompt },
    { role: 'user', content: userContent },
  ], { json: true, temperature: temperature ?? 0.6, signal })

  let result = normalizeRevisionResult(parseJson(content, '修订结果 JSON'), document_text, selected_text || oldText, optionCount)
  result.operation = result.operation || operation
  if (resolved.reason) result.reason = [resolved.reason, result.reason].filter(Boolean).join('；')
  if (resolved.paragraph_index) result.paragraph_index = resolved.paragraph_index
  if (resolved.target_text && operation !== 'delete') {
    result.paragraph_text = resolved.target_text
  }
  if (resolved.confidence === 'ambiguous' || resolved.confidence === 'paragraph-fuzzy') {
    result.match_confidence = 'failed'
  }
  if (operation === 'insert') {
    result.insert_anchor = resolved.insert_after_text || ''
    result.insert_position = resolved.insert_position === 'start' ? 'start' : resolved.insert_position === 'after_anchor' ? 'after' : 'end'
  }
  if (operation === 'delete') {
    result.old_text = oldText
    if (result.options[0]) result.options[0].text = ''
  }
  try {
    return validateRevisionResult(result, command)
  } catch (err) {
    if (settings.useApi && settings.apiKey && operation !== 'delete') {
      logger.warn('ai', '修订结果校验失败，尝试自动重试一次', { reason: err.message, command })
      const retryHint = revisionRetryHint(err.message)
      content = await callChat(settings, [
        { role: 'system', content: prompt },
        { role: 'user', content: `${userContent}\n\n${retryHint}` },
      ], { json: true, temperature: Math.max(0.4, temperature ?? 0.5), signal })
      result = normalizeRevisionResult(parseJson(content, '修订重试 JSON'), document_text, selected_text || oldText, optionCount)
      result.operation = result.operation || operation
      if (resolved.reason) result.reason = [resolved.reason, result.reason].filter(Boolean).join('；')
      if (resolved.paragraph_index) result.paragraph_index = resolved.paragraph_index
      if (resolved.target_text) result.paragraph_text = resolved.target_text
      return validateRevisionResult(result, command)
    }
    throw err
  }
}

async function processPolish(settings, payload, aiContext, onChunk, signal) {
  const { document_text, selected_text, tone, history = [] } = payload
  const target = selected_text?.trim() || document_text.trim()
  if (!target) throw new Error('NO_CONTENT')

  const optionCount = Math.min(3, Math.max(1, settings.optionCount || 1))
  const optionsHint =
    optionCount === 1
      ? 'options 数组只能 1 项。'
      : `options 数组必须包含 ${optionCount} 个不同语气版本。`

  const prompt = withShanshanRolePrompt(`将文本润色为「${tone}」语气。JSON 格式：
{"old_text":"原文","options":[{"id":"opt1","label":"方案名","text":"润色后文本"}],"reason":"说明"}
${optionsHint}`)

  const historyBlock = history.length
    ? `最近对话：\n${history.slice(-6).map((h) => `${h.role}: ${h.content}`).join('\n')}\n\n`
    : ''

  if (onChunk) onChunk('正在润色…\n')

  const content = await callChat(settings, [
    { role: 'system', content: prompt },
    { role: 'user', content: `${buildPromptContext(tone, aiContext, 'polish')}${historyBlock}原文：\n---\n${target}\n---\n语气：${tone}` },
  ], { json: true, signal })

  return validateRevisionResult(normalizeRevisionResult(parseJson(content, '润色结果 JSON'), document_text, selected_text || target, optionCount), tone)
}

async function processQA(settings, payload, aiContext, onChunk, signal) {
  const { document_text, question, history = [] } = payload
  const system = `${buildPromptContext(question, aiContext, 'qa')}${withShanshanRolePrompt('你是文档问答助手。基于提供的文档准确回答，不知道则说明。回答简洁专业。')}`
  const userContent = `文档内容：\n---\n${document_text}\n---\n\n问题：${question}`

  const messages = [
    { role: 'system', content: system },
    ...history.slice(-6),
    { role: 'user', content: userContent },
  ]

  return callChat(settings, messages, { stream: !!onChunk, onChunk, signal })
}

async function processRisk(settings, payload, aiContext, onChunk, signal) {
  const { document_text } = payload
  if (onChunk) onChunk('正在扫描文档风险…\n')

  const prompt = withShanshanRolePrompt(`分析文档风险与规范性问题。JSON 格式：
{"risks":[{"level":"high|medium|low","excerpt":"原文片段","reason":"风险原因","suggestion":"修改建议"}]}
至少返回 1 条，最多 8 条。只输出 JSON。`)

  const content = await callChat(settings, [
    { role: 'system', content: prompt },
    { role: 'user', content: `${buildPromptContext('', aiContext, 'risk')}文档：\n---\n${document_text}\n---` },
  ], { json: true, signal })

  const result = parseJson(content, '风险扫描 JSON')
  return { risks: (result.risks || []).map((r, i) => ({ ...r, id: `risk-${i}` })) }
}

async function processOral(settings, payload, aiContext, onChunk, signal) {
  const { oral_text, style = '公文风格' } = payload

  if (onChunk) onChunk('正在转换口语为正式文稿…\n')

  const prompt = withShanshanRolePrompt(`将口语文字转为${style}正式文稿。生成 1 个最佳最终版本，JSON：
{"old_text":"口语原文","options":[{"id":"final","label":"最终方案","text":"正式文稿"}],"reason":"说明"}
options 数组只能有 1 项。`)

  const content = await callChat(settings, [
    { role: 'system', content: prompt },
    { role: 'user', content: `${buildPromptContext(oral_text, aiContext, 'oral')}口语内容：\n---\n${oral_text}\n---\n风格：${style}` },
  ], { json: true, signal })

  return validateRevisionResult(normalizeRevisionResult(parseJson(content, '口语转换 JSON'), oral_text, oral_text), style)
}

async function processTable(settings, payload, aiContext, onChunk, signal) {
  const { selected_text } = payload
  if (!selected_text?.trim()) throw new Error('NO_SELECTION')

  if (onChunk) onChunk('正在生成表格…\n')

  const prompt = withShanshanRolePrompt(`从文字中提取结构化信息生成表格。JSON：
{"headers":["列1","列2"],"rows":[["值1","值2"]],"reason":"说明"}`)

  const content = await callChat(settings, [
    { role: 'system', content: prompt },
    { role: 'user', content: `${buildPromptContext(selected_text, aiContext, 'table')}文字：\n---\n${selected_text}\n---` },
  ], { json: true, signal })

  return parseJson(content, '表格结果 JSON')
}

async function processRoute(settings, payload, aiContext, onChunk, signal) {
  const { user_input, document_text, selected_text, history = [] } = payload
  const task = await classifyIntent(settings, callChat, user_input, selected_text)

  try {
    switch (task) {
      case 'polish': {
        const toneMatch = user_input.match(/(专业正式|亲切友好|简洁直白|自信有力|客观中立|正式|简洁)/)
        const tone = toneMatch ? toneMatch[1] : '专业正式'
        return {
          task,
          result: await processPolish(settings, {
            document_text,
            selected_text,
            tone: user_input.includes('润色') ? user_input : `全文润色：${tone}`,
            history,
          }, aiContext, onChunk, signal),
        }
      }
      case 'qa':
        return {
          task,
          result: await processQA(settings, {
            document_text,
            question: user_input,
            history,
          }, aiContext, onChunk, signal),
        }
      case 'summarize':
        return {
          task: 'qa',
          result: await processQA(settings, {
            document_text: selected_text?.trim() || document_text,
            question: user_input || '请总结这段文稿的核心要点',
            history,
          }, aiContext, onChunk, signal),
        }
      case 'risk':
        return {
          task,
          result: await processRisk(settings, { document_text }, aiContext, onChunk, signal),
        }
      case 'oral':
        return {
          task,
          result: await processOral(settings, { oral_text: user_input }, aiContext, onChunk, signal),
        }
      case 'table':
        return {
          task,
          result: await processTable(settings, { selected_text }, aiContext, onChunk, signal),
        }
      default: {
        const reviseResult = await processRevise(settings, {
          document_text,
          selected_text,
          command: user_input,
          history,
        }, aiContext, onChunk, signal)
        if (typeof reviseResult === 'string') {
          return { task: 'qa', result: reviseResult }
        }
        return { task: 'revise', result: reviseResult }
      }
    }
  } catch (err) {
    if (err.code === 'CLARIFY') {
      return {
        task: 'clarify',
        result: {
          question: err.message,
          candidates: err.candidates || [],
        },
      }
    }
    throw err
  }
}

async function processTask(settings, task, payload, aiContext, onChunk, signal) {
  switch (task) {
    case 'route':
      return processRoute(settings, payload, aiContext, onChunk, signal)
    case 'revise':
      return processRevise(settings, payload, aiContext, onChunk, signal)
    case 'polish':
      return processPolish(settings, payload, aiContext, onChunk, signal)
    case 'qa':
      return processQA(settings, payload, aiContext, onChunk, signal)
    case 'summarize':
      return processQA(settings, {
        document_text: payload.selected_text?.trim() || payload.document_text,
        question: payload.question || payload.user_input || '请总结这段文稿的核心要点',
        history: payload.history || [],
      }, aiContext, onChunk, signal)
    case 'risk':
      return processRisk(settings, payload, aiContext, onChunk, signal)
    case 'oral':
      return processOral(settings, payload, aiContext, onChunk, signal)
    case 'table':
      return processTable(settings, payload, aiContext, onChunk, signal)
    default:
      throw new Error(`未知任务: ${task}`)
  }
}

module.exports = {
  processTask,
  readKnowledgeBase,
  writeKnowledgeBase,
  callChat,
  classifyError,
}
