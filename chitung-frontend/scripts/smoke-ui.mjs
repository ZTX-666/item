import { readFileSync } from 'node:fs'

const files = {
  workbench: 'src/pages/WorkbenchPage.vue',
  reports: 'src/pages/ReportsPage.vue',
  settings: 'src/components/system/SystemSettingsPanel.vue',
  camera: 'src/components/cards/CameraGrid.vue',
  externalRisk: 'src/pages/ExternalRiskMonitorPage.vue',
  api: 'src/services/chitungApi.ts',
  router: 'src/router/index.ts',
  panelSidebar: 'src/components/layout/PanelSidebar.vue',
  cctvLivePanel: 'src/components/cctv/CctvLivePanel.vue',
}

const checks = [
  ['smart form button', files.workbench, '智能填表'],
  ['daily briefing button', files.workbench, '每日简报'],
  ['external risk monitor page', files.externalRisk, '外部舆情监听'],
  ['external risk execution process', files.externalRisk, '执行过程'],
  ['report generator page', files.reports, '报告生成'],
  ['output history panel', files.reports, '最近生成文件'],
  ['visual evidence button', files.camera, '打开证据'],
  ['connector settings form', files.settings, '保存连接器配置'],
  ['llm test button', files.settings, '测试连接'],
  ['service restart button', files.settings, '重启服务'],
  ['report api client', files.api, 'generateReport'],
  ['notification api client', files.api, 'sendCaseNotification'],
  ['cctv shared player component', files.cctvLivePanel, 'C-SMART CCTV player'],
  ['dashboard embeds cctv player', files.workbench, "import CctvLivePanel from '../components/cctv/CctvLivePanel.vue'"],
  ['visual patrol embeds cctv player', 'src/pages/VisualPatrolPage.vue', "import CctvLivePanel from '../components/cctv/CctvLivePanel.vue'"],
  ['cctv route redirects to patrol', files.router, "path: 'cctv', redirect: '/guardian/patrol'"],
]

let failed = false

for (const [name, path, token] of checks) {
  const content = readFileSync(path, 'utf8')
  if (!content.includes(token)) {
    failed = true
    console.error(`[FAIL] ${name}: missing "${token}" in ${path}`)
  } else {
    console.log(`[OK] ${name}`)
  }
}

const forbiddenChecks = [
  ['standalone cctv sidebar item', files.panelSidebar, 'CCTV 实时播放'],
  ['standalone cctv route component', files.router, "component: () => import('../pages/CctvPlayerPage.vue')"],
]

for (const [name, path, token] of forbiddenChecks) {
  const content = readFileSync(path, 'utf8')
  if (content.includes(token)) {
    failed = true
    console.error(`[FAIL] ${name}: unexpected "${token}" in ${path}`)
  } else {
    console.log(`[OK] ${name}`)
  }
}

if (failed) {
  process.exitCode = 1
}
