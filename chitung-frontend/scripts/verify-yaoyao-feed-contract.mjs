import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import assert from 'node:assert/strict'

const root = new URL('..', import.meta.url).pathname
const read = (path) => readFileSync(join(root, path), 'utf8')
const exists = (path) => existsSync(join(root, path))

assert(
  exists('src/pages/ExternalRiskMonitorPage.vue'),
  'yaoyao feed must have a dedicated ExternalRiskMonitorPage',
)

const page = read('src/pages/ExternalRiskMonitorPage.vue')
const router = read('src/router/index.ts')
const sidebar = read('src/components/layout/PanelSidebar.vue')
const workbench = read('src/pages/WorkbenchPage.vue')
const app = read('src/App.vue')
const ragPage = read('src/pages/YaoyaoKnowledgePage.vue')
const api = read('src/services/chitungApi.ts')

assert(
  router.includes("{ path: 'feed', name: 'yaoyao-feed', component: () => import('../pages/ExternalRiskMonitorPage.vue') }"),
  'yaoyao feed route must not reuse the generic RAG page',
)

for (const token of ['外部舆情监听', '监听配置', '执行过程', '生成简报', '历史简报', 'sendChatMessage']) {
  assert(page.includes(token), `ExternalRiskMonitorPage must expose ${token}`)
}

for (const token of ['上传资料', '拖拽文件到这里', 'RAG 知识库']) {
  assert(!page.includes(token), `external risk monitor must not expose generic RAG upload UI: ${token}`)
}

for (const token of ['风险条目', '关联表格', 'link_external_risk_to_forms', 'extractRiskItems', 'extractFormLinks']) {
  assert(!page.includes(token), `external risk monitor must render the report only, not legacy risk/form panels: ${token}`)
}

assert(
  sidebar.includes("label: '外部舆情监听'") && !sidebar.includes("label: '舆情规范', path: '/yaoyao/feed', note: '预留'"),
  'sidebar must present yaoyao feed as an active external monitoring feature, not a reserved placeholder',
)

assert(!workbench.includes('generateDailyBriefing'), 'dashboard must not execute the external briefing workflow directly')
assert(!workbench.includes('externalRiskBriefing'), 'dashboard must not render external risk results inline')
assert(app.includes("'external-risk': '/yaoyao/feed'"), 'legacy app navigation must support external-risk')

for (const token of ['知识库回答', 'askRag', 'ragAnswer', 'citations', '仅检索原文']) {
  assert(ragPage.includes(token) || api.includes(token), `RAG knowledge page must support LLM-backed Q&A: ${token}`)
}

assert(api.includes('/api/rag/ask'), 'frontend API client must call the RAG ask endpoint')
assert(api.includes('/api/external-risk/briefing-reports'), 'frontend API client must load persisted external risk briefings')
assert(
  !ragPage.includes('results.value = answer.matches'),
  'RAG answer flow must not dump all matched chunks into the visible raw-result list',
)
