<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import type {
  ChatMessage,
  AiStatus,
  RiskItem,
  RevisionHistoryEntry,
  RevisionResult,
  RevisionProposal,
} from '@/types'
import RiskList from './RiskList.vue'
import ModelSettingsModal from './ModelSettingsModal.vue'
import KnowledgeBaseModal from './KnowledgeBaseModal.vue'
import PreferencePanel from './PreferencePanel.vue'
import { useVoice } from '@/composables/useVoice'
import { useDraggable } from '@/composables/useDraggable'
import { useAgentDraft } from '@/composables/useAgentDraft'
import { processRoute } from '@/api/ai'

const props = defineProps<{
  collapsed: boolean
  panelMode?: 'sidebar' | 'float'
  getDocumentText: () => string
  getLockedText: () => string
  onShowReview: (result: RevisionResult, command: string) => boolean
  onApplyRevision: (result: RevisionResult, command: string) => boolean
  onLocate: (text: string) => void
  onGetHistory: () => RevisionHistoryEntry[]
  onCaptureSelection?: () => void
  isReviewing?: boolean
  onAcceptReview?: () => boolean
  onRejectReview?: () => void
  onHistoryChange?: () => void
}>()

const emit = defineEmits<{
  toggleCollapse: []
  toggleMode: []
  statusChange: [thinking: boolean]
  toast: [message: string, type?: 'success' | 'info' | 'error']
}>()

const AGENT_STORAGE_KEY = 'docmate-agent-thread-v2'
const AGENT_HISTORY_KEY = 'docmate-agent-history-v2'
const WELCOME_CONTENT = `你好！我是闪闪文档助手，你的文稿修改搭档。

我的工作方式很简单：你把文字粘贴进来，告诉我要怎么改，我来出修改建议！`

const TASK_LABELS: Record<string, string> = {
  revise: '修改',
  polish: '润色',
  qa: '问答',
  risk: '风险扫描',
  oral: '口语转正式',
  table: '表格',
}

const slashCommands = [
  { id: 'formal', label: '/formal', desc: '改正式', prompt: '把选中文本改得更正式' },
  { id: 'concise', label: '/concise', desc: '精简', prompt: '精简选中文本，去掉冗余' },
  { id: 'polish', label: '/polish', desc: '润色', prompt: '润色选中文本' },
  { id: 'risk', label: '/risk', desc: '风险检查', prompt: '风险检查' },
  { id: 'table', label: '/table', desc: '转表格', prompt: '把选中文本整理成表格' },
  { id: 'oral', label: '/oral', desc: '口语转公文', prompt: '把下面内容转成正式公文表达：' },
  { id: 'summarize', label: '/summarize', desc: '总结要点', prompt: '总结这段文稿的核心要点' },
  { id: 'expand', label: '/expand', desc: '展开', prompt: '在不编造事实的前提下适度展开选中文本' },
]

const showMoreMenu = ref(false)
const showSlashMenu = ref(false)
const messages = ref<ChatMessage[]>(loadStoredMessages())
const agentHistory = ref<{ role: string; content: string }[]>(loadAgentHistory())
const appLogoUrl = new URL('./闪闪文档.png', window.location.href).href

const { agentDraft, clearAgentDraft } = useAgentDraft()

const aiStatus = ref<AiStatus>('ready')
const chatBodyRef = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLTextAreaElement | null>(null)
const showSettings = ref(false)
const showKnowledge = ref(false)
const showPreferences = ref(false)
const revisionHistory = ref<RevisionHistoryEntry[]>([])
const submitGeneration = ref(0)
const activeProposalId = ref<string | null>(null)
const regeneratingProposalId = ref<string | null>(null)
const regenerateThinking = ref('')
const lastError = ref<{ message: string; retryable: boolean; input: string } | null>(null)
const panelRef = ref<HTMLElement | null>(null)
const dragHandleRef = ref<HTMLElement | null>(null)
let scrollFrame = 0
const pendingRevisionMeta = ref<{ operation?: RevisionResult['operation']; insert_anchor?: string; insert_position?: RevisionResult['insert_position']; paragraph_index?: number; paragraph_text?: string }>({})

function inferProposalOperation(proposal: RevisionProposal): RevisionProposal['operation'] {
  if (proposal.operation) return proposal.operation
  const oldText = proposal.oldText?.trim() ?? ''
  const newText = proposal.options[0]?.text?.trim() ?? ''
  if (oldText && !newText) return 'delete'
  if (!oldText && newText) return 'insert'
  return 'replace'
}

useDraggable(panelRef, dragHandleRef, computed(() => props.panelMode === 'float'))

const statusText = computed(() => {
  if (aiStatus.value === 'listening') return '正在听...'
  if (isProcessing.value) return '识别中...'
  if (aiStatus.value === 'thinking') return '思考中...'
  return '就绪'
})

const statusDotClass = computed(() => {
  if (aiStatus.value === 'listening' || isProcessing.value) return 'listening'
  if (aiStatus.value === 'thinking') return 'thinking'
  return ''
})

const lockedPreview = computed(() => props.getLockedText())

const placeholder = computed(() =>
  lockedPreview.value
    ? '描述要如何修改选中的文字…'
    : '告诉闪闪要怎么改：如「第二段改正式」… Ctrl+K 打开面板',
)

function loadStoredMessages(): ChatMessage[] {
  try {
    const raw = sessionStorage.getItem(AGENT_STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as ChatMessage[]
      if (Array.isArray(parsed) && parsed.length > 0) {
        return parsed.map((msg) => (msg.id === 'welcome' ? { ...msg, content: WELCOME_CONTENT } : msg))
      }
    }
  } catch { /* ignore */ }
  return [
    {
      id: 'welcome',
      role: 'assistant',
      content: WELCOME_CONTENT,
    },
  ]
}

