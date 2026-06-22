import { nextTick, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getChatHistory, sendCardAction, sendChatMessage, visualPatrolAssetUrl } from '../services/chitungApi'
import type { ChatAppliedSkill, ChatSkillReference } from '../types/domain'

export interface AiAssistantMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  status?: '执行中' | '完成' | '失败'
  cards?: Array<Record<string, unknown>>
  toolResults?: Array<Record<string, unknown>>
  appliedSkill?: ChatAppliedSkill | null
  skill?: ChatSkillReference | null
  intent?: string
  workflowName?: string
  workflowRunId?: string
  auditId?: string
}

export interface AiAssistantQuickAction {
  label: string
  prompt: string
}

interface ReportLink {
  label: string
  url: string
}

export interface ReportBlock {
  title: string
  text: string
  links: ReportLink[]
  reportId?: string
}

export const aiAssistantQuickActions: AiAssistantQuickAction[] = [
  { label: '隐患排查', prompt: '帮我分析最近的安全隐患' },
  { label: '视频巡检', prompt: '检查当前摄像头里的现场安全风险' },
  { label: '舆情简报', prompt: '生成今天香港工地安全舆情简报' },
  { label: '每日简报', prompt: '生成今日外部讯息简报' },
  { label: '制度查询', prompt: '查询临边作业安全管理要求' },
  { label: '文档表格', prompt: '帮我查找高处作业相关检查表模板' },
  { label: 'WhatsApp', prompt: '帮我看 WhatsApp 登录状态' },
]

