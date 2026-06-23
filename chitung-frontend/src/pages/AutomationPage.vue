<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { getAppConfig, runVisualPatrolBatch } from '../services/chitungApi'
import type { AppConfig } from '../types/domain'

type AutomationView = 'inspection' | 'workflows'
type TaskStatus = 'ACTIVE' | 'PAUSED'
type RunStatus = 'running' | 'success' | 'failed'
type TriggeredBy = 'scheduler' | 'manual'
type ScheduleType = 'once' | 'recurring'
type TemplateCategory = 'inspection' | 'monitoring' | 'security' | 'custom'
type FieldValue = string | number | string[]

interface TemplateField {
  key: string
  label: string
  type: 'text' | 'textarea' | 'number' | 'email' | 'select' | 'multiselect' | 'tags' | 'schedule_builder'
  required?: boolean
  placeholder?: string
  default?: FieldValue
  options?: string[]
}

interface AutomationTemplate {
  id: string
  name: string
  description: string
  icon: string
  category: TemplateCategory
  defaultPrompt: string
  defaultRrule: string
  defaultScheduleType: ScheduleType
  fields: TemplateField[]
}

interface AutomationTask {
  id: string
  name: string
  prompt: string
  scheduleType: ScheduleType
  rrule: string
  scheduledAt: string | null
  status: TaskStatus
  validFrom: string | null
  validUntil: string | null
  templateId: string | null
  cwds: string
  modelId: string | null
  createdAt: string
  updatedAt: string
  fieldValues?: Record<string, FieldValue>
  cameraIds?: string[]
  nextRunAt?: string | null
  lastRun?: {
    status: RunStatus
    finishedAt: string | null
    resultSummary: string | null
  } | null
}

interface AutomationRun {
  id: string
  taskId: string
  triggeredBy: TriggeredBy
  status: RunStatus
  startedAt: string
  finishedAt: string | null
  resultSummary: string | null
  errorMessage: string | null
}

interface AiSetupResult {
  suggested_template: string
  suggested_name: string
  suggested_prompt: string
  suggested_rrule: string
  prefilled_fields: Record<string, FieldValue>
  confidence: number
  explanation: string
}

const TASKS_KEY = 'chitung.automation.tasks.v2'
const RUNS_KEY = 'chitung.automation.runs.v2'
const SAFETY_PATROL_TASK_ID = 'auto_safety_ppe_smoking_30min'
const SAFETY_PATROL_PROMPT = '检测工人是否佩戴安全帽、PPE，是否有工人在抽烟。请对项目启用摄像头执行视觉巡检，生成巡检报告，并标记高风险画面。'

const templates: AutomationTemplate[] = [
  {
    id: 'tpl_visual_inspection',
    name: '视觉巡检',
    description: '定期截图并对比目标页面/摄像头状态，检测异常变化',
    icon: '👁',
    category: 'inspection',
    defaultPrompt: '请对目标系统 {{target_url}} 执行视觉巡检：\n1. 访问目标页面并截图\n2. 与上一次截图进行像素级对比\n3. 检测布局异常、元素缺失、错误提示\n4. 生成巡检报告，包含：正常项、异常项、截图对比\n5. 如有异常，标记严重等级（低/中/高）',
    defaultRrule: 'RRULE:FREQ=HOURLY;INTERVAL=6',
    defaultScheduleType: 'recurring',
    fields: [
      { key: 'target_url', label: '目标地址', type: 'text', required: true, placeholder: '摄像头巡检可填写项目区域或 URL' },
      { key: 'alert_threshold', label: '告警阈值（变化率%）', type: 'number', default: 5 },
    ],
  },
  {
    id: 'tpl_sentiment',
    name: '舆情抓取',
    description: '定期抓取指定关键词在主流平台的舆情动态，生成分析摘要',
    icon: '📡',
    category: 'monitoring',
    defaultPrompt: '请执行舆情监控任务：\n关键词：{{keywords}}\n监控平台：{{platforms}}\n\n任务步骤：\n1. 搜索过去 {{time_range}} 内与关键词相关的内容\n2. 统计正面/负面/中性情感分布\n3. 提取热度最高的 10 条内容及链接\n4. 识别舆情趋势（上升/平稳/下降）\n5. 输出舆情报告（含摘要、情感分布图数据、风险预警）',
    defaultRrule: 'RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0',
    defaultScheduleType: 'recurring',
    fields: [
      { key: 'keywords', label: '监控关键词', type: 'tags', required: true, placeholder: '项目名、公司名、风险词...' },
      { key: 'platforms', label: '监控平台', type: 'multiselect', options: ['微博', '微信', '抖音', '知乎', 'Twitter', 'Reddit'], default: ['微博', '知乎'] },
      { key: 'time_range', label: '时间范围', type: 'select', options: ['24小时', '7天', '30天'], default: '24小时' },
    ],
  },
  {
    id: 'tpl_security_report',
    name: '安全报告',
    description: '定期扫描系统安全状态，检测漏洞、异常访问和配置风险',
    icon: '🛡',
    category: 'security',
    defaultPrompt: '请执行安全巡检任务，目标系统：{{target_system}}\n\n检查项目：\n1. 检查最近 {{time_range}} 的异常登录尝试（IP、时间、频率）\n2. 扫描已知 CVE 漏洞（版本匹配）\n3. 检查不安全的配置项\n4. 分析访问日志中的异常流量模式\n5. 汇总输出安全报告：风险等级、漏洞描述、修复建议、趋势对比',
    defaultRrule: 'RRULE:FREQ=WEEKLY;BYDAY=MO;BYHOUR=9;BYMINUTE=0',
    defaultScheduleType: 'recurring',
    fields: [
      { key: 'target_system', label: '目标系统名称/IP', type: 'text', required: true },
      { key: 'time_range', label: '扫描时间范围', type: 'select', options: ['24小时', '7天', '30天'], default: '7天' },
      { key: 'notify_email', label: '报告接收邮箱', type: 'email' },
    ],
  },
  {
    id: 'tpl_custom',
    name: '自定义工作流',
    description: '从零开始，自由配置 AI 执行任何周期性任务',
    icon: '⚙',
    category: 'custom',
    defaultPrompt: '',
    defaultRrule: 'RRULE:FREQ=DAILY;BYHOUR=8;BYMINUTE=0',
    defaultScheduleType: 'recurring',
    fields: [
      { key: 'prompt', label: 'AI 执行指令', type: 'textarea', required: true, placeholder: '描述你希望 AI 定期执行的任务...' },
      { key: 'schedule_desc', label: '执行频率', type: 'schedule_builder', required: true },
    ],
  },
]