function loadAgentHistory(): { role: string; content: string }[] {
  try {
    const raw = sessionStorage.getItem(AGENT_HISTORY_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) return parsed
    }
  } catch { /* ignore */ }
  return []
}

function persistMessages() {
  try {
    sessionStorage.setItem(AGENT_STORAGE_KEY, JSON.stringify(messages.value))
  } catch { /* ignore */ }
}

function persistAgentHistory() {
  try {
    sessionStorage.setItem(AGENT_HISTORY_KEY, JSON.stringify(agentHistory.value))
  } catch { /* ignore */ }
}

function clearConversation() {
  if (aiStatus.value === 'thinking') return
  messages.value = loadStoredMessages().filter((m) => m.id === 'welcome')
  if (!messages.value.length) {
    messages.value = [{ id: 'welcome', role: 'assistant', content: WELCOME_CONTENT }]
  }
  agentHistory.value = []
  persistMessages()
  persistAgentHistory()
}

function pushAgentTurn(role: 'user' | 'assistant', content: string) {
  if (!content.trim()) return
  agentHistory.value.push({ role, content })
  if (agentHistory.value.length > 50) {
    agentHistory.value = agentHistory.value.slice(-50)
  }
  persistAgentHistory()
}

const { isRecording, isProcessing, toggle: toggleVoice } = useVoice({
  onStart: () => { aiStatus.value = 'listening' },
  onResult: (t) => { agentDraft.value = t },
  onEnd: (t) => {
    aiStatus.value = 'ready'
    if (t.trim()) handleSubmit(t.trim())
  },
  onStatus: (status) => {
    if (status === 'loading-model') {
      emit('toast', '首次使用正在加载语音模型，请稍候…', 'info')
    } else if (status === 'online-transcribing') {
      emit('toast', '正在使用在线语音识别…', 'info')
    } else if (status === 'online-fallback') {
      emit('toast', '在线识别失败，已切换本地识别', 'info')
    }
  },
  onError: (err) => {
    aiStatus.value = 'ready'
    if (err === 'not-allowed') emit('toast', '请允许麦克风权限', 'info')
    else if (err === 'not-supported') emit('toast', '语音识别不可用，请直接输入文字', 'info')
    else if (err !== 'aborted') emit('toast', '语音识别失败，请重试或直接输入', 'error')
  },
})

const taskBusy = computed(() => aiStatus.value === 'thinking' || isRecording.value || isProcessing.value || props.isReviewing)
const canStartVoice = computed(() => !props.isReviewing && aiStatus.value !== 'thinking' && !isProcessing.value)

function scrollToBottom() {
  if (scrollFrame) return
  scrollFrame = window.requestAnimationFrame(() => {
    scrollFrame = 0
    nextTick(() => {
      if (chatBodyRef.value) chatBodyRef.value.scrollTop = chatBodyRef.value.scrollHeight
    })
  })
}

function addMessage(partial: Omit<ChatMessage, 'id'> & { id?: string }) {
  const msg: ChatMessage = { id: partial.id || `msg-${Date.now()}`, ...partial }
  messages.value.push(msg)
  persistMessages()
  scrollToBottom()
  return msg.id
}

function updateMessage(id: string, patch: Partial<ChatMessage>, options: { persist?: boolean } = {}) {
  const idx = messages.value.findIndex((m) => m.id === id)
  if (idx !== -1) messages.value[idx] = { ...messages.value[idx], ...patch }
  if (options.persist !== false) persistMessages()
  scrollToBottom()
}

function findProposal(proposalId: string): RevisionProposal | undefined {
  for (const msg of messages.value) {
    if (msg.proposal?.id === proposalId) return msg.proposal
  }
  return undefined
}

function buildRevisionResult(proposal: RevisionProposal, optionId: string): RevisionResult | null {
  const option = proposal.options.find((o) => o.id === optionId)
  if (!option) return null
  const operation = inferProposalOperation(proposal)
  return {
    old_text: proposal.oldText,
    options: [option],
    reason: proposal.reason,
    operation,
    insert_anchor: proposal.insert_anchor ?? pendingRevisionMeta.value.insert_anchor,
    insert_position: proposal.insert_position ?? pendingRevisionMeta.value.insert_position,
    paragraph_index: proposal.paragraph_index ?? pendingRevisionMeta.value.paragraph_index,
    paragraph_text: proposal.paragraph_text ?? pendingRevisionMeta.value.paragraph_text,
  }
}

function opLabel(proposal: RevisionProposal): string {
  const op = inferProposalOperation(proposal)
  if (op === 'insert') return '新增'
  if (op === 'delete') return '删除'
  return '修改'
}

