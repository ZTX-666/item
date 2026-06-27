const routeLoaders: Record<string, () => Promise<unknown>> = {
  '/guardian/dashboard': () => import('../pages/WorkbenchPage.vue'),
  '/guardian/confirmations': () => import('../pages/PendingConfirmationsPage.vue'),
  '/guardian/hazards': () => import('../pages/HazardLedgerPage.vue'),
  '/guardian/patrol': () => import('../pages/VisualPatrolPage.vue'),
  '/docmate/documents': () => import('../pages/ShanshanDocPage.vue'),
  '/docmate/forms': () => import('../pages/SmartFormPage.vue'),
  '/docmate/table-mapping': () => import('../pages/TableMappingPage.vue'),
  '/docmate/reports': () => import('../pages/ReportsPage.vue'),
  '/lingxun/whatsapp': () => import('../pages/WhatsAppOpsPage.vue'),
  '/lingxun/browse': () => import('../pages/WhatsAppOpsPage.vue'),
  '/lingxun/sql': () => import('../pages/WhatsAppOpsPage.vue'),
  '/lingxun/commands': () => import('../pages/WhatsAppOpsPage.vue'),
  '/center/settings': () => import('../pages/SystemSettingsPage.vue'),
  '/center/execution': () => import('../pages/ExecutionCenterPage.vue'),
  '/center/assistant': () => import('../pages/AIAssistantPage.vue'),
  '/center/automation': () => import('../pages/AutomationPage.vue'),
  '/center/skills': () => import('../pages/SkillsCompatPage.vue'),
  '/center/memory': () => import('../pages/LongTermMemoryPage.vue'),
  '/center/workflows': () => import('../pages/WorkflowsCompatPage.vue'),
  '/yaoyao/structured': () => import('../pages/YaoyaoStructuredInputPage.vue'),
  '/yaoyao/rag': () => import('../pages/YaoyaoKnowledgePage.vue'),
  '/yaoyao/feed': () => import('../pages/ExternalRiskMonitorPage.vue'),
  '/automation/inspection': () => import('../pages/AutomationPage.vue'),
  '/automation/workflows': () => import('../pages/AutomationPage.vue'),
}

const prefetched = new Set<string>()

export function prefetchRoute(path: string) {
  const loader = routeLoaders[path]
  if (!loader || prefetched.has(path)) return
  prefetched.add(path)
  void loader()
}

export function prefetchPanel(panel: string) {
  const firstPaths: Record<string, string> = {
    guardian: '/guardian/dashboard',
    docmate: '/docmate/documents',
    lingxun: '/lingxun/whatsapp',
    center: '/center/settings',
    yaoyao: '/yaoyao/structured',
  }
  const path = firstPaths[panel]
  if (path) prefetchRoute(path)
}
