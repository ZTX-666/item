<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { askRag, getSkills, sendChatMessage } from '../../services/chitungApi'
import { useDocmateSession } from '../../composables/useDocmateSession'
import { useJobPolling } from '../../composables/useJobPolling'
import DocmateDiffReview from '../documents/DocmateDiffReview.vue'
import ChatRichBlocks from '../chat/ChatRichBlocks.vue'
import assistantAvatar from '../../assets/logos/assistant-avatar.png'
import type { AgentTraceItem, SkillInfo } from '../../types/domain'

defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  toggle: []
}>()

// ── resizable width (drag the left edge) ──
const panelWidth = ref(380)
let resizing = false
let startX = 0
let startWidth = 0

function startResize(event: MouseEvent) {
  resizing = true
  startX = event.clientX
  startWidth = panelWidth.value
  window.addEventListener('mousemove', onResize)
  window.addEventListener('mouseup', stopResize)
  document.body.style.userSelect = 'none'
  document.body.style.cursor = 'col-resize'
}

function onResize(event: MouseEvent) {
  if (!resizing) return
  const delta = startX - event.clientX // drag left → wider
  panelWidth.value = Math.min(760, Math.max(300, startWidth + delta))
}

function stopResize() {
  resizing = false
  window.removeEventListener('mousemove', onResize)
  window.removeEventListener('mouseup', stopResize)
  document.body.style.userSelect = ''
  document.body.style.cursor = ''
}

const skillMenuOpen = ref(false)
const skillMenuHeight = ref(148)
let resizingSkillMenu = false
let skillStartY = 0
let skillStartHeight = 0

function startSkillMenuResize(event: MouseEvent) {
  resizingSkillMenu = true
  skillStartY = event.clientY
  skillStartHeight = skillMenuHeight.value
  window.addEventListener('mousemove', onSkillMenuResize)
  window.addEventListener('mouseup', stopSkillMenuResize)
  document.body.style.userSelect = 'none'
  document.body.style.cursor = 'row-resize'
}

function onSkillMenuResize(event: MouseEvent) {
  if (!resizingSkillMenu) return
  const delta = skillStartY - event.clientY
  skillMenuHeight.value = Math.min(260, Math.max(92, skillStartHeight + delta))
}

function stopSkillMenuResize() {
  resizingSkillMenu = false
  window.removeEventListener('mousemove', onSkillMenuResize)
  window.removeEventListener('mouseup', stopSkillMenuResize)
  document.body.style.userSelect = ''
  document.body.style.cursor = ''
}

onBeforeUnmount(() => {
  stopResize()
  stopSkillMenuResize()
})

interface Message {
  id: number
  role: 'user' | 'assistant'
  content: string
  trace?: AgentTraceItem[]
  cards?: Array<Record<string, unknown>>
  toolResults?: Array<Record<string, unknown>>
  richBlocks?: Array<Record<string, unknown>>
}

const WELCOME_MESSAGE =
  '你好，我是赤瞳守护者内置的闪闪助手，专为安全生产场景设计。我可以帮你：\n🔍 隐患排查与处置 — 发现、记录、跟踪闭环\n📋 安全巡检 — 执行巡检任务、生成巡检报告\n📝 表单智能填报 — 自动识别字段，快速完成安全记录\n📖 制度法规查询 — 精准检索安全规章与合规要求\n⚙️ 工作流编排 — 串联多部门安全流程，自动化执行\n\n安全的事，交给我们来守护。'

function createWelcomeMessage(): Message {
  return { id: 1, role: 'assistant', content: WELCOME_MESSAGE }
}

const messages = ref<Message[]>([createWelcomeMessage()])
const inputText = ref('')
const isTyping = ref(false)
const messagesEl = ref<HTMLElement | null>(null)
const backendSkills = ref<SkillInfo[]>([])
const skillsLoading = ref(false)
const skillsError = ref('')
const selectedSkillLabel = ref('')
const selectedSkillName = ref<string | null>(null)
const currentSessionId = ref<string | null>(null)
let nextId = 2

// ── DocMate 文档改稿能力（与文档工作台共享同一会话） ──
const docmate = useDocmateSession()
const { poll: pollBackgroundJob } = useJobPolling()
const mode = ref<'chat' | 'edit' | 'rag'>('chat')

// 文档一旦加载，自动切到改稿模式
watch(
  () => docmate.isLoaded.value,
  (loaded) => {
    if (loaded) mode.value = 'edit'
  },
)