function showProposal(result: RevisionResult, command: string, task: string) {
  pendingRevisionMeta.value = {
    operation: result.operation,
    insert_anchor: result.insert_anchor,
    insert_position: result.insert_position,
    paragraph_index: result.paragraph_index,
    paragraph_text: result.paragraph_text,
  }

  const singleOption = result.options[0]
  const operation = result.operation || (result.old_text?.trim() && !singleOption?.text?.trim() ? 'delete' : 'replace')
  const proposal: RevisionProposal = {
    id: `prop-${Date.now()}`,
    oldText: result.old_text,
    options: singleOption ? [singleOption] : operation === 'delete' ? [{ id: 'opt1', label: '删除', text: '' }] : [],
    command,
    reason: result.reason,
    selectedOptionId: null,
    status: 'pending',
    operation,
    insert_anchor: result.insert_anchor,
    insert_position: result.insert_position,
    paragraph_index: result.paragraph_index,
    paragraph_text: result.paragraph_text,
  }

  if (result.match_confidence === 'failed') {
    emit('toast', 'AI 定位与原文略有偏差，请仔细确认后再采纳', 'info')
  }

  const first = singleOption || (operation === 'delete' ? { id: 'opt1', label: '删除', text: '' } : null)
  let previewOk = false
  if (first) {
    previewOk = props.onShowReview(
      {
        ...result,
        options: [first],
      },
      command,
    )
    if (!previewOk) {
      emit('toast', '未能自动定位，请点击「定位原文」或选择段落候选', 'info')
    }
  }

  const taskLabel = TASK_LABELS[task] || '修改'
  const locateHint = result.paragraph_index ? `第 ${result.paragraph_index} 段` : ''
  const opHint =
    result.operation === 'insert' ? '新增' : result.operation === 'delete' ? '删除' : taskLabel
  const summary = previewOk
    ? `${opHint}${locateHint ? ` · ${locateHint}` : ''} · 红删绿增已同步文档`
    : `${opHint} · 点击对话中的 Diff 同步到文档`

  activeProposalId.value = proposal.id

  addMessage({
    role: 'assistant',
    content: result.reason?.trim() || summary,
    proposal,
  })
  pushAgentTurn(
    'assistant',
    `${summary}\n${result.old_text?.trim() ? `原文：${result.old_text.slice(0, 120)}…` : '（新增/无原文锚点）'}`,
  )
}

async function handleSubmit(text?: string) {
  const input = (text ?? agentDraft.value).trim()
  if (!input) return
  if (taskBusy.value) {
    emit('toast', '当前已有任务进行中，请完成或终止后再开始新任务', 'info')
    return
  }
  clearAgentDraft()
  aiStatus.value = 'thinking'
  lastError.value = null
  const gen = ++submitGeneration.value

  props.onCaptureSelection?.()
  const doc = props.getDocumentText()
  const lockedText = props.getLockedText()

  addMessage({
    role: 'user',
    content: input,
    userContext: lockedText.trim() ? { selection: lockedText } : undefined,
  })

  const agentUserTurn = lockedText.trim()
    ? `[当前选区]\n${lockedText.slice(0, 500)}\n\n[用户指令]\n${input}`
    : input
  pushAgentTurn('user', agentUserTurn)

  const streamMsgId = addMessage({
    role: 'assistant',
    content: '',
    streaming: true,
    thinkingLog: [],
  })
  let streamed = ''

  const appendThinking = (chunk: string) => {
    streamed += chunk
    const msg = messages.value.find((m) => m.id === streamMsgId)
    const log = [...(msg?.thinkingLog || []), chunk]
    updateMessage(streamMsgId, { content: streamed.trim() || '处理中…', thinkingLog: log }, { persist: false })
  }

  try {
    const routeResult = await processRoute(doc, lockedText, input, agentHistory.value, appendThinking)

    if (gen !== submitGeneration.value) {
      updateMessage(streamMsgId, { content: '已终止', streaming: false })
      return
    }

    if (!routeResult?.task || routeResult.result === undefined) {
      throw new Error('AI 返回格式异常，请重试')
    }

    aiStatus.value = 'ready'
    const { task, result } = routeResult

    if (task === 'clarify') {
      const payload = result as { question: string; candidates?: { index: number; preview: string }[] }
      const question = payload.question || '请补充说明要修改的位置。'
      updateMessage(streamMsgId, {
        content: question,
        streaming: false,
        thinkingLog: streamed ? [streamed] : undefined,
        locateCandidates: payload.candidates,
        pendingCommand: input,
      })
      pushAgentTurn('assistant', question)
      return
    }

    if (task === 'qa') {
      const answer = (result as string) || streamed
      updateMessage(streamMsgId, {
        content: answer,
        streaming: false,
        thinkingLog: streamed && streamed !== answer ? [streamed] : undefined,
      })
      pushAgentTurn('assistant', answer)
      return
    }

    if (task === 'risk') {
      const risks = (result as { risks: RiskItem[] }).risks
      const summary = `扫描完成，发现 ${risks.length} 项需关注：`
      updateMessage(streamMsgId, {
        content: summary,
        streaming: false,
        risks,
        thinkingLog: streamed ? [streamed] : undefined,
      })
      pushAgentTurn('assistant', summary)
      return
    }

    if (task === 'revise' || task === 'polish' || task === 'oral') {
      const rev = result as RevisionResult
      const thinkingLog = streamed ? [streamed] : undefined
      updateMessage(streamMsgId, {
        content: rev.reason || '分析完成，已生成修改方案。',
        streaming: false,
        thinkingLog,
      })
      pushAgentTurn('assistant', rev.reason || '已生成修改方案')
      showProposal(rev, input, task)
      return
    }

    updateMessage(streamMsgId, { content: '任务已完成。', streaming: false })
  } catch (err) {
    if (gen !== submitGeneration.value) {
      updateMessage(streamMsgId, { content: '已终止', streaming: false })
      return
    }
    aiStatus.value = 'ready'
    const msg = err instanceof Error ? err.message : String(err)
    lastError.value = { message: msg, retryable: true, input }
    updateMessage(streamMsgId, {
      content: msg,
      streaming: false,
      thinkingLog: streamed ? [streamed] : undefined,
    })
    pushAgentTurn('assistant', msg)
  }
}

function findLatestPendingProposal(): RevisionProposal | undefined {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const p = messages.value[i].proposal
    if (p?.status === 'pending') return p
  }
  return undefined
}

function onRegenerateStart() {
  const id = activeProposalId.value ?? findLatestPendingProposal()?.id ?? null
  regeneratingProposalId.value = id
  regenerateThinking.value = ''
  aiStatus.value = 'thinking'
}

