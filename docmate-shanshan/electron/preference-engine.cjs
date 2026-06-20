const fs = require('fs')
const path = require('path')
const { parseJson } = require('./utils.cjs')

const DEFAULT_PROFILE = {
  version: 1,
  updated_at: null,
  auto_learn: true,
  learning: {
    enabled: true,
    apply_mode: 'suggest',
    learn_from: {
      accepted: true,
      rejected: true,
      manual_terms: true,
      commands: true,
    },
    digest_threshold: 10,
    retention_limit: 200,
    privacy: {
      store_examples: true,
      store_rejected_text: false,
    },
  },
  style: {
    formality: 'formal',
    conciseness: 'concise',
    tone: '公文风格',
    document_style: 'general',
    risk_sensitivity: 'strict',
    preferred_phrases: [],
    avoided_phrases: [],
  },
  domain: {
    industry: '',
    org: '',
    terms: [],
  },
  habits: {
    common_commands: [],
    reject_triggers: [],
  },
  digest: {
    interactions_count: 0,
    last_digest_at: null,
    next_digest_at: 5,
  },
}

const DIGEST_PROMPT = `你是一个用户偏好分析助手。根据用户近期的文稿修改操作记录，更新其写作偏好档案。

请输出更新后的偏好档案 JSON，规则：
1. 只修改有充分证据支持的字段，没有证据的字段保持原值
2. preferred_phrases：用户多次采纳的修改中反复出现的用词（最多 10 个）
3. avoided_phrases：用户多次拒绝的修改中反复出现的用词（最多 10 个）
4. reject_triggers：从拒绝模式中总结的规律（最多 5 条）
5. domain.terms：用户文稿中反复出现的行业术语（最多 15 个）
6. 如果涉及人事、薪酬、职级、绩效、培训、党建、党委、组织生活等表述，优先沉淀到 domain.terms
7. 如果用户多次拒绝某类替换（例如把“加强”改成“强化”），记录到 avoided_phrases 或 reject_triggers
8. 不要因为单次操作就大幅改变风格偏好，必须有明确证据
9. 保持 JSON 结构与输入一致
10. 只输出 JSON`

function profilePath(userDataPath) {
  return path.join(userDataPath, 'user-preferences.json')
}

function logPath(userDataPath) {
  return path.join(userDataPath, 'interaction-log.jsonl')
}

function readUserProfile(userDataPath) {
  try {
    const raw = JSON.parse(fs.readFileSync(profilePath(userDataPath), 'utf-8'))
    const learning = {
      ...DEFAULT_PROFILE.learning,
      ...raw.learning,
      learn_from: { ...DEFAULT_PROFILE.learning.learn_from, ...raw.learning?.learn_from },
      privacy: { ...DEFAULT_PROFILE.learning.privacy, ...raw.learning?.privacy },
    }
    if (typeof raw.auto_learn === 'boolean') learning.enabled = raw.auto_learn
    return {
      ...DEFAULT_PROFILE,
      ...raw,
      auto_learn: learning.enabled,
      learning,
      style: { ...DEFAULT_PROFILE.style, ...raw.style },
      domain: { ...DEFAULT_PROFILE.domain, ...raw.domain },
      habits: { ...DEFAULT_PROFILE.habits, ...raw.habits },
      digest: { ...DEFAULT_PROFILE.digest, ...raw.digest },
    }
  } catch {
    return { ...DEFAULT_PROFILE }
  }
}

function writeUserProfile(userDataPath, profile) {
  fs.writeFileSync(profilePath(userDataPath), `${JSON.stringify(profile, null, 2)}\n`, 'utf-8')
}

function readInteractionLog(userDataPath) {
  const fp = logPath(userDataPath)
  if (!fs.existsSync(fp)) return []
  return fs
    .readFileSync(fp, 'utf-8')
    .trim()
    .split('\n')
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line)
      } catch {
        return null
      }
    })
    .filter(Boolean)
}

function appendInteraction(userDataPath, record) {
  const fp = logPath(userDataPath)
  const line = `${JSON.stringify({ ts: new Date().toISOString(), ...record })}\n`
  fs.appendFileSync(fp, line, 'utf-8')
  return readInteractionLog(userDataPath).length
}

function cleanInteractionLog(userDataPath, keepLast = 200) {
  const fp = logPath(userDataPath)
  if (!fs.existsSync(fp)) return
  const lines = fs.readFileSync(fp, 'utf-8').trim().split('\n').filter(Boolean)
  if (lines.length <= keepLast) return
  fs.writeFileSync(fp, `${lines.slice(-keepLast).join('\n')}\n`, 'utf-8')
}