const placeholder = computed(() =>
  mode.value === 'edit'
    ? '用自然语言改稿：如「把第二段改正式」「删掉最后一段」'
    : mode.value === 'rag'
      ? '询问内置安全管理规定，例如：机械作业半径怎么检查？'
    : '输入消息，Enter 发送，Shift+Enter 换行',
)

const showDiffPanel = computed(
  () => docmate.hasWork.value || docmate.state.step === 'committing' || docmate.isDone.value,
)

interface SkillAction {
  label: string
  prompt: string
  skill?: string
  summary?: string
  enabled?: boolean
}

const fallbackActions: SkillAction[] = [
  { label: '制度知识问答', prompt: '🔨 使用技能：制度知识问答\n', skill: 'rag', summary: '询问内置安全管理规定知识库', enabled: true },
]

const skillActions = computed<SkillAction[]>(() => {
  const backend = backendSkills.value.map((skill) => ({
    label: readableSkillName(skill),
    prompt: `🔨 使用技能：${readableSkillName(skill)}\n`,
    skill: skill.name,
    summary: skill.description || skill.summary || skill.category || skill.name,
    enabled: skill.enabled !== false,
  }))
  return [...fallbackActions, ...backend]
})

onMounted(loadBackendSkills)

async function loadBackendSkills() {
  skillsLoading.value = true
  skillsError.value = ''
  try {
    backendSkills.value = await getSkills()
  } catch (error) {
    skillsError.value = error instanceof Error ? error.message : String(error)
    backendSkills.value = []
  } finally {
    skillsLoading.value = false
  }
}

function readableSkillName(skill: SkillInfo): string {
  if (skill.display_name?.trim()) return skill.display_name.trim()
  const config = skill.config as Record<string, unknown> | undefined
  if (typeof config?.display_name === 'string' && config.display_name.trim()) {
    return config.display_name.trim()
  }
  if (skill.name === 'external-info-monitor') return '外部讯息监听'
  return skill.name
    .replace(/^skill[_-]?/i, '')
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesEl.value) messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  })
}

function pushAssistant(content: string) {
  messages.value.push({ id: nextId++, role: 'assistant', content })
  scrollToBottom()
}