function onRegenerateEnd(payload: { ok: boolean; error?: string; revision?: RevisionResult }) {
  const targetId = regeneratingProposalId.value
  regeneratingProposalId.value = null
  regenerateThinking.value = ''
  aiStatus.value = 'ready'

  if (!payload.ok || !payload.revision) return

  const proposal = targetId ? findProposal(targetId) : findLatestPendingProposal()
  if (!proposal) return

  const rev = payload.revision
  const opt = rev.options?.[0]
  proposal.oldText = rev.old_text
  if (opt) proposal.options = [opt]
  proposal.operation = rev.operation || inferProposalOperation(proposal)
  proposal.status = 'pending'
  proposal.paragraph_index = rev.paragraph_index
  proposal.paragraph_text = rev.paragraph_text
  proposal.selectedOptionId = null
  activeProposalId.value = proposal.id
  persistMessages()
}

function onRegenerateThinking(log: string) {
  if (regeneratingProposalId.value) {
    regenerateThinking.value = log
  }
}

function onEditorAiState(state: string) {
  if (regeneratingProposalId.value && state === 'thinking') {
    aiStatus.value = 'thinking'
  } else if (regeneratingProposalId.value && state === 'reviewing') {
    aiStatus.value = 'ready'
  }
}

function handlePreviewProposal(proposalId: string) {
  activeProposalId.value = proposalId
  const proposal = findProposal(proposalId)
  if (!proposal) return
  const opt = proposal.options[0]
  if (!opt && inferProposalOperation(proposal) !== 'delete') return

  if (proposal.oldText?.trim()) props.onLocate(proposal.oldText)

  if (proposal.status !== 'pending') return

  const rev = buildRevisionResult(proposal, opt?.id || 'opt1')
  if (rev) {
    const ok = props.onShowReview(rev, proposal.command)
    if (!ok) emit('toast', '无法在文档中定位，请手动选中相关段落', 'info')
  }
}

function handlePickParagraph(index: number, pendingCommand: string) {
  if (!pendingCommand.trim()) return
  handleSubmit(`第${index}段：${pendingCommand}`)
}

function handleRiskAccept(id: string) {
  for (const msg of messages.value) {
    if (!msg.risks) continue
    const risk = msg.risks.find((r) => r.id === id)
    if (risk) {
      props.onLocate(risk.excerpt)
      const shown = props.onShowReview(
        {
          old_text: risk.excerpt,
          options: [{ id: '1', label: '建议', text: risk.suggestion }],
          reason: risk.reason,
        },
        '风险修复',
      )
      risk.resolved = shown
      if (shown) emit('toast', '请在编辑器内 Ctrl+Enter 采纳或 Esc 拒绝', 'success')
      else emit('toast', '定位失败，请手动修改', 'error')
      return
    }
  }
}

function handleRiskIgnore(id: string) {
  for (const msg of messages.value) {
    if (!msg.risks) continue
    const risk = msg.risks.find((r) => r.id === id)
    if (risk) risk.resolved = true
  }
  persistMessages()
}

function retryLast() {
  if (!lastError.value) return
  if (taskBusy.value) {
    emit('toast', '当前已有任务进行中，请稍后再重试', 'info')
    return
  }
  handleSubmit(lastError.value.input)
}

function refreshHistory() {
  revisionHistory.value = props.onGetHistory()
}

function handleHistoryPreview(item: RevisionHistoryEntry) {
  if (item.oldText?.trim()) props.onLocate(item.oldText)
}

function syncProposalFromHistory() {
  const latest = props.onGetHistory()[0]
  if (!latest) return
  for (const msg of messages.value) {
    const p = msg.proposal
    if (!p || p.status !== 'pending') continue
    if (p.command !== latest.command) continue
    p.status = latest.status
    if (latest.status === 'accepted') p.selectedOptionId = p.options[0]?.id ?? null
    persistMessages()
  }
}

function handleKeydown(e: KeyboardEvent) {
  if (agentDraft.value.trim() === '/') {
    showSlashMenu.value = true
  }
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSubmit()
  }
}

function applySlashCommand(prompt: string) {
  agentDraft.value = prompt
  showSlashMenu.value = false
  nextTick(() => focusInput())
}

function cancelAgentTask() {
  submitGeneration.value += 1
  aiStatus.value = 'ready'
  window.electronAPI?.cancelAI?.().catch(() => {})
  const streaming = [...messages.value].reverse().find((m) => m.streaming)
  if (streaming) {
    updateMessage(streaming.id, { content: '已终止', streaming: false })
  }
  emit('toast', '已终止当前任务', 'info')
}

function focusInput() {
  inputRef.value?.focus()
}

function submitExternalCommand(command: string) {
  if (taskBusy.value) {
    emit('toast', '当前已有任务进行中，请完成或终止后再开始新任务', 'info')
    return
  }
  handleSubmit(command)
}

defineExpose({
  focusInput,
  submitExternalCommand,
  clearConversation,
  refreshHistory,
  onRegenerateStart,
  onRegenerateEnd,
  onRegenerateThinking,
  onEditorAiState,
})

watch(
  () => props.isReviewing,
  (now, prev) => {
    if (prev && !now && !regeneratingProposalId.value) {
      activeProposalId.value = null
      nextTick(() => syncProposalFromHistory())
    }
  },
)

