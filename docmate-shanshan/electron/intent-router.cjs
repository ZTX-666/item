const { parseJson } = require('./utils.cjs')

const KEYWORD_RULES = [
  { task: 'risk', patterns: [/风险/, /合规/, /扫描/, /审查/, /检查/, /规范性/, /问题点/, /敏感表述/, /3311/, /有没有问题/, /查一下/, /法律/, /法规/, /违规/, /隐患/] },
  { task: 'table', patterns: [/表格/, /做成表/, /转成表/, /列表化/, /清单/, /台账/, /汇总表/, /对比表/] },
  { task: 'summarize', patterns: [/总结/, /摘要/, /概括/, /提炼要点/, /提取要点/, /归纳/, /核心要点/, /主要内容/, /要点/, /概述/] },
  { task: 'oral', patterns: [/口语/, /口头/, /录音/, /转成公文/, /转成正式/, /改成公文/, /改成正式/, /书面化/, /文字稿/] },
  { task: 'polish', patterns: [/润色/, /语气/, /风格/, /正式化/, /专业化/, /简洁/, /精简/, /亲切/, /客观/, /优化表达/, /修改/, /改一下/, /调整/, /改好/, /改正式/, /改文/, /优化/, /提升/, /完善/, /修缮/] },
  { task: 'qa', patterns: [/^(问|请问|查询|解释|说明一下|是什么|什么意思|为什么|如何理解)/, /\?$/, /？$/, /解释下/, /什么意思/] },
]

const LOCATE_PATTERNS = [/第[一二三四五六七八九十\d]+段/, /标题/, /结尾/, /开头/, /文末/, /全文/, /所有/, /全部/, /「[^」]+」/, /"[^"]+"/]

function keywordRoute(input) {
  const text = input.trim()
  if (!text) return 'revise'
  const hasLocate = LOCATE_PATTERNS.some((p) => p.test(text))

  for (const rule of KEYWORD_RULES) {
    if (hasLocate && rule.task === 'polish' && /修改|改一下|调整|改好|改文|优化|提升|完善|修缮/.test(text)) {
      return 'revise'
    }
    if (rule.patterns.some((p) => p.test(text))) return rule.task
  }
  return 'revise'
}

async function classifyIntent(settings, callChat, input, selectedText) {
  const quick = keywordRoute(input)
  if (quick !== 'revise') return quick
  if (selectedText?.trim() && /表格|列表/.test(input)) return 'table'
  if (!selectedText?.trim() && /总结|摘要|概括/.test(input)) return 'summarize'

  if (!settings.useApi || !settings.apiKey) {
    return quick
  }

  try {
    const content = await callChat(
      settings,
      [
        {
          role: 'system',
          content:
            '你是意图分类器。根据用户输入和是否选中文本判断任务类型，只输出 JSON：{"task":"revise|polish|qa|risk|oral|table|summarize"}。revise=改写/新增/删除正文；polish=润色风格；qa=询问解释；risk=风险合规检查；oral=口语转正式；table=转表格；summarize=总结摘要。',
        },
        {
          role: 'user',
          content: `用户输入：${input}\n是否有选中文本：${selectedText?.trim() ? '是' : '否'}\n选中文本预览：${(selectedText || '').slice(0, 200)}`,
        },
      ],
      { json: true },
    )
    const parsed = parseJson(content, '意图分类 JSON')
    const task = parsed.task
    if (['revise', 'polish', 'qa', 'risk', 'oral', 'table', 'summarize'].includes(task)) return task
  } catch {
    /* fallback */
  }

  return 'revise'
}

module.exports = { keywordRoute, classifyIntent }