function pushAssistantWithTrace(
  content: string,
  trace?: AgentTraceItem[],
  cards: Array<Record<string, unknown>> = [],
  toolResults: Array<Record<string, unknown>> = [],
  richBlocks: Array<Record<string, unknown>> = [],
) {
  messages.value.push({ id: nextId++, role: 'assistant', content, trace: trace ?? [], cards, toolResults, richBlocks })
  scrollToBottom()
}

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || isTyping.value) return

  // 改稿模式：把输入作为修改指令交给 DocMate 流程
  if (mode.value === 'edit' && docmate.isLoaded.value) {
    messages.value.push({ id: nextId++, role: 'user', content: text })
    inputText.value = ''
    isTyping.value = true
    scrollToBottom()
    const result = await docmate.generateChanges(text)
    isTyping.value = false
    if (result.ok && result.count > 0) {
      pushAssistant(`已生成 ${result.count} 项修改建议，请在下方审阅、勾选后采纳写入文档。`)
    } else if (result.ok) {
      pushAssistant('未能从这条指令解析出可执行的修改，请换一种更明确的说法，例如「把X改为Y」「删掉第三段」。')
    } else {
      pushAssistant(`生成修改方案失败：${result.error}`)
    }
    return
  }

  // 内置 RAG 知识库问答：固定查询安全管理规定集合。
  if (mode.value === 'rag') {
    messages.value.push({ id: nextId++, role: 'user', content: text })
    inputText.value = ''
    isTyping.value = true
    scrollToBottom()
    try {
      const answer = await askRag({ query: text, topK: 5, collection: 'safety' })
      const citations = (answer.citations ?? [])
        .map((item) => `${item.source_file_name || '知识库'}#${item.chunk_index}`)
        .slice(0, 3)
        .join('、')
      pushAssistant(citations ? `${answer.answer}\n\n引用：${citations}` : answer.answer)
    } catch (error) {
      pushAssistant(`知识库问答失败：${error instanceof Error ? error.message : String(error)}`)
    } finally {
      isTyping.value = false
      scrollToBottom()
    }
    return
  }

  // 普通中台问答
  messages.value.push({ id: nextId++, role: 'user', content: text })
  inputText.value = ''
  isTyping.value = true
  scrollToBottom()
  try {
    const context: Record<string, unknown> = {}
    if (selectedSkillName.value) {
      context.skill = selectedSkillName.value
    }
    const response = await sendChatMessage({
      message: text,
      channel: 'local_chat',
      context,
      sessionId: currentSessionId.value || undefined,
    })
    if (response.sessionId) currentSessionId.value = response.sessionId
    selectedSkillName.value = null
    pushAssistantWithTrace(
      response.message,
      response.payload?.agentTrace,
      (response.payload?.cards as Array<Record<string, unknown>> | undefined) ?? [],
      (response.payload?.toolResults as Array<Record<string, unknown>> | undefined) ?? [],
      (response.payload?.richBlocks as Array<Record<string, unknown>> | undefined) ?? [],
    )
    const patrolJobCard = ((response.payload?.cards as Array<Record<string, unknown>> | undefined) ?? []).find(
      (card) => card.card_type === 'visual_patrol_job',
    )
    const patrolJobId = String((patrolJobCard?.data as Record<string, unknown> | undefined)?.job_id || '')
    if (patrolJobId) {
      void pollBackgroundJob(patrolJobId, async (job) => {
        const result = (job.result || {}) as Record<string, unknown>
        const reply = String(result.reply || '')
        const cards = (result.cards as Array<Record<string, unknown>> | undefined) ?? []
        const toolResults = (result.tool_results as Array<Record<string, unknown>> | undefined) ?? []
        if (job.status === 'success' && reply) {
          pushAssistantWithTrace(
            reply,
            [
              { stage: 'execute', status: 'done', title: '视觉巡检完成', detail: patrolJobId },
              { stage: 'result', status: 'done', title: '报告已生成', detail: reply.slice(0, 120) },
            ],
            cards,
            toolResults,
          )
        } else if (job.status === 'failed') {
          pushAssistant(`视觉巡检后台任务失败：${job.error || '未知错误'}`)
        }
      })
    }
  } catch (error) {
    pushAssistant(`请求失败：${error instanceof Error ? error.message : String(error)}`)
  } finally {
    isTyping.value = false
    scrollToBottom()
  }
}

function handleQuickAction(action: SkillAction) {
  if (action.enabled === false) return
  selectedSkillLabel.value = action.label
  if (action.skill === 'rag') {
    selectedSkillName.value = null
    mode.value = 'rag'
    inputText.value = action.prompt
    return
  }
  mode.value = 'chat'
  selectedSkillName.value = action.skill || null
  inputText.value = action.prompt
}

function handleUnload() {
  docmate.unload()
  mode.value = 'chat'
  pushAssistant('已退出文档改稿，恢复到助手问答模式。')
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    sendMessage()
  }
}

function clearConversation() {
  if (isTyping.value) return
  messages.value = [createWelcomeMessage()]
  nextId = 2
  currentSessionId.value = null
  inputText.value = ''
  selectedSkillLabel.value = ''
  selectedSkillName.value = null
  skillMenuOpen.value = false
  if (!docmate.isLoaded.value) {
    mode.value = 'chat'
  }
  scrollToBottom()
}
</script>

