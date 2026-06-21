import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import assert from 'node:assert/strict'

const root = new URL('..', import.meta.url).pathname
const read = (path) => readFileSync(join(root, path), 'utf8')

const workbench = read('src/pages/WorkbenchPage.vue')
const router = read('src/router/index.ts')
const commandBar = read('src/components/layout/CommandBar.vue')
const cameraGrid = read('src/components/cards/CameraGrid.vue')
const visualPatrol = read('src/pages/VisualPatrolPage.vue')
const panelSidebar = read('src/components/layout/PanelSidebar.vue')
const hazardLedger = read('src/pages/HazardLedgerPage.vue')
const api = read('src/services/chitungApi.ts')
const cctvLivePanel = read('src/components/cctv/CctvLivePanel.vue')
const cctvPlayerPage = read('src/pages/CctvPlayerPage.vue')
const chatbotPanel = read('src/components/layout/ChatbotPanel.vue')
const skillsPage = read('src/pages/SkillsCompatPage.vue')
const electronMain = read('electron/main.cjs')
const preload = read('electron/preload.cjs')
const packageJson = read('package.json')

const hiddenFromDashboard = [
  'HybridOrchestrationPanel',
  'SystemSettingsPanel',
  'HazardLedgerPanel',
  'FormTemplateBrowserPanel',
  '安全表格模板库',
  '系统设置',
  'Codex + Chitong 混合编排',
]

for (const token of hiddenFromDashboard) {
  assert(
    !workbench.includes(token),
    `guardian dashboard must not expose debug/config/docmate surface: ${token}`,
  )
}

assert(
  !router.includes("{ path: 'reports', name: 'docmate-reports', component: () => import('../pages/WorkbenchPage.vue') }"),
  'docmate reports route must not reuse the guardian dashboard',
)

assert(
  commandBar.includes("submit: [payload: { message: string; area: string }]"),
  'CommandBar must submit the selected area with the command',
)

assert(
  !workbench.includes("current_area: 'B2'"),
  'Workbench command submission must not hard-code current_area to B2',
)

assert(
  cameraGrid.includes('openEvidence: [cameraId: string]'),
  'CameraGrid must expose an openEvidence event matching the workbench listener',
)

assert(
  workbench.includes("import CctvLivePanel from '../components/cctv/CctvLivePanel.vue'"),
  'guardian dashboard must embed the shared CCTV live panel',
)

assert(
  visualPatrol.includes("import CctvLivePanel from '../components/cctv/CctvLivePanel.vue'"),
  'visual patrol must embed the shared CCTV live panel',
)

assert(
  !panelSidebar.includes('CCTV 实时播放'),
  'guardian sidebar must not expose CCTV as a separate tab',
)

assert(
  !panelSidebar.includes("label: '待确认事项'") && !panelSidebar.includes("path: '/guardian/confirmations'"),
  'guardian sidebar must not expose the pending-confirmations tab',
)

assert(
  !router.includes("component: () => import('../pages/CctvPlayerPage.vue')"),
  'CCTV standalone page must not be mounted as a guardian tab page',
)

assert(
  workbench.includes('检测方向') && workbench.includes('selectedVideoCameraIds'),
  'guardian dashboard must expose video detection direction input and multi-camera selection',
)

assert(
  workbench.includes('机械作业半径') && workbench.includes('人员PPE合规'),
  'guardian dashboard default video detection prompt must target PPE and machinery exclusion-zone risks',
)

assert(
  workbench.includes('refinedVideoPrompt') && workbench.includes('textarea'),
  'guardian dashboard must show the refined prompt in an editable textarea',
)

assert(
  workbench.includes('refineWorkbenchVideoDetectionPrompt'),
  'guardian dashboard must let users refine the prompt before running detection',
)

assert(
  workbench.includes('runWorkbenchVideoDetection'),
  'guardian dashboard must call the workbench video detection API',
)

assert(
  !workbench.includes('最近检测') &&
    !workbench.includes('刷新结果') &&
    !workbench.includes('loadLatestVideoDetectionReport'),
  'guardian dashboard must not frame history as a recent detection result',
)

assert(
  workbench.includes('检测结论'),
  'guardian dashboard must name detection output as a current detection conclusion',
)

assert(
  workbench.includes('帧选择方式') &&
    workbench.includes('实时流截取当前帧') &&
    workbench.includes('C-SMART 截图') &&
    workbench.includes('本地预设回退帧'),
  'guardian dashboard must explain how video frames are selected for detection',
)

assert(
  workbench.includes('class="panel video-detection-process"') &&
    workbench.includes('中间过程') &&
    workbench.includes('videoDetectionSteps'),
  'guardian dashboard must keep video-detection intermediate steps visible',
)

assert(
  workbench.includes('class="panel video-detection-final"') &&
    workbench.includes('最终结果') &&
    workbench.includes('等待开始检测'),
  'guardian dashboard must reserve a clear final-result panel for video detection',
)

