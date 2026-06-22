import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import assert from 'node:assert/strict'

const root = new URL('..', import.meta.url).pathname
const read = (path) => readFileSync(join(root, path), 'utf8')

const assistantPage = read('src/pages/AIAssistantPage.vue')
const chatbotPanel = read('src/components/layout/ChatbotPanel.vue')
const assistantComposable = read('src/composables/useAiAssistant.ts')
const packageJson = read('package.json')

assert(
  assistantPage.includes('getSkills') && assistantPage.includes('getWorkflowTemplates'),
  'AI assistant tab must load real backend skills and workflows',
)

assert(
  assistantPage.includes("import { useAiAssistant }"),
  'AI assistant tab must use the same assistant composable as the robot panel',
)

assert(
  chatbotPanel.includes("import { useAiAssistant }"),
  'robot panel must use the shared assistant composable',
)

for (const label of ['隐患排查', '视频巡检', '舆情简报', '每日简报', '制度查询', '文档表格']) {
  assert(
    assistantComposable.includes(label),
    `robot quick action preset should remain available: ${label}`,
  )
}

for (const skillName of [
  'daily-risk-briefing',
  'hazard-intake',
  'knowledge-query',
  'shanshan-doc',
  'visual-patrol',
  'whatsapp-sql-query',
  'whatsapp-wacli-ops',
]) {
  assert(
    assistantPage.includes(skillName),
    `AI assistant tab must know how to parameterize backend skill: ${skillName}`,
  )
}

for (const token of ['selectedEntry', '参数', 'entryParams', 'runSelectedEntry', 'paramFields']) {
  assert(
    assistantPage.includes(token),
    `AI assistant tab must support editable skill/workflow parameters: ${token}`,
  )
}

for (const token of ['runSelectedEntry', 'toolResults', 'cards', 'Skill', 'Workflow', 'resultReports', 'resultImages']) {
  assert(
    assistantPage.includes(token),
    `AI assistant tab must render the same execution surface as the robot panel: ${token}`,
  )
}

assert(
  packageJson.includes('"test:assistant"'),
  'frontend package must expose an assistant contract test',
)