<template>
  <aside
    class="chatbot-panel"
    :class="{ 'chatbot-panel--hidden': !visible }"
    :style="visible ? { width: panelWidth + 'px' } : {}"
  >
    <div v-if="visible" class="chatbot-panel__resize" title="拖动调整宽度" @mousedown.prevent="startResize"></div>
    <div class="chatbot-panel__header">
      <div class="chatbot-panel__title">
        <img class="chatbot-panel__assistant-avatar" :src="assistantAvatar" alt="AI 助手头像" />
        <strong>闪闪助手</strong>
      </div>
      <button class="chatbot-panel__close" title="关闭" @click="emit('toggle')">×</button>
    </div>

    <!-- 文档上下文条（仅在加载文档后出现） -->
    <div v-if="docmate.isLoaded.value" class="doc-bar">
      <div class="doc-bar__info">
        <span class="doc-bar__icon">📄</span>
        <span class="doc-bar__name" :title="docmate.state.sourcePath">{{ docmate.docName.value }}</span>
        <span class="doc-bar__stat">{{ docmate.docStats.value.paragraph_count }} 段</span>
      </div>
      <div class="doc-bar__actions">
        <div class="mode-switch">
          <button :class="{ active: mode === 'edit' }" @click="mode = 'edit'">改稿</button>
          <button :class="{ active: mode === 'chat' }" @click="mode = 'chat'">问答</button>
        </div>
        <button class="doc-bar__unload" title="移除文档" @click="handleUnload">移除</button>
      </div>
    </div>

    <div ref="messagesEl" class="chatbot-panel__messages">
      <div
        v-for="message in messages"
        :key="message.id"
        class="chatbot-row"
        :class="`chatbot-row--${message.role}`"
      >
        <img v-if="message.role === 'assistant'" class="chatbot-avatar" :src="assistantAvatar" alt="闪闪助手" />
        <span v-else class="chatbot-avatar chatbot-avatar--user">👷</span>
        <article class="chatbot-message" :class="`chatbot-message--${message.role}`">
          <ChatRichBlocks
            v-if="message.role === 'assistant'"
            :content="message.content"
            :cards="message.cards"
            :tool-results="message.toolResults"
            :rich-blocks="message.richBlocks"
          />
          <template v-else>{{ message.content }}</template>
          <div v-if="message.role === 'assistant' && message.trace?.length" class="agent-trace">
            <button
              v-for="item in message.trace"
              :key="`${message.id}-${item.stage}-${item.title}`"
              type="button"
              class="agent-trace__item"
              :class="`agent-trace__item--${item.status}`"
              :title="item.detail"
            >
              <span>{{ item.stage }}</span>
              <strong>{{ item.title }}</strong>
            </button>
          </div>
        </article>
      </div>
      <div v-if="isTyping" class="chatbot-row chatbot-row--assistant">
        <img class="chatbot-avatar" :src="assistantAvatar" alt="闪闪助手" />
        <article class="chatbot-message chatbot-message--assistant">正在处理中...</article>
      </div>
    </div>

    <!-- 改稿 Diff 审阅（与文档工作台共享会话） -->
    <div v-if="mode === 'edit' && showDiffPanel" class="chatbot-panel__diff">
      <DocmateDiffReview />
    </div>

    <div v-if="mode !== 'edit'" class="skill-dock" :class="{ 'skill-dock--open': skillMenuOpen }">
      <div
        v-if="skillMenuOpen"
        class="skill-menu"
        :style="{ height: `${skillMenuHeight}px` }"
      >
        <div class="skill-menu__resize" title="上下拖动调整菜单高度" @mousedown.prevent="startSkillMenuResize"></div>
        <div class="skill-menu__header">
          <strong>技能</strong>
          <span>{{ skillsLoading ? '正在同步后台技能...' : skillsError ? '后台技能暂不可用，显示内置技能' : `已同步 ${backendSkills.length} 个后台技能` }}</span>
        </div>
        <button
          v-for="action in skillActions"
          :key="action.label"
          class="skill-menu__item"
          :class="{
            'skill-menu__item--disabled': action.enabled === false,
            'skill-menu__item--active': selectedSkillLabel === action.label,
          }"
          @click="handleQuickAction(action)"
        >
          <span class="skill-menu__item-icon">🔨</span>
          <span>
            <strong>{{ action.label }}</strong>
            <small>{{ action.enabled === false ? '已停用' : action.summary }}</small>
          </span>
        </button>
      </div>
      <div class="skill-dock__bar">
        <button
          class="skill-trigger"
          :class="{ 'skill-trigger--active': skillMenuOpen }"
          type="button"
          title="技能"
          @click="skillMenuOpen = !skillMenuOpen"
        >
          <span>🔨</span>
          <strong>技能</strong>
        </button>
        <button
          class="clear-chat-btn"
          type="button"
          title="清空当前对话并重新开始"
          :disabled="isTyping"
          @click="clearConversation"
        >
          清空对话
        </button>
      </div>
    </div>

    <div v-else class="chat-footer-tools">
      <button
        class="clear-chat-btn"
        type="button"
        title="清空当前对话并重新开始"
        :disabled="isTyping"
        @click="clearConversation"
      >
        清空对话
      </button>
    </div>

    <div class="chatbot-panel__input-area">
      <textarea
        v-model="inputText"
        :placeholder="placeholder"
        rows="2"
        @keydown="handleKeydown"
      />
      <button :disabled="!inputText.trim() || isTyping" @click="sendMessage">发送</button>
    </div>
  </aside>