assert(
  workbench.includes(':show-action="false"'),
  'guardian dashboard CCTV panel must hide the secondary patrol action so detection has one entry point',
)

assert(
  cctvLivePanel.includes('embedded=1') &&
    cctvLivePanel.includes('live=1') &&
    !cctvLivePanel.includes('standalonePlayerSrc') &&
    !cctvLivePanel.includes('openStandalonePlayer') &&
    !cctvLivePanel.includes('独立窗口'),
  'embedded dashboard CCTV must render a live main video stage without a separate window entry',
)

assert(
  cctvPlayerPage.includes('live=1'),
  'standalone CCTV page must request live video mode from the gateway player',
)

assert(
  electronMain.includes('http://127.0.0.1:3457/api/health') &&
    electronMain.includes("'cctv-gateway'") &&
    electronMain.includes('src/server.cjs'),
  'Electron desktop shell must health-check and autostart the local CCTV gateway on :3457',
)

assert(
  electronMain.includes('function waitForHealthy') &&
    electronMain.includes("await waitForHealthy('http://127.0.0.1:3457/api/health'"),
  'Electron desktop shell must wait briefly for CCTV gateway readiness before opening the UI',
)

assert(
  electronMain.includes("ipcMain.handle('services:ensure-cctv-gateway'") &&
    preload.includes('ensureCctvGateway') &&
    cctvLivePanel.includes('window.chitungDesktop?.ensureCctvGateway') &&
    cctvPlayerPage.includes('window.chitungDesktop?.ensureCctvGateway'),
  'CCTV views must ask Electron to restart the local CCTV gateway and retry when health fetch fails',
)

assert(
  packageJson.includes('"from": "../cctv-gateway"') &&
    packageJson.includes('"to": "cctv-gateway"'),
  'desktop package must include cctv-gateway so packaged Electron can start :3457',
)

assert(
  cctvLivePanel.includes('aspect-ratio: 6 / 5') &&
    cctvLivePanel.includes('width: min(100%, 1120px)') &&
    cctvLivePanel.includes('min-height: 0') &&
    !cctvLivePanel.includes('min-height: 430px') &&
    !cctvLivePanel.includes('min-height: 360px'),
  'embedded dashboard CCTV must reserve a tall stage for the full 11-camera nested layout without forcing internal scroll',
)

assert(
  cctvLivePanel.includes('.cctv-live-panel--compact {') &&
    cctvLivePanel.includes('box-shadow: none') &&
    cctvLivePanel.includes('.cctv-live-panel--compact .cctv-live-panel__player-shell') &&
    cctvLivePanel.includes('border: 0'),
  'compact dashboard CCTV must remove outer card/player bbox chrome',
)

assert(
  workbench.indexOf('class="panel video-detection-panel"') < workbench.indexOf('<StatusStrip'),
  'guardian dashboard must place video detection before KPI strips so reports stay near the top',
)

assert(
  workbench.indexOf('class="video-camera-picker"') < workbench.indexOf('<CctvLivePanel') &&
    workbench.indexOf('<CctvLivePanel') < workbench.indexOf('<StatusStrip'),
  'guardian dashboard must keep camera selection adjacent to the CCTV live view',
)

assert(
  !workbench.includes('class="video-detection-camera-results"') &&
    !workbench.includes('class="video-detection-camera-card"'),
  'guardian dashboard must not render per-camera annotated evidence cards inline',
)

assert(
  workbench.includes('查看证据') && workbench.includes("goTo('hazard-ledger')"),
  'guardian dashboard must expose evidence as a ledger/history entry instead of a large inline image',
)

for (const token of ['toolResults', 'cards', 'status', '执行中', 'chatbot-card', 'chatbot-tool-result']) {
  assert(chatbotPanel.includes(token), `chatbot panel must render workflow execution state and structured results: ${token}`)
}

for (const token of ['configText', 'saveSkillConfig', '配置 JSON', '/config']) {
  assert(
    skillsPage.includes(token) || api.includes(token),
    `skill page must allow editing sidecar source/keyword config: ${token}`,
  )
}

assert(
  workbench.includes('class="video-prompt-settings"') && workbench.includes('<summary>'),
  'guardian dashboard must keep prompt editing inside collapsed settings',
)

assert(
  workbench.includes('.video-prompt-settings:not([open]) .video-prompt-block'),
  'guardian dashboard must explicitly hide prompt controls while prompt settings are collapsed',
)

assert(
  hazardLedger.includes('视觉检测历史') && hazardLedger.includes('listWorkbenchVideoDetections'),
  'hazard ledger must show detailed video detection history',
)

assert(
  hazardLedger.includes('fallback_used') &&
    hazardLedger.includes('回退图') &&
    hazardLedger.includes('fallback_reason'),
  'hazard ledger video history must visibly mark fallback sample frames',
)

assert(
  api.includes('runWorkbenchVideoDetection') &&
    api.includes('listWorkbenchVideoDetections') &&
    api.includes('refineWorkbenchVideoDetectionPrompt'),
  'frontend API client must expose workbench video detection methods',
)