export function useAiAssistant() {
  const route = useRoute()
  const messages = ref<AiAssistantMessage[]>([
    {
      id: 1,
      role: 'assistant',
      content: '你好，我是赤瞳 AI 助手。可以帮你处理隐患、巡检、填表、制度查询和工作流编排。',
    },
  ])
  const inputText = ref('')
  const isTyping = ref(false)
  const isHistoryLoaded = ref(false)
  const messagesEl = ref<HTMLElement | null>(null)
  const currentSessionId = ref('')
  const activeActionKeys = ref<string[]>([])
  const pendingContext = ref<Record<string, unknown>>({})
  let nextId = 2

  function scrollToBottom() {
    nextTick(() => {
      if (messagesEl.value) messagesEl.value.scrollTop = messagesEl.value.scrollHeight
    })
  }

  async function sendMessage(extraContext: Record<string, unknown> = {}) {
    const text = inputText.value.trim()
    if (!text || isTyping.value) return
    const metadata = { ...pendingContext.value, ...extraContext }
    messages.value.push({ id: nextId++, role: 'user', content: text })
    const assistantId = nextId++
    messages.value.push({
      id: assistantId,
      role: 'assistant',
      content: '执行中：正在识别意图并调用中台工具...',
      status: '执行中',
      cards: [],
      toolResults: [],
    })
    inputText.value = ''
    isTyping.value = true
    scrollToBottom()
    try {
      const response = await sendChatMessage({
        message: text,
        sessionId: currentSessionId.value || undefined,
        channel: 'local_chat',
        context: { ...buildPageContext(), ...metadata },
      })
      if (response.sessionId) currentSessionId.value = response.sessionId
      updateAssistantMessage(assistantId, {
        content: response.message,
        status: '完成',
        cards: (response.payload?.cards as Array<Record<string, unknown>> | undefined) ?? [],
        toolResults: (response.payload?.toolResults as Array<Record<string, unknown>> | undefined) ?? [],
        appliedSkill: response.payload?.appliedSkill ?? null,
        skill: response.payload?.skill ?? null,
        intent: String(response.payload?.intent?.intent || ''),
        workflowName: response.payload?.workflowName || '',
        workflowRunId: response.payload?.workflowRunId || response.workflowId || '',
        auditId: response.payload?.auditId || '',
      })
    } catch (error) {
      updateAssistantMessage(assistantId, {
        content: `请求失败：${error instanceof Error ? error.message : String(error)}`,
        status: '失败',
      })
    } finally {
      pendingContext.value = {}
      isTyping.value = false
      scrollToBottom()
    }
  }

  async function loadLatestHistory() {
    if (isHistoryLoaded.value) return
    isHistoryLoaded.value = true
    try {
      const history = await getChatHistory()
      if (!history.session || !history.messages.length) return
      currentSessionId.value = history.session.session_id
      messages.value = history.messages.map((item) => ({
        id: nextId++,
        role: item.role,
        content: item.content,
        status: item.role === 'assistant' ? ((item.status as AiAssistantMessage['status']) || '完成') : undefined,
        cards: item.cards ?? [],
        toolResults: item.tool_results ?? [],
        appliedSkill: item.metadata?.applied_skill ?? null,
        skill: item.metadata?.skill ?? null,
        intent: String(item.intent?.intent || ''),
        workflowName: String(item.metadata?.workflow_name || ''),
        workflowRunId: item.workflow_run_id || '',
        auditId: item.audit_id || '',
      }))
      scrollToBottom()
    } catch {
      // History loading should never block local chat input.
    }
  }

  function updateAssistantMessage(id: number, patch: Partial<AiAssistantMessage>) {
    const index = messages.value.findIndex((message) => message.id === id)
    if (index >= 0) {
      messages.value[index] = { ...messages.value[index], ...patch }
    }
  }

  function setDraft(prompt: string, context: Record<string, unknown> = {}) {
    inputText.value = prompt
    pendingContext.value = context
  }

  function handleQuickAction(prompt: string, context: Record<string, unknown> = {}) {
    setDraft(prompt, context)
    sendMessage(context)
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      sendMessage()
    }
  }

  function buildPageContext(): Record<string, unknown> {
    const segments = route.path.split('/').filter(Boolean)
    return {
      route: route.path,
      full_path: route.fullPath,
      route_name: String(route.name || ''),
      panel: segments[0] || '',
      module: segments[1] || segments[0] || '',
      timestamp: new Date().toISOString(),
    }
  }

  function actionRunning(key: string) {
    return activeActionKeys.value.includes(key)
  }

  async function handleCardAction(message: AiAssistantMessage, card: Record<string, unknown>, action: Record<string, unknown>) {
    const id = cardActionId(action)
    if (!id) return
    const key = actionKey(message, card, action)
    if (actionRunning(key)) return
    activeActionKeys.value = [...activeActionKeys.value, key]
    try {
      const result = await sendCardAction({
        actionId: id,
        cardData: card,
        channel: 'local_chat',
      })
      const ok = result.ok !== false
      messages.value.push({
        id: nextId++,
        role: 'assistant',
        content: String(result.summary || result.message || `${cardActionLabel(action)}已提交。`),
        status: ok ? '完成' : '失败',
        toolResults: [{ tool: 'card_action', action_id: id, ...result }],
        cards: Array.isArray(result.cards) ? (result.cards as Array<Record<string, unknown>>) : [],
      })
      scrollToBottom()
    } catch (error) {
      messages.value.push({
        id: nextId++,
        role: 'assistant',
        content: `卡片动作失败：${error instanceof Error ? error.message : String(error)}`,
        status: '失败',
      })
      scrollToBottom()
    } finally {
      activeActionKeys.value = activeActionKeys.value.filter((item) => item !== key)
    }
  }

  return {
    messages,
    inputText,
    isTyping,
    messagesEl,
    quickActions: aiAssistantQuickActions,
    loadLatestHistory,
    sendMessage,
    setDraft,
    handleQuickAction,
    handleKeydown,
    toolName,
    toolOk,
    toolSummary,
    cardTitle,
    cardSummary,
    cardActions,
    cardActionId,
    cardActionLabel,
    actionKey,
    actionRunning,
    handleCardAction,
    appliedSkillName,
    skillHighlights,
    skillNextActions,
    resultImages,
    resultReports,
  }
}

function toolName(result: Record<string, unknown>) {
  return String(result.tool || result.tool_name || result.source || 'tool')
}

function toolOk(result: Record<string, unknown>) {
  return result.ok !== false
}

function toolSummary(result: Record<string, unknown>) {
  const summary = result.summary
  if (typeof summary === 'string') return summary
  if (summary && typeof summary === 'object') {
    const value = summary as Record<string, unknown>
    if (typeof value.total_items === 'number') return `汇总 ${value.total_items} 条`
    if (typeof value.matched_item_count === 'number') return `匹配 ${value.matched_item_count} 条`
    if (typeof value.item_count === 'number') return `入库 ${value.item_count} 条`
    if (typeof value.detection_count === 'number') return `检测 ${value.detection_count} 个目标`
    if (typeof value.text === 'string') return value.text
  }
  if (typeof result.error === 'string') return result.error
  if (typeof result.message === 'string') return result.message
  return toolOk(result) ? '已完成' : '执行失败'
}

function cardTitle(card: Record<string, unknown>) {
  return String(card.title || card.card_type || '结果卡片')
}

function cardSummary(card: Record<string, unknown>) {
  return String(card.summary || '')
}

function cardActions(card: Record<string, unknown>) {
  return Array.isArray(card.actions) ? (card.actions as Array<Record<string, unknown>>) : []
}