</template>

<style scoped>
.chatbot-panel {
  background: #f7f9fc;
  border-left: 1px solid #e5e9f2;
  color: #1f2329;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  height: 100%;
  overflow: hidden;
  position: relative;
  transition: width 0.28s var(--ease-out), opacity 0.22s var(--ease-out), border-color 0.22s var(--ease-out);
  width: 380px;
}

.chatbot-panel--hidden {
  border-left-color: transparent;
  opacity: 0;
  pointer-events: none;
  width: 0 !important;
}

.chatbot-panel__resize {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 6px;
  cursor: col-resize;
  z-index: 5;
}

.chatbot-panel__resize:hover {
  background: rgb(51 112 255 / 22%);
}

.chatbot-panel__header {
  align-items: center;
  border-bottom: 1px solid #e5e9f2;
  display: flex;
  justify-content: space-between;
  min-width: 0;
  padding: 12px 14px;
}

.chatbot-panel__title {
  align-items: center;
  display: flex;
  gap: 10px;
}

.chatbot-panel__assistant-avatar {
  border: 1px solid #d5dbe7;
  border-radius: 50%;
  height: 30px;
  object-fit: cover;
  width: 30px;
}

.chatbot-panel__close {
  background: transparent;
  border: 0;
  color: #667085;
  font-size: 22px;
  cursor: pointer;
}

/* 文档上下文条 */
.doc-bar {
  border-bottom: 1px solid #e5e9f2;
  min-width: 0;
  padding: 8px 12px;
}

.doc-bar__info {
  align-items: center;
  display: flex;
  gap: 6px;
  margin-bottom: 6px;
  overflow: hidden;
}

.doc-bar__icon {
  flex-shrink: 0;
}