const router = useRouter()
const appConfig = ref<AppConfig | null>(null)
const tasks = ref<AutomationTask[]>([])
const runs = ref<AutomationRun[]>([])
const loading = ref(false)
const runningTaskId = ref('')
const expandedTaskId = ref('')
const message = ref('')
const statusFilter = ref<'ALL' | TaskStatus>('ALL')
const categoryFilter = ref<'ALL' | TemplateCategory>('ALL')

const drawerOpen = ref(false)
const selectedTemplateId = ref('tpl_visual_inspection')
const selectedTaskId = ref('')
const fieldValues = reactive<Record<string, FieldValue>>({})
const drawerForm = reactive({
  name: '',
  prompt: '',
  scheduleType: 'recurring' as ScheduleType,
  rrule: '',
  scheduledAt: '',
  simpleFrequency: 'every6hours',
  time: '08:00',
  weekday: 'MO',
  validFrom: '',
  validUntil: '',
  cwds: '',
  modelId: '',
  cameraIds: [] as string[],
})

const aiDescription = ref('')
const aiLoading = ref(false)
const aiResult = ref<AiSetupResult | null>(null)
const aiError = ref('')
let automationTimer: number | undefined

const enabledCameras = computed(() => (appConfig.value?.cameras ?? []).filter((camera) => camera.enabled))
const activeTasks = computed(() => tasks.value.filter((task) => task.status === 'ACTIVE'))
const todayRuns = computed(() => {
  const today = new Date().toDateString()
  return runs.value.filter((run) => new Date(run.startedAt).toDateString() === today)
})
const failedRuns = computed(() => runs.value.filter((run) => run.status === 'failed'))
const selectedTemplate = computed(() => templates.find((template) => template.id === selectedTemplateId.value) ?? templates[0])

const filteredTasks = computed(() => {
  return tasks.value.filter((task) => {
    const template = templateById(task.templateId)
    const statusOk = statusFilter.value === 'ALL' || task.status === statusFilter.value
    const categoryOk = categoryFilter.value === 'ALL' || template?.category === categoryFilter.value
    return statusOk && categoryOk
  })
})

watch(selectedTemplateId, () => {
  if (!drawerOpen.value) return
  applyTemplateDefaults(selectedTemplate.value)
})

onMounted(async () => {
  loadLocalData()
  ensureVisibleSafetyPatrolTask()
  ensureStarterTask()
  await refreshRuntimeData()
  startAutomationScheduler()
})

onBeforeUnmount(() => {
  if (automationTimer) window.clearInterval(automationTimer)
})

async function refreshRuntimeData() {
  loading.value = true
  try {
    appConfig.value = await getAppConfig()
  } catch (error) {
    message.value = `自动化运行数据加载失败：${formatError(error)}`
  } finally {
    loading.value = false
  }
}

function loadLocalData() {
  tasks.value = readStoredArray<AutomationTask>(TASKS_KEY)
  runs.value = readStoredArray<AutomationRun>(RUNS_KEY)
}