function scrollChatToBottom() {
  nextTick(() => {
    const el = chatBodyRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

function thinkingPreview(msg: ChatMessage): string {
  if (!msg.thinkingLog?.length) return ''
  return msg.thinkingLog.join('').trim()
}

watch(aiStatus, () => scrollChatToBottom())
watch(aiStatus, (status) => emit('statusChange', status === 'thinking'), { immediate: true })

watch(
  () => props.collapsed,
  (c) => {
    if (!c) {
      nextTick(() => {
        focusInput()
        refreshHistory()
        scrollChatToBottom()
      })
    }
  },
)
</script>

<template>
  <aside
    v-show="!collapsed"
    ref="panelRef"
    class="chat-panel agent-sidebar"
    :class="{ collapsed, 'agent-float': panelMode === 'float' }"
  >
    <div ref="dragHandleRef" class="chat-header drag-handle">
      <img :src="appLogoUrl" alt="DocMate" class="panel-logo" />
      <span class="chat-header-title">闪闪</span>
      <span class="status-dot" :class="statusDotClass" />
      <span class="chat-status">{{ statusText }}</span>
      <div class="header-actions">
        <div class="more-wrap">
          <button class="icon-btn" title="更多" @click="showMoreMenu = !showMoreMenu">
            <svg viewBox="0 0 16 16" fill="currentColor" width="14" height="14">
              <circle cx="3" cy="8" r="1.5"/><circle cx="8" cy="8" r="1.5"/><circle cx="13" cy="8" r="1.5"/>
            </svg>
          </button>
          <Transition name="dropdown">
            <div v-if="showMoreMenu" class="more-menu">
              <button class="more-item" type="button" @click="showPreferences = true; showMoreMenu = false">
                <svg viewBox="0 0 16 16" fill="currentColor" width="14" height="14">
                  <path d="M8 1.5a6.5 6.5 0 100 13 6.5 6.5 0 000-13zM8 3a5 5 0 110 10A5 5 0 018 3z"/>
                  <path d="M7.5 5h1v3.5H11v1H7.5V5z"/>
                </svg>
                偏好设置
              </button>
              <button class="more-item" type="button" @click="showKnowledge = true; showMoreMenu = false">
                <svg viewBox="0 0 16 16" fill="currentColor" width="14" height="14">
                  <path d="M2 2h5v12H2V2zm7 0h5v12H9V2z"/>
                </svg>
                知识库
              </button>
              <button class="more-item" type="button" @click="showSettings = true; showMoreMenu = false">
                <svg viewBox="0 0 16 16" fill="currentColor" width="14" height="14">
                  <path d="M8 5.5a2.5 2.5 0 110 5 2.5 2.5 0 010-5zM8 4a4 4 0 100 8 4 4 0 000-8z"/>
                  <path d="M8 0l1 2.5L8 5 7 2.5 8 0zM8 11l1 2.5L8 16l-1-2.5L8 11z"/>
                </svg>
                模型配置
              </button>
              <button class="more-item" type="button" @click="clearConversation(); showMoreMenu = false">
                <svg viewBox="0 0 16 16" fill="currentColor" width="14" height="14">
                  <path d="M3 3h10v1H3V3zm1 3h8v7H4V6zm2-4h4l1 1H5l1-1z"/>
                </svg>
                清空对话
              </button>
            </div>
          </Transition>
        </div>
        <button
          class="icon-btn layout-toggle"
          :title="panelMode === 'sidebar' ? '切换为浮窗' : '切换为侧栏'"
          @click="emit('toggleMode')"
        >
          <svg v-if="panelMode === 'sidebar'" viewBox="0 0 16 16" fill="currentColor" width="14" height="14">
            <path d="M3 3h4v1H3v8h4v1H2V3h1zm10 0H9v1h4v8H9v1h5V3h-1z"/>
            <path d="M7 7.5h2v1H7z" opacity="0.4"/>
          </svg>
          <svg v-else viewBox="0 0 16 16" fill="currentColor" width="14" height="14">
            <path d="M2 2h12v12H2V2zm1 1v10h10V3H3z"/>
            <path d="M3 7.5h10v1H3z" opacity="0.4"/>
          </svg>
        </button>
        <button class="icon-btn" title="折叠" @click="emit('toggleCollapse')">
          <svg viewBox="0 0 16 16" fill="currentColor" width="14" height="14">
            <path d="M7 4l4 4-4 4V4z"/>
          </svg>
        </button>
      </div>
    </div>

    <div ref="chatBodyRef" class="chat-body">
      <div
        v-for="msg in messages"
        :key="msg.id"
        class="chat-row"
        :class="[msg.role, { streaming: msg.streaming }]"
      >
        <div class="chat-avatar" :class="msg.role">
          <img v-if="msg.role === 'assistant'" :src="appLogoUrl" alt="" class="avatar-img" />
          <span v-else class="avatar-you">You</span>
        </div>

        <div class="chat-col">
          <div v-if="msg.role === 'user' && msg.userContext?.selection" class="context-chip">
            <span class="context-label">选区</span>
            {{ msg.userContext.selection }}
          </div>

          <div v-if="msg.streaming" class="thinking-live">
            <span class="thinking-dots"><span /><span /><span /></span>
            <span class="thinking-label">Thinking</span>
          </div>

          <details
            v-if="msg.thinkingLog?.length && (!msg.streaming || thinkingPreview(msg).length > 40)"
            class="thinking-block"
            :open="msg.streaming"
          >
            <summary>{{ msg.streaming ? '推理过程' : '查看思考过程' }}</summary>
            <pre class="thinking-text">{{ thinkingPreview(msg) }}</pre>
          </details>

          <div
            v-if="!msg.proposal && (msg.content || msg.streaming)"
            class="msg-bubble"
            :class="msg.role"
          >
            <div class="msg-content" :class="{ streaming: msg.streaming }">
              {{ msg.content }}<span v-if="msg.streaming && !msg.content" class="thinking-placeholder">正在分析…</span>
            </div>
          </div>

          <div v-else-if="msg.proposal && msg.content?.trim() && msg.content !== msg.proposal.reason" class="msg-bubble assistant">
            <div class="msg-content">{{ msg.content }}</div>
          </div>

          <button v-if="lastError?.retryable && msg === messages[messages.length - 1]" class="retry-btn" @click="retryLast">
            重试
          </button>

          <div v-if="msg.locateCandidates?.length" class="candidate-list">
            <p class="candidate-title">请选择要修改的段落：</p>
            <button
              v-for="c in msg.locateCandidates"
              :key="c.index"
              type="button"
              class="candidate-btn"
              @click="handlePickParagraph(c.index, msg.pendingCommand || '')"
            >
              第 {{ c.index }} 段 · {{ c.preview }}
            </button>
          </div>

          <button
            v-if="msg.proposal && regeneratingProposalId === msg.proposal.id"
            type="button"
            class="regenerate-thinking-card"
            disabled
          >
            <div class="thinking-live">
              <span class="thinking-dots"><span /><span /><span /></span>
              <span class="thinking-label">Regenerating…</span>
            </div>
            <pre v-if="regenerateThinking.trim()" class="thinking-text">{{ regenerateThinking.trim() }}</pre>
            <p v-else class="regenerate-hint">正在重新生成修改方案…</p>
          </button>

          <button
            v-else-if="msg.proposal"
            type="button"
            class="proposal-preview"
            :class="[msg.proposal.status, { synced: activeProposalId === msg.proposal.id && isReviewing }]"
            @click="handlePreviewProposal(msg.proposal.id)"
          >
            <div class="diff-head">
              <span class="op-tag">{{ opLabel(msg.proposal) }}</span>
              <span v-if="msg.proposal.status === 'pending' && activeProposalId === msg.proposal.id && isReviewing" class="sync-tag">
                ↗ 文档已同步
              </span>
              <span v-else-if="msg.proposal.status === 'pending'" class="sync-hint">点击同步 · Ctrl+↵ 采纳 · Esc 拒绝</span>
              <span v-else class="done-tag">{{ msg.proposal.status === 'accepted' ? '✓ 已应用' : '✗ 已拒绝' }}</span>
            </div>
            <div v-if="msg.proposal.oldText" class="diff-old">{{ msg.proposal.oldText }}</div>
            <div v-if="inferProposalOperation(msg.proposal) !== 'delete'" class="diff-new">
              {{ msg.proposal.options[0]?.text || '（空）' }}
            </div>
            <div v-else class="diff-new delete-hint">（删除以上内容）</div>
          </button>

          <RiskList
            v-if="msg.risks"
            :risks="msg.risks"
            @locate="(t) => props.onLocate(t)"
            @accept="handleRiskAccept"
            @ignore="handleRiskIgnore"
          />
        </div>
      </div>
    </div>

    <details class="history-fold" @toggle="(e) => (e.target as HTMLDetailsElement).open && refreshHistory()">
      <summary>
        修改历史
        <span v-if="revisionHistory.length" class="history-count">{{ revisionHistory.length }}</span>
      </summary>
      <div class="history-list">
        <div v-if="revisionHistory.length === 0" class="history-empty">暂无记录</div>
        <button
          v-for="item in revisionHistory"
          :key="item.id"
          type="button"
          class="history-item"
          @click="handleHistoryPreview(item)"
        >
          <div class="history-meta">
            <span class="history-time">{{ item.time }}</span>
            <span class="history-cmd">「{{ item.command }}」</span>
            <span class="history-status" :class="item.status">
              {{ item.status === 'accepted' ? '已应用' : '已拒绝' }}
            </span>
          </div>
          <div class="diff-box compact">
            <div v-if="item.oldText?.trim()" class="diff-old">{{ item.oldText }}</div>
            <div v-if="item.newText?.trim()" class="diff-new">{{ item.newText }}</div>
          </div>
        </button>
      </div>
    </details>

    <div class="composer">
      <div v-if="lockedPreview" class="pinned-banner">
        <span class="pinned-text">{{ lockedPreview.slice(0, 50) }}{{ lockedPreview.length > 50 ? '…' : '' }}</span>
      </div>
      <div class="composer-box">
        <div v-if="showSlashMenu && !taskBusy" class="agent-slash-menu">
          <button
            v-for="cmd in slashCommands"
            :key="cmd.id"
            type="button"
            class="agent-slash-item"
            @click="applySlashCommand(cmd.prompt)"
          >
            <span class="agent-slash-label">{{ cmd.label }}</span>
            <span class="agent-slash-desc">{{ cmd.desc }}</span>
          </button>
        </div>
        <textarea
          ref="inputRef"
          v-model="agentDraft"
          class="composer-input"
          :placeholder="placeholder"
          :disabled="taskBusy"
          rows="2"
          @keydown="handleKeydown"
          @input="showSlashMenu = agentDraft.trim() === '/'"
        />
        <div class="composer-footer">
          <span class="composer-hint">{{ taskBusy ? '当前任务完成后可继续' : 'Enter 发送' }}</span>
          <div class="composer-actions">
            <button
              v-if="aiStatus === 'thinking'"
              class="composer-btn stop"
              type="button"
              title="终止任务"
              @click="cancelAgentTask"
            >
              <span class="stop-square" />
            </button>
            <button
              v-else
              class="composer-btn"
              :class="{ recording: isRecording || isProcessing }"
              title="语音输入"
              :disabled="!canStartVoice && !isRecording"
              @click="toggleVoice"
            >
              <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor"><path d="M8 1.5a2.5 2.5 0 0 1 2.5 2.5V8a2.5 2.5 0 0 1-5 0V4A2.5 2.5 0 0 1 8 1.5z"/></svg>
            </button>
            <button
              class="composer-btn send"
              :disabled="taskBusy || !agentDraft.trim()"
              @click="handleSubmit()"
            >
              <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor"><path d="M2 2l12 6-12 6V9l8-1-8-1V2z"/></svg>
            </button>
          </div>
        </div>
      </div>
    </div>

    <ModelSettingsModal v-if="showSettings" @close="showSettings = false" @saved="showSettings = false" @toast="(m,t) => emit('toast', m, t)" />
    <KnowledgeBaseModal v-if="showKnowledge" @close="showKnowledge = false" @saved="showKnowledge = false" @toast="(m,t) => emit('toast', m, t)" />
    <PreferencePanel v-if="showPreferences" @close="showPreferences = false" @saved="showPreferences = false" @toast="(m,t) => emit('toast', m, t)" />
  </aside>
</template>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.drag-handle {
  cursor: move;
  user-select: none;
  position: relative;
}

.agent-sidebar:not(.agent-float) .drag-handle {
  cursor: default;
}

.drag-handle .icon-btn {
  cursor: pointer;
}

.panel-logo {
  width: 22px;
  height: 22px;
  border-radius: 4px;
}

.chat-header .icon-btn { margin-left: 2px; }

.agent-slash-menu {
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: 78px;
  z-index: 5;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  padding: 8px;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  background: var(--bg-panel);
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.35);
}

.agent-slash-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 7px 8px;
  border-radius: 8px;
  text-align: left;
}

.agent-slash-item:hover {
  background: var(--bg-hover);
}

.agent-slash-label {
  color: var(--accent);
  font-size: 12px;
}

.agent-slash-desc {
  color: var(--text-muted);
  font-size: 11px;
}

.header-actions {
  margin-left: auto;
  display: flex;
  gap: 2px;
}

.chat-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  width: 100%;
}

