import { readFileSync } from 'node:fs'

const files = {
  workbench: 'src/pages/WorkbenchPage.vue',
  settings: 'src/components/system/SystemSettingsPanel.vue',
  camera: 'src/components/cards/CameraGrid.vue',
  api: 'src/services/chitungApi.ts',
  router: 'src/router/index.ts',
  panelSidebar: 'src/components/layout/PanelSidebar.vue',
}

const checks = [
  ['smart form button', files.workbench, '智能填表'],
  ['daily briefing button', files.workbench, '每日简报'],
  ['report generator panel', files.workbench, '报告生成'],
  ['output history panel', files.workbench, '最近生成文件'],
  ['visual evidence button', files.camera, '打开证据'],
  ['connector settings form', files.settings, '保存连接器配置'],
  ['llm test button', files.settings, '测试连接'],
  ['service restart button', files.settings, '重启服务'],
  ['report api client', files.api, 'generateReport'],
  ['notification api client', files.api, 'sendCaseNotification'],
  ['cctv route', files.router, 'guardian-cctv'],
  ['cctv sidebar item', files.panelSidebar, 'CCTV 实时播放'],
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

if (failed) {
  process.exitCode = 1
}