function preferencePrefix(preferences, task = 'revise') {
  if (!preferences?.style) return ''

  const parts = []
  const formalityMap = { formal: '正式公文', balanced: '适度正式', casual: '简洁口语' }
  if (preferences.style.formality) {
    parts.push(`风格：${formalityMap[preferences.style.formality] || preferences.style.tone || '正式公文'}`)
  }
  const concisenessMap = {
    concise: '用词精简，避免冗余修饰',
    balanced: '适度精炼',
    verbose: '表述详尽',
  }
  if (preferences.style.conciseness) {
    parts.push(concisenessMap[preferences.style.conciseness] || '')
  }
  const docStyleMap = {
    hr: '优先适配人力部门文稿，重视制度、薪酬、职级、考核、培训等表述的严谨性',
    party: '优先适配党建部门文稿，重视政治术语、党内公文规范和政策引用准确性',
    general: '适配综合公文场景，保持正式、规范、稳妥',
  }
  if (preferences.style.document_style && ['revise', 'polish', 'oral', 'risk'].includes(task)) {
    parts.push(docStyleMap[preferences.style.document_style] || '')
  }
  const riskMap = {
    standard: '风险检查按常规办公文稿标准',
    strict: '风险检查从严，重点关注歧义、合规和政策表述',
    highest: '风险检查最高敏感度，涉及人事制度和党建表述必须特别谨慎',
  }
  if (preferences.style.risk_sensitivity && task === 'risk') {
    parts.push(riskMap[preferences.style.risk_sensitivity] || '')
  }
  if (preferences.style.avoided_phrases?.length) {
    parts.push(`避免使用：${preferences.style.avoided_phrases.slice(0, 5).join('、')}`)
  }
  if (preferences.style.preferred_phrases?.length && task !== 'risk') {
    parts.push(`倾向用词：${preferences.style.preferred_phrases.slice(0, 5).join('、')}`)
  }
  if (preferences.domain?.terms?.length) {
    const limit = task === 'qa' || task === 'risk' ? 12 : 8
    parts.push(`领域术语：${preferences.domain.terms.slice(0, limit).join('、')}`)
  }
  const commonCommands = preferences.habits?.common_commands || []
  if (task === 'revise' && commonCommands.length) {
    parts.push(`常用改稿倾向：${commonCommands.slice(0, 3).join('、')}`)
  }
  if (preferences.learning?.apply_mode === 'suggest') {
    parts.push('用户偏好只作为建议约束，不得覆盖用户本次明确指令')
  }
  if (!parts.length) return ''
  return `用户偏好：${parts.filter(Boolean).join('；')}。\n\n`
}

function deepMerge(base, patch) {
  const out = { ...base }
  for (const key of Object.keys(patch || {})) {
    if (patch[key] && typeof patch[key] === 'object' && !Array.isArray(patch[key])) {
      out[key] = deepMerge(base[key] || {}, patch[key])
    } else {
      out[key] = patch[key]
    }
  }
  return out
}

async function digestPreferences(settings, callChat, userDataPath) {
  const log = readInteractionLog(userDataPath)
  const profile = readUserProfile(userDataPath)
  const threshold = Number(profile.learning?.digest_threshold || 10)
  const lastDigest = profile.digest?.interactions_count || 0
  const recentActions = log.slice(lastDigest)
  if (recentActions.length < Math.max(3, threshold)) return profile

  const recentText = recentActions
    .map(
      (a) =>
        `指令："${a.command}" | 原文："${(a.old_text || '').slice(0, 80)}" | AI改为："${(a.new_text || '').slice(0, 80)}" | 用户：${a.action}${a.reject_reason ? `（原因：${a.reject_reason}）` : ''}`,
    )
    .join('\n')

  try {
    const content = await callChat(
      settings,
      [
        { role: 'system', content: DIGEST_PROMPT },
        {
          role: 'user',
          content: `当前偏好档案：\n${JSON.stringify(profile, null, 2)}\n\n近期操作记录：\n${recentText}`,
        },
      ],
      { json: true, temperature: 0.2 },
    )
    const updated = parseJson(content, '偏好摘要 JSON')
    updated.digest = {
      interactions_count: log.length,
      last_digest_at: new Date().toISOString(),
      next_digest_at: log.length + Math.max(3, threshold),
    }
    writeUserProfile(userDataPath, deepMerge(profile, updated))
    console.log('偏好摘要已更新:', updated.digest)
    cleanInteractionLog(userDataPath)
    return updated
  } catch (err) {
    console.error('偏好摘要失败:', err)
    return profile
  }
}

function logInteraction(userDataPath, record, settings, callChat) {
  const profile = readUserProfile(userDataPath)
  const learning = profile.learning || DEFAULT_PROFILE.learning
  if (learning.enabled === false || profile.auto_learn === false) {
    return { ok: true, count: readInteractionLog(userDataPath).length }
  }
  if (record.action === 'accept' && learning.learn_from?.accepted === false) {
    return { ok: true, count: readInteractionLog(userDataPath).length }
  }
  if (record.action === 'reject' && learning.learn_from?.rejected === false) {
    return { ok: true, count: readInteractionLog(userDataPath).length }
  }

  const safeRecord = { ...record }
  if (learning.privacy?.store_examples === false) {
    safeRecord.old_text = ''
    safeRecord.new_text = ''
  } else if (safeRecord.action === 'reject' && learning.privacy?.store_rejected_text === false) {
    safeRecord.old_text = ''
  }

  const count = appendInteraction(userDataPath, safeRecord)

  const threshold = Number(learning.digest_threshold || 10)
  const nextDigest = profile.digest?.next_digest_at || Math.max(3, threshold)
  if (count >= nextDigest) {
    digestPreferences(settings, callChat, userDataPath).catch((err) => {
      console.error('偏好摘要失败:', err)
    })
  }
  cleanInteractionLog(userDataPath, Number(learning.retention_limit || 200))
  return { ok: true, count }
}

module.exports = {
  DEFAULT_PROFILE,
  readUserProfile,
  writeUserProfile,
  readInteractionLog,
  logInteraction,
  digestPreferences,
  preferencePrefix,
  cleanInteractionLog,
  deepMerge,
}