.chat-row.user {
  flex-direction: row-reverse;
}

.chat-row.user .chat-col {
  align-items: flex-end;
}

.chat-row.assistant .chat-col {
  align-items: flex-start;
}

.chat-avatar {
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 2px;
}

.chat-avatar.assistant {
  background: var(--bg-hover);
  border: 1px solid var(--border-light);
}

.chat-avatar.user {
  background: var(--accent-muted, rgba(0, 122, 204, 0.2));
  border: 1px solid rgba(0, 122, 204, 0.35);
}

.avatar-img {
  width: 18px;
  height: 18px;
  border-radius: 4px;
}

.avatar-you {
  font-size: 9px;
  font-weight: 700;
  color: var(--accent);
}

.chat-col {
  display: flex;
  flex-direction: column;
  min-width: 0;
  max-width: calc(100% - 36px);
  flex: 1;
}

.msg-bubble {
  border-radius: 12px;
  padding: 10px 12px;
  max-width: 100%;
  word-break: break-word;
}

.msg-bubble.user {
  background: rgba(0, 122, 204, 0.18);
  border: 1px solid rgba(0, 122, 204, 0.28);
  border-bottom-right-radius: 4px;
}

.msg-bubble.assistant {
  background: var(--bg-input, var(--bg-hover));
  border: 1px solid var(--border-light);
  border-bottom-left-radius: 4px;
}