function cardActionId(action: Record<string, unknown>) {
  return String(action.id || action.action_id || action.key || '')
}

function cardActionLabel(action: Record<string, unknown>) {
  return String(action.label || action.title || action.id || action.action_id || '执行')
}

function actionKey(message: AiAssistantMessage, card: Record<string, unknown>, action: Record<string, unknown>) {
  return `${message.id}:${cardTitle(card)}:${cardActionId(action)}`
}

function appliedSkillName(message: AiAssistantMessage) {
  return message.skill?.name || message.appliedSkill?.skill || ''
}

function skillHighlights(message: AiAssistantMessage) {
  return Array.isArray(message.appliedSkill?.highlights) ? message.appliedSkill.highlights : []
}

function skillNextActions(message: AiAssistantMessage) {
  return Array.isArray(message.appliedSkill?.next_actions) ? message.appliedSkill.next_actions : []
}

function resultImages(message: AiAssistantMessage) {
  const images: Array<{ title: string; url: string; caption?: string }> = []
  for (const card of message.cards ?? []) {
    collectImagesFromValue(card, images)
  }
  for (const result of message.toolResults ?? []) {
    collectImagesFromValue(result, images)
  }
  const seen = new Set<string>()
  return images.filter((image) => {
    if (seen.has(image.url)) return false
    seen.add(image.url)
    return true
  }).slice(0, 4)
}

function resultReports(message: AiAssistantMessage): ReportBlock[] {
  const reports: ReportBlock[] = []
  for (const card of message.cards ?? []) collectReportsFromValue(card, reports)
  for (const result of message.toolResults ?? []) collectReportsFromValue(result, reports)
  const seen = new Set<string>()
  return reports
    .filter((report) => {
      const key = `${report.title}:${report.text}:${report.reportId || ''}`
      if (seen.has(key)) return false
      seen.add(key)
      return Boolean(report.text || report.links.length || report.reportId)
    })
    .slice(0, 3)
}

function collectReportsFromValue(value: unknown, reports: ReportBlock[]) {
  if (!value || typeof value !== 'object') return
  const record = value as Record<string, unknown>
  const text = stringFromKeys(record, ['briefing_text', 'report_text', 'report_markdown', 'answer', 'llm_answer'])
  const links = linksFromValue(record.report_links ?? record.links ?? record.references)
  const reportId = stringFromKeys(record, ['briefing_report_id', 'report_id', 'id'])
  if (text || links.length || reportId) {
    reports.push({
      title: stringFromKeys(record, ['title', 'report_title', 'card_type']) || '报告结果',
      text,
      links,
      reportId,
    })
  }
  for (const key of ['report', 'data', 'briefing', 'payload', 'item']) collectReportsFromValue(record[key], reports)
}

function stringFromKeys(record: Record<string, unknown>, keys: string[]): string {
  for (const key of keys) {
    const value = record[key]
    if (typeof value === 'string' && value.trim()) return value
    if (typeof value === 'number') return String(value)
  }
  return ''
}

function linksFromValue(value: unknown): ReportLink[] {
  if (!Array.isArray(value)) return []
  return value
    .map((item, index) => {
      if (typeof item === 'string') return { label: `链接 ${index + 1}`, url: item }
      if (!item || typeof item !== 'object') return null
      const record = item as Record<string, unknown>
      const url = stringFromKeys(record, ['url', 'href', 'link'])
      if (!url) return null
      return {
        label: stringFromKeys(record, ['title', 'label', 'source', 'name']) || `链接 ${index + 1}`,
        url,
      }
    })
    .filter((item): item is ReportLink => Boolean(item))
    .slice(0, 5)
}

function collectImagesFromValue(value: unknown, images: Array<{ title: string; url: string; caption?: string }>) {
  if (!value || typeof value !== 'object') return
  const record = value as Record<string, unknown>
  for (const key of ['annotated_url', 'snapshot_url', 'image_url', 'thumbnail_url']) {
    const url = record[key]
    if (typeof url === 'string' && url) {
      const normalizedUrl = visualPatrolAssetUrl(url) || (url.startsWith('http') || url.startsWith('data:') ? url : '')
      if (normalizedUrl) {
        images.push({
          title: String(record.title || key),
          url: normalizedUrl,
          caption: String(record.camera_name || record.source_name || ''),
        })
      }
    }
  }
  for (const key of ['report', 'data', 'briefing']) collectImagesFromValue(record[key], images)
  for (const key of ['report_images', 'images', 'items', 'cameras']) {
    const list = record[key]
    if (!Array.isArray(list)) continue
    for (const item of list) collectImagesFromValue(item, images)
  }
}
