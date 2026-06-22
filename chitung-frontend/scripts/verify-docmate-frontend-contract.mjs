import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import assert from 'node:assert/strict'

const root = new URL('..', import.meta.url).pathname
const read = (path) => readFileSync(join(root, path), 'utf8')
const exists = (path) => existsSync(join(root, path))

const api = read('src/services/chitungApi.ts')
const chatbot = read('src/components/layout/ChatbotPanel.vue')
const assistant = read('src/composables/useAiAssistant.ts')
const docPage = read('src/pages/ShanshanDocPage.vue')
const activityBar = read('src/components/layout/ActivityBar.vue')
const panelSidebar = read('src/components/layout/PanelSidebar.vue')
const topBar = read('src/components/layout/TopBar.vue')
const styles = read('src/style.css')

for (const fnName of ['docmateUpload', 'docmateCommit', 'docmateRetry', 'docmateDownloadUrl']) {
  assert(api.includes(`function ${fnName}`), `DocMate API client must expose ${fnName}`)
}

for (const route of ['/api/docmate/upload', '/api/docmate/commit', '/api/docmate/retry', '/api/docmate/download']) {
  assert(api.includes(route), `DocMate API client must call ${route}`)
}

assert(api.includes('DocmateUploadResult'), 'DocMate upload must have a dedicated upload result type')
assert(
  api.includes('Promise<DocmateUploadResult>'),
  'docmateUpload must return upload metadata, not a parsed document result',
)
assert(
  api.includes('/api/docmate/download/${encodeURIComponent(fileIdOrUrl)}'),
  'docmateDownloadUrl must build file-id based download URLs',
)

assert(exists('src/composables/useDocmateSession.ts'), 'DocMate session composable must exist')
assert(exists('src/components/documents/DocmateDiffReview.vue'), 'DocMate diff review component must exist')

const session = read('src/composables/useDocmateSession.ts')
const diffReview = read('src/components/documents/DocmateDiffReview.vue')

for (const token of [
  'uploadDocument',
  'generateChanges',
  'acceptSelected',
  'rejectSelected',
  'retryAll',
  'outputResultPath',
  'previewParagraphs',
]) {
assert(session.includes(token), `DocMate shared session must provide ${token}`)
}

assert(
  session.includes('const uploaded = await docmateUpload(file)') && session.includes('await docmateRead(uploaded.file_path)'),
  'uploadDocument must upload first, then read the returned file_path to obtain doc_id',
)
assert(
  session.includes('result.data.download_url') || session.includes('result.data.file_id'),
  'DocMate commit flow must preserve backend download_url or file_id for downloads',
)

for (const token of ['采纳选中', '不采纳', '全部重试', '下载修改后的文档', 'docmateDownloadUrl']) {
  assert(diffReview.includes(token), `DocMate diff review must render ${token}`)
}

assert(docPage.includes('useDocmateSession'), 'Shanshan document page must use shared DocMate session')
assert(docPage.includes('uploadDocument'), 'Shanshan document page must support document upload')
assert(docPage.includes('pendingChanges'), 'Shanshan document page must surface pending DocMate changes')
assert(!docPage.includes('docmateApply('), 'Shanshan document page should not use legacy apply flow directly')

assert(chatbot.includes("import { useAiAssistant }"), 'ChatbotPanel must keep the shared AI assistant composable')
assert(chatbot.includes('loadLatestHistory'), 'ChatbotPanel must keep chat history loading')
assert(chatbot.includes('toolResults'), 'ChatbotPanel must keep tool-result rendering')
assert(chatbot.includes('handleCardAction'), 'ChatbotPanel must keep card actions')
assert(chatbot.includes('DocmateDiffReview'), 'ChatbotPanel must embed DocMate review additively')
assert(chatbot.includes('useDocmateSession'), 'ChatbotPanel must share DocMate session state')

assert(chatbot.includes('文档改稿'), 'ChatbotPanel must include a DocMate editing quick action')
assert(assistant.includes('WhatsApp'), 'WhatsApp quick action must remain available')

for (const logo of ['brand.jpg', 'center.png', 'docmate.png', 'guardian.png', 'lingxun.png', 'yaoyao.png']) {
  assert(exists(`src/assets/logos/${logo}`), `final logo asset missing: ${logo}`)
}

assert(!exists('../Front End Logo'), 'root Front End Logo folder must not be added')

for (const component of [activityBar, panelSidebar, topBar]) {
  assert(component.includes('assets/logos'), 'layout components must import final logo assets')
}

assert(panelSidebar.includes('赤瞳灵讯'), 'Panel sidebar must preserve 灵讯 naming')
const wrongLingxunName = `赤瞳${'零'}讯`
assert(!panelSidebar.includes(wrongLingxunName), 'Panel sidebar must not drift from 灵讯 naming')
assert(!activityBar.includes(wrongLingxunName), 'Activity bar must not drift from 灵讯 naming')

for (const token of ['--rail-bg', '--ring', ':focus-visible', 'scrollbar-width', '.btn--accent']) {
  assert(styles.includes(token), `shared design system token/rule missing: ${token}`)
}