.msg-content {
  font-size: 13px;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--text-primary);
}

.thinking-live {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  color: var(--text-muted);
  font-size: 12px;
}

.thinking-label {
  font-weight: 500;
  letter-spacing: 0.02em;
}

.thinking-dots {
  display: inline-flex;
  gap: 3px;
  align-items: center;
}

.thinking-dots span {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--accent);
  animation: thinking-pulse 1.2s ease-in-out infinite;
}

.thinking-dots span:nth-child(2) { animation-delay: 0.15s; }
.thinking-dots span:nth-child(3) { animation-delay: 0.3s; }

@keyframes thinking-pulse {
  0%, 80%, 100% { opacity: 0.25; transform: scale(0.85); }
  40% { opacity: 1; transform: scale(1); }
}

.thinking-placeholder {
  color: var(--text-muted);
  font-style: italic;
}

.msg-note {
  font-size: 11px;
  color: var(--text-muted);
  margin: 0 0 4px;
}

.history-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  margin-bottom: 6px;
}

.diff-box.compact {
  border: 1px solid var(--border-light);
  border-radius: 6px;
  overflow: hidden;
  text-align: left;
}

.diff-box.compact .diff-old {
  padding: 6px 8px;
  background: rgba(241, 76, 76, 0.1);
  font-size: 11px;
  color: var(--red);
  text-decoration: line-through;
  line-height: 1.45;
}

.diff-box.compact .diff-new {
  padding: 6px 8px;
  background: rgba(78, 201, 176, 0.1);
  font-size: 11px;
  color: var(--green);
  line-height: 1.45;
}

.proposal-preview {
  width: 100%;
  text-align: left;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  overflow: hidden;
  background: var(--bg-base);
  cursor: pointer;
  margin-top: 6px;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.proposal-preview:hover {
  border-color: var(--accent);
}

.proposal-preview.synced {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px rgba(0, 122, 204, 0.25);
}

.proposal-preview .diff-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  background: var(--bg-hover);
  border-bottom: 1px solid var(--border);
}

.proposal-preview .op-tag {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-secondary);
}

.proposal-preview .sync-tag {
  font-size: 10px;
  color: var(--accent);
}

.proposal-preview .sync-hint,
.proposal-preview .done-tag {
  font-size: 10px;
  color: var(--text-muted);
  margin-left: auto;
}

.proposal-preview .diff-old {
  padding: 8px 10px;
  background: rgba(241, 76, 76, 0.12);
  font-size: 12px;
  line-height: 1.55;
  color: var(--red);
  text-decoration: line-through;
  word-break: break-word;
  max-height: none;
  overflow: visible;
}

.proposal-preview .diff-new {
  padding: 8px 10px;
  background: rgba(78, 201, 176, 0.12);
  font-size: 12px;
  line-height: 1.55;
  color: var(--green);
  word-break: break-word;
  max-height: none;
  overflow: visible;
}

.proposal-preview .diff-new.delete-hint {
  color: var(--text-muted);
  font-style: italic;
}

.regenerate-thinking-card {
  width: 100%;
  text-align: left;
  border: 1px dashed var(--accent);
  border-radius: 8px;
  padding: 10px 12px;
  margin-top: 6px;
  background: rgba(0, 122, 204, 0.06);
  cursor: default;
}