.doc-bar__name {
  color: #1f2329;
  font-size: 12px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-bar__stat {
  color: #667085;
  flex-shrink: 0;
  font-size: 11px;
}

.doc-bar__actions {
  align-items: center;
  display: flex;
  justify-content: space-between;
}

.mode-switch {
  background: #eef3fb;
  border-radius: 8px;
  display: flex;
  gap: 2px;
  padding: 2px;
}

.mode-switch button {
  background: transparent;
  border: 0;
  border-radius: 6px;
  color: #667085;
  cursor: pointer;
  font-size: 11px;
  padding: 4px 12px;
}

.mode-switch button.active {
  background: #3370ff;
  color: #fff;
}

.doc-bar__unload {
  background: #fff;
  border: 1px solid #d5dbe7;
  border-radius: 6px;
  color: #667085;
  cursor: pointer;
  font-size: 11px;
  padding: 4px 10px;
}

.doc-bar__unload:hover {
  color: #245bdb;
  border-color: rgb(51 112 255 / 36%);
}

.chatbot-panel__messages {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  overflow-y: auto;
  padding: 14px 12px;
}

.chatbot-row {
  align-items: flex-start;
  display: flex;
  gap: 8px;
  max-width: 100%;
}

.chatbot-row--user {
  flex-direction: row-reverse;
}

.chatbot-avatar {
  background: #fff;
  border: 1px solid #d5dbe7;
  border-radius: 50%;
  box-shadow: 0 1px 2px rgb(16 24 40 / 8%);
  flex-shrink: 0;
  height: 30px;
  object-fit: cover;
  width: 30px;
}

.chatbot-avatar--user {
  align-items: center;
  background: #fff7ed;
  border-color: #fed7aa;
  color: #c2410c;
  display: inline-flex;
  font-size: 18px;
  justify-content: center;
}

.chatbot-message {
  border-radius: 14px;
  font-size: 13px;
  line-height: 1.55;
  max-width: calc(100% - 48px);
  padding: 10px 12px;
  position: relative;
  white-space: pre-wrap;
}

.chatbot-message--assistant {
  background: #fff;
  border: 1px solid #e5e9f2;
  border-top-left-radius: 4px;
  box-shadow: 0 1px 2px rgb(16 24 40 / 5%);
}

.chatbot-message--user {
  background: #95ec69;
  border: 1px solid rgb(89 191 62 / 30%);
  border-top-right-radius: 4px;
  color: #1f2329;
  box-shadow: 0 1px 2px rgb(16 24 40 / 5%);
}

.agent-trace {
  border-top: 1px dashed #d5dbe7;
  display: grid;
  gap: 6px;
  margin-top: 10px;
  padding-top: 8px;
}

.agent-trace__item {
  align-items: center;
  background: #f8fafc;
  border: 1px solid #e5e9f2;
  border-radius: 10px;
  color: #1f2329;
  display: grid;
  gap: 2px;
  grid-template-columns: 64px 1fr;
  padding: 6px 8px;
  text-align: left;
}

.agent-trace__item span {
  color: #667085;
  font-size: 10px;
  text-transform: uppercase;
}

.agent-trace__item strong {
  font-size: 11px;
}

.agent-trace__item--error {
  background: #fff1f2;
  border-color: #fecdd3;
}

.chatbot-panel__diff {
  border-top: 1px solid #e5e9f2;
  max-height: 46%;
  min-width: 0;
  overflow-y: auto;
  padding: 10px 12px;
}

.skill-dock {
  border-top: 1px solid #e5e9f2;
  padding: 8px 12px 0;
}

.skill-dock__bar {
  align-items: center;
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.chat-footer-tools {
  border-top: 1px solid #e5e9f2;
  display: flex;
  justify-content: flex-end;
  padding: 8px 12px 0;
}

.clear-chat-btn {
  background: #fff;
  border: 1px solid #d5dbe7;
  border-radius: 999px;
  color: #667085;
  cursor: pointer;
  font-size: 12px;
  padding: 6px 12px;
}

.clear-chat-btn:hover:not(:disabled) {
  background: #fff7ed;
  border-color: #fdba74;
  color: #c2410c;
}

.clear-chat-btn:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.skill-menu {
  background: #fff;
  border: 1px solid #d5dbe7;
  border-radius: 12px;
  box-shadow: 0 10px 26px rgb(16 24 40 / 12%);
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 8px;
  min-height: 92px;
  overflow-y: auto;
  padding: 14px 10px 10px;
  position: relative;
}

.skill-menu__resize {
  background: #d5dbe7;
  border-radius: 999px;
  cursor: row-resize;
  height: 4px;
  left: 50%;
  position: absolute;
  top: 5px;
  transform: translateX(-50%);
  width: 42px;
}

.skill-menu__header {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-bottom: 2px;
}

.skill-menu__header strong {
  color: #1f2329;
  font-size: 13px;
}

.skill-menu__header span {
  color: #667085;
  font-size: 11px;
}

.skill-menu__item {
  align-items: center;
  background: #f7f9fc;
  border: 1px solid #e5e9f2;
  border-radius: 10px;
  color: #1f2329;
  display: flex;
  gap: 8px;
  padding: 8px 10px;
  text-align: left;
}

.skill-menu__item > span:last-child {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.skill-menu__item strong {
  font-size: 12px;
}

.skill-menu__item small {
  color: #667085;
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.skill-menu__item:hover {
  background: #eef3fb;
  border-color: rgb(51 112 255 / 28%);
  color: #245bdb;
}

.skill-menu__item--active {
  background: #eef3fb;
  border-color: rgb(51 112 255 / 40%);
  color: #245bdb;
}

.skill-menu__item--disabled {
  opacity: 0.56;
}

.skill-menu__item-icon {
  color: #3370ff;
  font-weight: 900;
}

.skill-trigger {
  align-items: center;
  background: #fff;
  border: 1px solid #d5dbe7;
  border-radius: 999px;
  color: #667085;
  display: inline-flex;
  gap: 6px;
  padding: 6px 12px;
}

.skill-trigger--active,
.skill-trigger:hover {
  background: #e7f0ff;
  border-color: rgb(51 112 255 / 34%);
  color: #245bdb;
}

.chatbot-panel__input-area {
  align-items: flex-end;
  border-top: 1px solid #e5e9f2;
  display: flex;
  gap: 8px;
  min-width: 0;
  padding: 10px 12px;
}

.chatbot-panel__input-area textarea {
  background: #fff;
  border: 1px solid #d5dbe7;
  border-radius: 10px;
  color: #1f2329;
  flex: 1;
  outline: none;
  padding: 8px 10px;
  resize: none;
}

.chatbot-panel__input-area button {
  background: #3370ff;
  border: 0;
  border-radius: 8px;
  color: white;
  padding: 8px 12px;
  cursor: pointer;
}

.chatbot-panel__input-area button:disabled {
  cursor: not-allowed;
  opacity: 0.35;
}
</style>