function readStoredArray<T>(key: string): T[] {
  try {
    const raw = localStorage.getItem(key)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function persist() {
  localStorage.setItem(TASKS_KEY, JSON.stringify(tasks.value))
  localStorage.setItem(RUNS_KEY, JSON.stringify(runs.value))
}

function ensureStarterTask() {
  if (tasks.value.length) return
  const template = templates[0]
  const now = new Date().toISOString()
  tasks.value = [{
    id: generateId('auto'),
    name: '每日工地视觉巡检',
    prompt: '请对项目启用摄像头执行视觉巡检，检查人员 PPE、机械作业半径、隔离围挡和明显安全隐患，生成巡检报告。',
    scheduleType: 'recurring',
    rrule: template.defaultRrule,
    scheduledAt: null,
    status: 'ACTIVE',
    validFrom: null,
    validUntil: null,
    templateId: template.id,
    cwds: '',
    modelId: null,
    createdAt: now,
    updatedAt: now,
    fieldValues: { target_url: appConfig.value?.project?.name || '项目摄像头', alert_threshold: 5 },
    cameraIds: [],
    nextRunAt: estimateNextRunAt(template.defaultRrule),
    lastRun: null,
  }]
  persist()
}

function ensureVisibleSafetyPatrolTask() {
  const now = new Date().toISOString()
  const existing = tasks.value.find((task) => task.id === SAFETY_PATROL_TASK_ID)
  const task: AutomationTask = {
    id: SAFETY_PATROL_TASK_ID,
    name: '30分钟安全帽/PPE/抽烟自动巡检',
    prompt: SAFETY_PATROL_PROMPT,
    scheduleType: 'recurring',
    rrule: 'RRULE:FREQ=MINUTELY;INTERVAL=30',
    scheduledAt: null,
    status: 'ACTIVE',
    validFrom: null,
    validUntil: null,
    templateId: 'tpl_visual_inspection',
    cwds: '',
    modelId: null,
    createdAt: existing?.createdAt || now,
    updatedAt: now,
    fieldValues: { target_url: appConfig.value?.project?.name || '项目摄像头', alert_threshold: 5 },
    cameraIds: existing?.cameraIds ?? [],
    nextRunAt: existing?.nextRunAt || estimateNextRunAt('RRULE:FREQ=MINUTELY;INTERVAL=30'),
    lastRun: existing?.lastRun ?? null,
  }
  if (existing) Object.assign(existing, task)
  else tasks.value.unshift(task)
  persist()
}

function switchView(view: AutomationView) {
  router.push({ path: '/center/automation', query: { tab: view } })
}

function openCreateDrawer(template = selectedTemplate.value) {
  selectedTaskId.value = ''
  selectedTemplateId.value = template.id
  drawerOpen.value = true
  applyTemplateDefaults(template)
}

function openEditDrawer(task: AutomationTask) {
  selectedTaskId.value = task.id
  selectedTemplateId.value = task.templateId || 'tpl_custom'
  drawerOpen.value = true
  clearFieldValues()
  Object.assign(fieldValues, task.fieldValues ?? {})
  drawerForm.name = task.name
  drawerForm.prompt = task.prompt
  drawerForm.scheduleType = task.scheduleType
  drawerForm.rrule = task.rrule
  drawerForm.scheduledAt = toLocalDateTime(task.scheduledAt)
  drawerForm.validFrom = toLocalDate(task.validFrom)
  drawerForm.validUntil = toLocalDate(task.validUntil)
  drawerForm.cwds = task.cwds
  drawerForm.modelId = task.modelId ?? ''
  drawerForm.cameraIds = [...(task.cameraIds ?? [])]
  deriveSimpleSchedule(task.rrule)
}

function closeDrawer() {
  drawerOpen.value = false
  selectedTaskId.value = ''
}

function applyTemplateDefaults(template: AutomationTemplate) {
  clearFieldValues()
  for (const field of template.fields) {
    if (field.default !== undefined) fieldValues[field.key] = Array.isArray(field.default) ? [...field.default] : field.default
    else if (field.type === 'multiselect' || field.type === 'tags') fieldValues[field.key] = []
    else fieldValues[field.key] = ''
  }
  drawerForm.name = `${template.name}_${new Date().toISOString().slice(0, 10)}`
  drawerForm.prompt = template.defaultPrompt
  drawerForm.scheduleType = template.defaultScheduleType
  drawerForm.rrule = template.defaultRrule
  drawerForm.scheduledAt = ''
  drawerForm.validFrom = ''
  drawerForm.validUntil = ''
  drawerForm.cwds = ''
  drawerForm.modelId = ''
  drawerForm.cameraIds = []
  deriveSimpleSchedule(template.defaultRrule)
}

function clearFieldValues() {
  for (const key of Object.keys(fieldValues)) delete fieldValues[key]
}

function saveTask() {
  const template = selectedTemplate.value
  const prompt = drawerForm.prompt.trim() || replaceVariables(template.defaultPrompt, fieldValues)
  if (!drawerForm.name.trim()) {
    message.value = '请填写工作流名称。'
    return
  }
  if (!prompt.trim()) {
    message.value = '请填写 AI 执行指令。'
    return
  }
  const now = new Date().toISOString()
  const existing = tasks.value.find((task) => task.id === selectedTaskId.value)
  const task: AutomationTask = {
    id: existing?.id || generateId('auto'),
    name: drawerForm.name.trim(),
    prompt,
    scheduleType: drawerForm.scheduleType,
    rrule: drawerForm.scheduleType === 'recurring' ? drawerForm.rrule.trim() : '',
    scheduledAt: drawerForm.scheduleType === 'once' ? fromLocalDateTime(drawerForm.scheduledAt) : null,
    status: existing?.status || 'ACTIVE',
    validFrom: fromLocalDate(drawerForm.validFrom),
    validUntil: fromLocalDate(drawerForm.validUntil),
    templateId: template.id,
    cwds: drawerForm.cwds.trim(),
    modelId: drawerForm.modelId.trim() || null,
    createdAt: existing?.createdAt || now,
    updatedAt: now,
    fieldValues: { ...fieldValues },
    cameraIds: [...drawerForm.cameraIds],
    nextRunAt: drawerForm.scheduleType === 'recurring' ? estimateNextRunAt(drawerForm.rrule) : fromLocalDateTime(drawerForm.scheduledAt),
    lastRun: existing?.lastRun ?? null,
  }
  const index = tasks.value.findIndex((item) => item.id === task.id)
  if (index >= 0) tasks.value.splice(index, 1, task)
  else tasks.value.unshift(task)
  persist()
  closeDrawer()
  message.value = '工作流已保存。当前为本地 JSON 形态缓存，后端 /api/automation 接入后可直接迁移。'
  switchView('workflows')
}

function toggleTask(task: AutomationTask) {
  task.status = task.status === 'ACTIVE' ? 'PAUSED' : 'ACTIVE'
  task.updatedAt = new Date().toISOString()
  task.nextRunAt = task.status === 'ACTIVE'
    ? (task.scheduleType === 'recurring' ? estimateNextRunAt(task.rrule) : task.scheduledAt)
    : null
  persist()
}

function deleteTask(task: AutomationTask) {
  tasks.value = tasks.value.filter((item) => item.id !== task.id)
  runs.value = runs.value.filter((run) => run.taskId !== task.id)
  persist()
}

async function triggerTask(task: AutomationTask, triggeredBy: TriggeredBy = 'manual') {
  runningTaskId.value = task.id
  const run: AutomationRun = {
    id: generateId('run'),
    taskId: task.id,
    triggeredBy,
    status: 'running',
    startedAt: new Date().toISOString(),
    finishedAt: null,
    resultSummary: null,
    errorMessage: null,
  }
  runs.value.unshift(run)
  persist()
  try {
    const template = templateById(task.templateId)
    if (template?.id === 'tpl_visual_inspection') {
      const cameraId = task.cameraIds?.length === 1 ? task.cameraIds[0] : undefined
      const result = await runVisualPatrolBatch({ cameraId, vlmEnabled: true, yoloOnly: false })
      if (!result.ok || !result.report) throw new Error(result.error || '视觉巡检未返回报告')
      run.status = 'success'
      run.resultSummary = `巡检完成：${result.report.success_count ?? 0}/${result.report.camera_count ?? 0} 路成功，检测 ${result.report.total_detections ?? 0} 个目标`
    } else {
      run.status = 'success'
      run.resultSummary = `已创建手动执行记录。后端 /api/automation 接入后将把 prompt 发送给 AI 执行：${task.prompt.slice(0, 80)}`
    }
    run.finishedAt = new Date().toISOString()
    task.lastRun = { status: run.status, finishedAt: run.finishedAt, resultSummary: run.resultSummary }
    task.nextRunAt = task.scheduleType === 'recurring' ? estimateNextRunAt(task.rrule) : null
    task.updatedAt = new Date().toISOString()
    await refreshRuntimeData()
    message.value = run.resultSummary || '执行完成。'
  } catch (error) {
    run.status = 'failed'
    run.finishedAt = new Date().toISOString()
    run.errorMessage = formatError(error)
    task.lastRun = { status: 'failed', finishedAt: run.finishedAt, resultSummary: run.errorMessage }
    message.value = `执行失败：${run.errorMessage}`
  } finally {
    runningTaskId.value = ''
    persist()
  }
}

function taskRuns(taskId: string) {
  return runs.value.filter((run) => run.taskId === taskId).slice(0, 5)
}

function startAutomationScheduler() {
  if (automationTimer) window.clearInterval(automationTimer)
  automationTimer = window.setInterval(checkDueTasks, 30_000)
  checkDueTasks()
}

function checkDueTasks() {
  if (runningTaskId.value) return
  const now = Date.now()
  const dueTask = tasks.value.find((task) => {
    if (task.status !== 'ACTIVE' || task.scheduleType !== 'recurring' || !task.nextRunAt) return false
    return new Date(task.nextRunAt).getTime() <= now
  })
  if (dueTask) triggerTask(dueTask, 'scheduler')
}

async function runAiSetup() {
  if (!aiDescription.value.trim()) {
    aiError.value = '请先输入自然语言需求。'
    return
  }
  aiLoading.value = true
  aiError.value = ''
  aiResult.value = null
  try {
    const response = await fetch(`${centerBaseUrl()}/api/automation/ai-setup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ description: aiDescription.value.trim() }),
    })
    if (!response.ok) throw new Error(`AI 智能配置接口暂不可用：${response.status}`)
    aiResult.value = await response.json() as AiSetupResult
  } catch {
    aiResult.value = heuristicAiSetup(aiDescription.value.trim())
    aiError.value = '后端 AI 智能配置接口尚未接入，已使用本地规则预填。'
  } finally {
    aiLoading.value = false
  }
  applyAiResult()
}

function applyAiResult() {
  if (!aiResult.value) return
  const template = templates.find((item) => item.id === aiResult.value?.suggested_template) ?? templates[3]
  openCreateDrawer(template)
  drawerForm.name = aiResult.value.suggested_name
  drawerForm.prompt = aiResult.value.suggested_prompt
  drawerForm.rrule = aiResult.value.suggested_rrule
  drawerForm.scheduleType = 'recurring'
  deriveSimpleSchedule(drawerForm.rrule)
  clearFieldValues()
  Object.assign(fieldValues, aiResult.value.prefilled_fields)
}

function heuristicAiSetup(description: string): AiSetupResult {
  const lower = description.toLowerCase()
  const isSentiment = /舆情|微博|知乎|抖音|关键词|sentiment/.test(description)
  const isSecurity = /安全|漏洞|登录|端口|security|cve/.test(lower)
  const isVisual = /巡检|检查|摄像头|官网|页面|截图|visual|website/.test(lower)
  const template = isSentiment ? templates[1] : isSecurity ? templates[2] : isVisual ? templates[0] : templates[3]
  const rrule = parseRruleFromText(description)
  const fields: Record<string, FieldValue> = {}
  if (template.id === 'tpl_visual_inspection') fields.target_url = extractUrl(description) || '项目摄像头'
  if (template.id === 'tpl_sentiment') fields.keywords = description.replace(/每天|每周|定期|帮我|监控|舆情/g, '').trim().split(/[，,\s]+/).filter(Boolean).slice(0, 6)
  if (template.id === 'tpl_security_report') fields.target_system = extractUrl(description) || '目标系统'
  if (template.id === 'tpl_custom') fields.prompt = description
  return {
    suggested_template: template.id,
    suggested_name: `${template.name}_${new Date().toISOString().slice(0, 10)}`,
    suggested_prompt: template.id === 'tpl_custom' ? description : replaceVariables(template.defaultPrompt, fields),
    suggested_rrule: rrule,
    prefilled_fields: fields,
    confidence: 0.62,
    explanation: '后端 LLM 接口尚未接入，前端根据关键词、时间表达和 URL 做了本地预填。',
  }
}

function parseRruleFromText(text: string): string {
  const hourMatch = text.match(/(\d{1,2})\s*[点:：时]/)
  const hour = hourMatch ? Math.min(23, Number(hourMatch[1])) : 8
  if (/每\s*30\s*分|30\s*min|30\s*minutes/i.test(text)) return 'RRULE:FREQ=MINUTELY;INTERVAL=30'
  if (/每\s*6\s*小?时|6\s*hours/i.test(text)) return 'RRULE:FREQ=HOURLY;INTERVAL=6'
  if (/每小时|hourly/i.test(text)) return 'RRULE:FREQ=HOURLY'
  if (/每周|weekly/i.test(text)) return `RRULE:FREQ=WEEKLY;BYDAY=MO;BYHOUR=${hour};BYMINUTE=0`
  if (/每月|monthly/i.test(text)) return 'RRULE:FREQ=MONTHLY;BYMONTHDAY=1'
  return `RRULE:FREQ=DAILY;BYHOUR=${hour};BYMINUTE=0`
}

function replaceVariables(prompt: string, values: Record<string, FieldValue>): string {
  return prompt.replace(/\{\{(\w+)\}\}/g, (match, key) => {
    const value = values[key]
    if (value === undefined || value === null || value === '') return match
    return Array.isArray(value) ? value.join('、') : String(value)
  })
}

function updatePromptFromFields() {
  drawerForm.prompt = replaceVariables(selectedTemplate.value.defaultPrompt, fieldValues)
}

function setSimpleSchedule(value: string) {
  drawerForm.simpleFrequency = value
  const [hour = '8', minute = '0'] = drawerForm.time.split(':')
  if (value === 'every30min') drawerForm.rrule = 'RRULE:FREQ=MINUTELY;INTERVAL=30'
  else if (value === 'hourly') drawerForm.rrule = 'RRULE:FREQ=HOURLY'
  else if (value === 'every6hours') drawerForm.rrule = 'RRULE:FREQ=HOURLY;INTERVAL=6'
  else if (value === 'daily') drawerForm.rrule = `RRULE:FREQ=DAILY;BYHOUR=${Number(hour)};BYMINUTE=${Number(minute)}`
  else if (value === 'weekly') drawerForm.rrule = `RRULE:FREQ=WEEKLY;BYDAY=${drawerForm.weekday};BYHOUR=${Number(hour)};BYMINUTE=${Number(minute)}`
  else if (value === 'monthly') drawerForm.rrule = 'RRULE:FREQ=MONTHLY;BYMONTHDAY=1'
}

function deriveSimpleSchedule(rrule: string) {
  if (rrule.includes('FREQ=MINUTELY;INTERVAL=30')) drawerForm.simpleFrequency = 'every30min'
  else if (rrule.includes('FREQ=HOURLY;INTERVAL=6')) drawerForm.simpleFrequency = 'every6hours'
  else if (rrule.includes('FREQ=HOURLY')) drawerForm.simpleFrequency = 'hourly'
  else if (rrule.includes('FREQ=WEEKLY')) drawerForm.simpleFrequency = 'weekly'
  else if (rrule.includes('FREQ=MONTHLY')) drawerForm.simpleFrequency = 'monthly'
  else drawerForm.simpleFrequency = 'daily'
  const hour = rrule.match(/BYHOUR=(\d+)/)?.[1]
  const minute = rrule.match(/BYMINUTE=(\d+)/)?.[1] ?? '0'
  if (hour) drawerForm.time = `${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`
  const weekday = rrule.match(/BYDAY=([A-Z]{2})/)?.[1]
  if (weekday) drawerForm.weekday = weekday
}

function estimateNextRunAt(rrule?: string): string | null {
  if (!rrule) return null
  const now = new Date()
  if (rrule.includes('FREQ=MINUTELY')) {
    const interval = Number(rrule.match(/INTERVAL=(\d+)/)?.[1] ?? 1)
    return new Date(now.getTime() + interval * 60 * 1000).toISOString()
  }
  if (rrule.includes('FREQ=HOURLY')) {
    const interval = Number(rrule.match(/INTERVAL=(\d+)/)?.[1] ?? 1)
    return new Date(now.getTime() + interval * 60 * 60 * 1000).toISOString()
  }
  const hour = Number(rrule.match(/BYHOUR=(\d+)/)?.[1] ?? 8)
  const minute = Number(rrule.match(/BYMINUTE=(\d+)/)?.[1] ?? 0)
  const next = new Date(now)
  next.setHours(hour, minute, 0, 0)
  if (rrule.includes('FREQ=WEEKLY')) {
    const weekdayMap: Record<string, number> = { SU: 0, MO: 1, TU: 2, WE: 3, TH: 4, FR: 5, SA: 6 }
    const byday = rrule.match(/BYDAY=([A-Z]{2})/)?.[1] ?? 'MO'
    const delta = (weekdayMap[byday] - next.getDay() + 7) % 7
    next.setDate(next.getDate() + delta)
  }
  if (rrule.includes('FREQ=MONTHLY')) {
    const day = Number(rrule.match(/BYMONTHDAY=(\d+)/)?.[1] ?? 1)
    next.setDate(day)
  }
  if (next <= now) next.setDate(next.getDate() + (rrule.includes('FREQ=WEEKLY') ? 7 : rrule.includes('FREQ=MONTHLY') ? 30 : 1))
  return next.toISOString()
}

function templateById(id?: string | null) {
  return templates.find((template) => template.id === id)
}

function categoryLabel(category?: TemplateCategory) {
  const labels: Record<TemplateCategory, string> = { inspection: '巡检', monitoring: '监控', security: '安全', custom: '自定义' }
  return category ? labels[category] : '自动化'
}

function statusLabel(status: TaskStatus) {
  return status === 'ACTIVE' ? '运行中' : '已暂停'
}

function runStatusLabel(status?: RunStatus) {
  if (status === 'running') return '执行中'
  if (status === 'failed') return '失败'
  return '成功'
}

function formatTime(value?: string | null) {
  if (!value) return '待计算'
  return new Intl.DateTimeFormat('zh-Hans-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}

function centerBaseUrl() {
  return import.meta.env.VITE_CHITUNG_CENTER_URL?.replace(/\/$/, '') || 'http://127.0.0.1:8999'
}

function generateId(prefix: 'auto' | 'run') {
  return `${prefix}_${Math.random().toString(16).slice(2, 10)}`
}

function formatError(error: unknown) {
  return error instanceof Error ? error.message : String(error)
}

function extractUrl(text: string) {
  return text.match(/https?:\/\/[^\s，。]+/)?.[0] ?? ''
}

function toLocalDate(value?: string | null) {
  return value ? value.slice(0, 10) : ''
}

function toLocalDateTime(value?: string | null) {
  return value ? value.slice(0, 16) : ''
}

function fromLocalDate(value: string) {
  return value ? new Date(`${value}T00:00:00`).toISOString() : null
}

function fromLocalDateTime(value: string) {
  return value ? new Date(value).toISOString() : null
}
</script>

<template>
  <main class="workbench wb-auto">
    <section class="hero-panel wb-auto-hero">
      <div>
        <p class="eyebrow">自动化编排</p>
        <h1>自动化工作流</h1>
        <p>从模板或自然语言创建自动化任务，用 RRULE 管理定时规则，并为后端 `/api/automation` 调度器预留接口。</p>
      </div>
      <button class="primary-soft-button" @click="openCreateDrawer()">新建工作流</button>
    </section>

    <section class="wb-auto-stats">
      <article class="status-card status-card--green">
        <span class="status-card__label">运行中</span>
        <div class="status-card__value">{{ activeTasks.length }}</div>
        <span class="status-card__helper">正在启用的工作流</span>
      </article>
      <article class="status-card status-card--blue">
        <span class="status-card__label">今日执行</span>
        <div class="status-card__value">{{ todayRuns.length }}</div>
        <span class="status-card__helper">本地 run 记录</span>
      </article>
      <article class="status-card status-card--red">
        <span class="status-card__label">异常</span>
        <div class="status-card__value">{{ failedRuns.length }}</div>
        <span class="status-card__helper">执行失败记录</span>
      </article>
      <article class="status-card status-card--orange">
        <span class="status-card__label">摄像头</span>
        <div class="status-card__value">{{ enabledCameras.length }}</div>
        <span class="status-card__helper">来自系统设置</span>
      </article>
    </section>

    <p v-if="message" class="wb-auto-banner">{{ message }}</p>

    <section class="wb-auto-workflow-layout">
      <div class="wb-auto-workflow-main">
        <section class="panel">
          <div class="panel__header">
            <div>
              <h2>AI 智能配置</h2>
              <p>用自然语言描述需求，后端接入后调用 `/api/automation/ai-setup`；当前提供本地降级预填。</p>
            </div>
          </div>
          <div class="wb-auto-ai-box">
            <textarea v-model="aiDescription" rows="4" placeholder="例如：每天早上8点帮我检查公司官网是否正常" />
            <button class="primary-soft-button" :disabled="aiLoading" @click="runAiSetup">
              {{ aiLoading ? '解析中...' : 'AI 智能配置' }}
            </button>
          </div>
          <p v-if="aiError" class="wb-auto-error">{{ aiError }}</p>
          <div v-if="aiResult" class="wb-auto-ai-result">
            <strong>{{ aiResult.suggested_name }} · 置信度 {{ Math.round(aiResult.confidence * 100) }}%</strong>
            <p>{{ aiResult.explanation }}</p>
            <code>{{ aiResult.suggested_rrule }}</code>
          </div>
        </section>

        <section class="panel">
          <div class="panel__header">
            <div>
              <h2>从模板创建</h2>
              <p>4 个内置模板与后端 `templates.json` 结构保持一致。</p>
            </div>
          </div>
          <div class="wb-auto-template-grid">
            <article
              v-for="template in templates"
              :key="template.id"
              class="wb-auto-template-card"
              :class="{ 'wb-auto-template-card--active': selectedTemplateId === template.id }"
              @click="openCreateDrawer(template)"
            >
              <span>{{ template.icon }}</span>
              <strong>{{ template.name }}</strong>
              <p>{{ template.description }}</p>
              <small>{{ categoryLabel(template.category) }} · {{ template.defaultRrule }}</small>
              <button class="wb-auto-use-template">使用模板</button>
            </article>
          </div>
        </section>
      </div>

      <aside class="panel">
        <div class="panel__header">
          <div>
            <h2>已建工作流</h2>
            <p>{{ filteredTasks.length }} / {{ tasks.length }} 个任务</p>
          </div>
        </div>
        <div class="wb-auto-filters">
          <select v-model="statusFilter">
            <option value="ALL">全部状态</option>
            <option value="ACTIVE">运行中</option>
            <option value="PAUSED">已暂停</option>
          </select>
          <select v-model="categoryFilter">
            <option value="ALL">全部分类</option>
            <option value="inspection">巡检</option>
            <option value="monitoring">监控</option>
            <option value="security">安全</option>
            <option value="custom">自定义</option>
          </select>
        </div>
        <div class="wb-auto-mini-list">
          <article v-for="task in filteredTasks" :key="task.id" class="wb-auto-mini-task">
            <div>
              <strong>{{ task.name }}</strong>
              <p>{{ statusLabel(task.status) }} · {{ categoryLabel(templateById(task.templateId)?.category) }}</p>
              <small>下次：{{ formatTime(task.nextRunAt) }} · 上次：{{ task.lastRun?.resultSummary || '暂无执行记录' }}</small>
            </div>
            <div class="wb-auto-mini-actions">
              <button class="mini-button" @click="toggleTask(task)">{{ task.status === 'ACTIVE' ? '暂停' : '激活' }}</button>
              <button class="mini-button" :disabled="!!runningTaskId" @click="triggerTask(task)">
                {{ runningTaskId === task.id ? '执行中...' : '运行' }}
              </button>
              <button class="mini-button" @click="expandedTaskId = expandedTaskId === task.id ? '' : task.id">历史</button>
              <button class="mini-button" @click="openEditDrawer(task)">编辑</button>
              <button class="mini-button" @click="deleteTask(task)">删除</button>
            </div>
            <div v-if="expandedTaskId === task.id" class="wb-auto-run-timeline wb-auto-run-timeline--mini">
              <article v-for="run in taskRuns(task.id)" :key="run.id" class="wb-auto-run-item">
                <span class="wb-auto-status-dot" :class="`wb-auto-status-${run.status}`" />
                <div>
                  <strong>{{ runStatusLabel(run.status) }} · {{ run.triggeredBy === 'manual' ? '手动' : '定时' }}</strong>
                  <p>{{ formatTime(run.startedAt) }} - {{ run.resultSummary || run.errorMessage || '执行中' }}</p>
                </div>
              </article>
              <p v-if="!taskRuns(task.id).length" class="wb-auto-empty">暂无执行历史。</p>
            </div>
          </article>
          <p v-if="!filteredTasks.length" class="wb-auto-empty">暂无匹配任务。</p>
        </div>
      </aside>
    </section>

    <div v-if="drawerOpen" class="wb-auto-drawer-mask" @click.self="closeDrawer">
      <aside class="wb-auto-drawer">
        <header>
          <div>
            <span class="wb-auto-drawer-icon">{{ selectedTemplate.icon }}</span>
            <strong>{{ selectedTemplate.name }}</strong>
          </div>
          <button class="mini-button" @click="closeDrawer">关闭</button>
        </header>

        <label>
          <span>工作流名称</span>
          <input v-model="drawerForm.name" />
        </label>

        <div class="wb-auto-field-grid">
          <label v-for="field in selectedTemplate.fields" :key="field.key">
            <span>{{ field.label }} <em v-if="field.required">*</em></span>
            <textarea
              v-if="field.type === 'textarea' || field.type === 'schedule_builder'"
              v-model="fieldValues[field.key] as string"
              rows="3"
              :placeholder="field.placeholder"
              @input="updatePromptFromFields"
            />
            <select
              v-else-if="field.type === 'select'"
              v-model="fieldValues[field.key] as string"
              @change="updatePromptFromFields"
            >
              <option v-for="option in field.options" :key="option" :value="option">{{ option }}</option>
            </select>
            <div v-else-if="field.type === 'multiselect'" class="wb-auto-choice-row">
              <label v-for="option in field.options" :key="option" class="wb-auto-check">
                <input
                  type="checkbox"
                  :checked="Array.isArray(fieldValues[field.key]) && (fieldValues[field.key] as string[]).includes(option)"
                  @change="fieldValues[field.key] = Array.isArray(fieldValues[field.key]) && (fieldValues[field.key] as string[]).includes(option) ? (fieldValues[field.key] as string[]).filter((item) => item !== option) : [...((fieldValues[field.key] as string[]) || []), option]; updatePromptFromFields()"
                />
                {{ option }}
              </label>
            </div>
            <input
              v-else
              v-model="fieldValues[field.key] as string"
              :type="field.type === 'number' ? 'number' : field.type === 'email' ? 'email' : 'text'"
              :placeholder="field.placeholder"
              @input="updatePromptFromFields"
            />
          </label>
        </div>

        <label>
          <span>AI 执行指令</span>
          <textarea v-model="drawerForm.prompt" rows="7" />
        </label>

        <section class="wb-auto-schedule-builder">
          <strong>调度规则</strong>
          <div class="wb-auto-drawer-grid">
            <label>
              <span>执行类型</span>
              <select v-model="drawerForm.scheduleType">
                <option value="recurring">周期</option>
                <option value="once">单次</option>
              </select>
            </label>
            <label v-if="drawerForm.scheduleType === 'once'">
              <span>执行时间</span>
              <input v-model="drawerForm.scheduledAt" type="datetime-local" />
            </label>
            <label v-if="drawerForm.scheduleType === 'recurring'">
              <span>简单频率</span>
              <select v-model="drawerForm.simpleFrequency" @change="setSimpleSchedule(drawerForm.simpleFrequency)">
                <option value="every30min">每 30 分钟</option>
                <option value="hourly">每小时</option>
                <option value="every6hours">每 6 小时</option>
                <option value="daily">每天</option>
                <option value="weekly">每周</option>
                <option value="monthly">每月 1 号</option>
              </select>
            </label>
            <label v-if="drawerForm.scheduleType === 'recurring' && ['daily', 'weekly'].includes(drawerForm.simpleFrequency)">
              <span>执行时间</span>
              <input v-model="drawerForm.time" type="time" @change="setSimpleSchedule(drawerForm.simpleFrequency)" />
            </label>
            <label v-if="drawerForm.scheduleType === 'recurring' && drawerForm.simpleFrequency === 'weekly'">
              <span>星期</span>
              <select v-model="drawerForm.weekday" @change="setSimpleSchedule(drawerForm.simpleFrequency)">
                <option value="MO">周一</option>
                <option value="TU">周二</option>
                <option value="WE">周三</option>
                <option value="TH">周四</option>
                <option value="FR">周五</option>
                <option value="SA">周六</option>
                <option value="SU">周日</option>
              </select>
            </label>
          </div>
          <label v-if="drawerForm.scheduleType === 'recurring'">
            <span>RRULE（高级）</span>
            <input v-model="drawerForm.rrule" />
          </label>
          <div class="wb-auto-drawer-grid">
            <label>
              <span>有效期开始</span>
              <input v-model="drawerForm.validFrom" type="date" />
            </label>
            <label>
              <span>有效期结束</span>
              <input v-model="drawerForm.validUntil" type="date" />
            </label>
          </div>
        </section>

        <section v-if="selectedTemplate.id === 'tpl_visual_inspection'" class="wb-auto-camera-section">
          <strong>项目摄像头（可选）</strong>
          <div class="wb-auto-camera-grid">
            <button
              v-for="camera in enabledCameras"
              :key="camera.id"
              :class="{ 'wb-auto-camera-active': drawerForm.cameraIds.includes(camera.id) }"
              @click="drawerForm.cameraIds = drawerForm.cameraIds.includes(camera.id) ? drawerForm.cameraIds.filter((id) => id !== camera.id) : [...drawerForm.cameraIds, camera.id]"
            >
              {{ camera.name }}
              <small>{{ camera.area }}</small>
            </button>
          </div>
        </section>

        <details>
          <summary>高级选项</summary>
          <div class="wb-auto-drawer-grid">
            <label>
              <span>绑定工作目录</span>
              <input v-model="drawerForm.cwds" placeholder="cwds" />
            </label>
            <label>
              <span>指定 AI 模型</span>
              <input v-model="drawerForm.modelId" placeholder="modelId" />
            </label>
          </div>
        </details>

        <footer>
          <button class="mini-button" @click="closeDrawer">取消</button>
          <button class="primary-soft-button" @click="saveTask">创建工作流 →</button>
        </footer>
      </aside>
    </div>
  </main>
</template>

<style scoped>
.wb-auto-tabs,
.wb-auto-stats,
.wb-auto-workflow-layout {
  display: grid;
  gap: 12px;
}

.wb-auto-tabs {
  grid-template-columns: repeat(2, minmax(0, 180px));
  margin-bottom: 16px;
}

.wb-auto-tabs button {
  background: var(--bg-white);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-weight: 700;
  padding: 10px 12px;
}

.wb-auto-tab--active {
  background: #f0f7ff !important;
  border-color: rgb(15 158 213 / 42%) !important;
  color: var(--brand-cyan-dark) !important;
}

.wb-auto-stats {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-bottom: 16px;
}

.wb-auto-banner,
.wb-auto-error {
  border-radius: var(--radius-md);
  margin-bottom: 12px;
  padding: 10px 12px;
}

.wb-auto-banner {
  background: #f6fbff;
  border: 1px solid #d7ecff;
  color: var(--text-secondary);
}

.wb-auto-error {
  background: #fff3f3;
  border: 1px solid #ffd4d4;
  color: var(--brand-red);
}

.wb-auto-task-list,
.wb-auto-mini-list,
.wb-auto-run-timeline {
  display: grid;
  gap: 12px;
}

.wb-auto-task-card,
.wb-auto-mini-task,
.wb-auto-run-item {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  padding: 12px;
}

.wb-auto-task-card {
  display: grid;
  gap: 12px;
}

.wb-auto-task-main,
.wb-auto-run-item {
  align-items: center;
  display: flex;
  gap: 12px;
  justify-content: space-between;
}

.wb-auto-mini-task {
  display: grid;
  gap: 10px;
}

.wb-auto-task-main {
  justify-content: flex-start;
}

.wb-auto-task-card p,
.wb-auto-task-card small,
.wb-auto-mini-task p,
.wb-auto-run-item p,
.wb-auto-template-card p,
.wb-auto-ai-result p,
.wb-auto-empty {
  color: var(--text-secondary);
  font-size: 12px;
  margin-top: 4px;
}

.wb-auto-actions,
.wb-auto-mini-actions,
.wb-auto-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.wb-auto-mini-actions {
  justify-content: flex-end;
}

.wb-auto-run-timeline--mini {
  background: var(--bg-subtle);
  border-radius: var(--radius-md);
  padding: 8px;
}

.wb-auto-status-dot {
  border-radius: 50%;
  flex: 0 0 auto;
  height: 10px;
  width: 10px;
}

.wb-auto-status-active,
.wb-auto-status-success {
  background: #22c55e;
}

.wb-auto-status-paused {
  background: #94a3b8;
}

.wb-auto-status-running {
  animation: wb-auto-pulse 1.5s ease-in-out infinite;
  background: #3b82f6;
}

.wb-auto-status-failed {
  background: #ef4444;
}

@keyframes wb-auto-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.wb-auto-workflow-layout {
  grid-template-columns: minmax(0, 1.3fr) 360px;
}

.wb-auto-workflow-main {
  display: grid;
  gap: 16px;
}

.wb-auto-ai-box {
  display: grid;
  gap: 10px;
}

.wb-auto-ai-box textarea,
.wb-auto-drawer textarea,
.wb-auto-drawer input,
.wb-auto-drawer select,
.wb-auto-filters select {
  border: 1px solid var(--border-normal);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  outline: none;
  padding: 9px 10px;
  width: 100%;
}

.wb-auto-ai-box textarea:focus,
.wb-auto-drawer textarea:focus,
.wb-auto-drawer input:focus,
.wb-auto-drawer select:focus {
  border-color: var(--brand-cyan);
  box-shadow: 0 0 0 3px rgb(15 158 213 / 10%);
}

.wb-auto-ai-result {
  background: var(--bg-subtle);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  margin-top: 12px;
  padding: 12px;
}

.wb-auto-ai-result code {
  color: var(--brand-cyan-dark);
  font-size: 12px;
}

.wb-auto-template-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.wb-auto-template-card {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  cursor: pointer;
  display: grid;
  gap: 8px;
  min-width: 0;
  padding: 14px;
  position: relative;
  transition: border-color var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease);
}

.wb-auto-template-card:hover,
.wb-auto-template-card--active {
  border-color: #6366f1;
  border-left: 3px solid #6366f1;
  box-shadow: var(--shadow-sm);
}

.wb-auto-template-card > span {
  font-size: 28px;
}

.wb-auto-template-card strong,
.wb-auto-template-card p,
.wb-auto-template-card small {
  min-width: 0;
  overflow-wrap: anywhere;
}

.wb-auto-template-card small {
  color: var(--text-muted);
  line-height: 1.45;
  word-break: break-word;
}

.wb-auto-use-template {
  background: #eef2ff;
  border: 1px solid #d9ddff;
  border-radius: var(--radius-sm);
  color: #4f46e5;
  justify-self: start;
  opacity: 0;
  padding: 4px 8px;
}

.wb-auto-template-card:hover .wb-auto-use-template,
.wb-auto-template-card--active .wb-auto-use-template {
  opacity: 1;
}

.wb-auto-patrol-panel {
  margin-top: 16px;
}

.wb-auto-patrol-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.wb-auto-patrol-list span {
  background: var(--bg-subtle);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-round);
  color: var(--text-secondary);
  font-size: 12px;
  padding: 5px 10px;
}

.wb-auto-drawer-mask {
  background: rgb(15 23 42 / 28%);
  bottom: 0;
  display: flex;
  justify-content: flex-end;
  left: 0;
  position: fixed;
  right: 0;
  top: 0;
  z-index: 20;
}

.wb-auto-drawer {
  background: var(--bg-white);
  box-shadow: -12px 0 28px rgb(15 23 42 / 16%);
  display: grid;
  gap: 14px;
  max-width: 560px;
  overflow-y: auto;
  padding: 18px;
  width: min(560px, 100vw);
}

.wb-auto-drawer header,
.wb-auto-drawer footer,
.wb-auto-drawer-grid {
  align-items: center;
  display: flex;
  gap: 10px;
  justify-content: space-between;
}

.wb-auto-drawer footer {
  border-top: 1px solid var(--border-light);
  padding-top: 12px;
}

.wb-auto-drawer label {
  display: grid;
  gap: 6px;
}

.wb-auto-drawer label span,
.wb-auto-camera-section strong,
.wb-auto-schedule-builder strong {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.wb-auto-drawer em {
  color: var(--brand-red);
  font-style: normal;
}

.wb-auto-drawer-icon {
  font-size: 22px;
  margin-right: 8px;
}

.wb-auto-field-grid,
.wb-auto-schedule-builder,
.wb-auto-camera-section {
  display: grid;
  gap: 10px;
}

.wb-auto-drawer-grid > label {
  flex: 1;
}

.wb-auto-choice-row,
.wb-auto-camera-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.wb-auto-check {
  align-items: center;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  display: flex !important;
  gap: 6px;
  padding: 6px 8px;
}

.wb-auto-check input {
  width: auto;
}

.wb-auto-camera-grid button {
  background: var(--bg-white);
  border: 1px solid var(--border-normal);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  display: grid;
  min-width: 130px;
  padding: 8px 10px;
  text-align: left;
}

.wb-auto-camera-grid small {
  color: var(--text-muted);
}

.wb-auto-camera-active {
  background: #f0f7ff !important;
  border-color: rgb(15 158 213 / 45%) !important;
  color: var(--brand-cyan-dark) !important;
  font-weight: 700;
}

@media (max-width: 1180px) {
  .wb-auto-stats,
  .wb-auto-workflow-layout,
  .wb-auto-template-grid {
    grid-template-columns: 1fr;
  }
}
</style>