.regenerate-hint {
  margin: 8px 0 0;
  font-size: 11px;
  color: var(--text-muted);
}

.more-wrap {
  position: relative;
}

.more-menu {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 4px;
  background: var(--bg-panel);
  border: 1px solid var(--border-light);
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
  padding: 4px;
  min-width: 140px;
  z-index: 60;
}

.more-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 7px 10px;
  border-radius: 4px;
  font-size: 12px;
  color: var(--text-primary);
  text-align: left;
}

.more-item:hover {
  background: var(--bg-hover);
}

.dropdown-enter-active { transition: opacity 0.15s, transform 0.15s; }
.dropdown-leave-active { transition: opacity 0.1s, transform 0.1s; }
.dropdown-enter-from { opacity: 0; transform: translateY(-4px); }
.dropdown-leave-to { opacity: 0; transform: translateY(-4px); }

.history-fold {
  border-top: 1px solid var(--border);
  padding: 6px 12px;
  flex-shrink: 0;
}

.history-fold summary {
  font-size: 11px;
  color: var(--text-muted);
  cursor: pointer;
  user-select: none;
  list-style: none;
}

.history-fold summary::-webkit-details-marker {
  display: none;
}

.history-count {
  font-size: 10px;
  background: var(--bg-hover);
  padding: 0 4px;
  border-radius: 4px;
  margin-left: 4px;
}

.history-list {
  max-height: 180px;
  overflow-y: auto;
  margin-top: 6px;
}

.chat-body {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 12px 10px;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.context-chip {
  font-size: 11px;
  padding: 6px 10px;
  margin-bottom: 6px;
  border-radius: 8px;
  background: rgba(0, 122, 204, 0.1);
  color: var(--text-secondary);
  line-height: 1.5;
  border: 1px solid rgba(0, 122, 204, 0.2);
  white-space: pre-wrap;
  word-break: break-word;
  max-width: 100%;
}

.context-label {
  font-weight: 600;
  color: var(--accent);
  margin-right: 6px;
}

.thinking-block {
  margin-bottom: 8px;
  font-size: 11px;
}

.thinking-block summary {
  cursor: pointer;
  color: var(--text-muted);
  user-select: none;
}

.thinking-text {
  margin-top: 6px;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--bg-input);
  color: var(--text-muted);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: none;
  overflow: visible;
  font-family: ui-monospace, 'Cascadia Code', monospace;
  font-size: 11px;
  line-height: 1.5;
}

.candidate-title {
  font-size: 11px;
  color: var(--text-muted);
  margin: 0 0 6px;
}

.candidate-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 10px;
}

.candidate-btn {
  text-align: left;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--border-light);
  background: var(--bg-input);
  font-size: 11px;
  line-height: 1.4;
  color: var(--text-primary);
}

.candidate-btn:hover {
  border-color: var(--accent);
  background: var(--accent-muted);
}

.review-hint {
  margin-bottom: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 11px;
  color: var(--green);
  background: rgba(78, 201, 176, 0.12);
  border: 1px solid rgba(78, 201, 176, 0.35);
}

.review-hint kbd {
  font-size: 10px;
  padding: 1px 4px;
  border-radius: 3px;
  background: var(--bg-hover);
}


.history-empty {
  text-align: center;
  color: var(--text-muted);
  padding: 24px;
  font-size: 13px;
}

.history-item {
  width: 100%;
  text-align: left;
  padding: 10px;
  border-radius: 8px;
  margin-bottom: 4px;
  border: 1px solid var(--border);
  background: var(--bg-input);
}

.history-item:hover {
  border-color: var(--accent);
}

.history-time {
  font-size: 11px;
  color: var(--text-muted);
  display: block;
}

.history-cmd {
  font-size: 12px;
  color: var(--text-primary);
  display: block;
  margin-top: 4px;
}

.history-preview {
  font-size: 11px;
  color: var(--text-secondary);
  display: block;
  margin-top: 4px;
  line-height: 1.4;
}

.history-status {
  font-size: 11px;
  margin-top: 4px;
  display: inline-block;
}

.history-status.accepted { color: var(--green); }
.history-status.rejected { color: var(--text-muted); }

.retry-btn {
  margin-top: 8px;
  padding: 4px 12px;
  font-size: 12px;
  border-radius: 6px;
  background: var(--accent);
  color: white;
}

.msg-content.streaming { min-height: 1.2em; }

.composer {
  padding: 10px 12px 12px;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}

.pinned-banner {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  padding: 6px 8px;
  border-radius: 8px;
  background: var(--accent-muted);
  font-size: 11px;
}

.pinned-label {
  color: var(--accent);
  font-weight: 600;
  flex-shrink: 0;
}

.pinned-text {
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.composer-box {
  background: var(--bg-input);
  border: 1px solid var(--border-light);
  border-radius: 12px;
  overflow: hidden;
}

.composer-box:focus-within {
  border-color: var(--accent);
}

.composer-input {
  width: 100%;
  padding: 10px 12px 4px;
  background: transparent;
  border: none;
  outline: none;
  resize: none;
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-primary);
}

.composer-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 8px 8px;
}

.composer-hint {
  font-size: 10px;
  color: var(--text-muted);
}

.composer-actions {
  display: flex;
  gap: 4px;
}

.composer-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: var(--text-secondary);
}

.composer-btn.recording { color: var(--red); }
.composer-btn.stop {
  background: rgba(244, 71, 71, 0.15);
  color: #f44747;
}
.stop-square {
  width: 10px;
  height: 10px;
  background: #f44747;
  border-radius: 2px;
  display: block;
}
.composer-btn.send { background: var(--accent); color: white; }
.composer-btn.send:disabled { opacity: 0.35; cursor: not-allowed; }
</style>
