<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { sendChatMessage } from '../../services/chitungApi'
import { useDocmateSession } from '../../composables/useDocmateSession'
import DocmateDiffReview from '../documents/DocmateDiffReview.vue'

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

onBeforeUnmount(stopResize)

interface Message {
  id: number
  role: 'user' | 'assistant'
  content: string
}

const messages = ref<Message[]>([
  {
    id: 1,
    role: 'assistant',
    content:
      '你好，我是赤瞳 AI 助手。我可以处理隐患、巡检、填表、制度查询和工作流编排，也能直接帮你改写 Word 文档（加载文档后即可用自然语言改稿）。',
  },
])
const inputText = ref('')
const isTyping = ref(false)
const messagesEl = ref<HTMLElement | null>(null)
let nextId = 2

// ── DocMate 文档改稿能力（与文档工作台共享同一会话） ──
const docmate = useDocmateSession()
const mode = ref<'chat' | 'edit'>('chat')

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
    : '输入消息，Enter 发送，Shift+Enter 换行',
)

const showDiffPanel = computed(
  () => docmate.hasWork.value || docmate.state.step === 'committing' || docmate.isDone.value,
)

const quickActions = [
  { label: '隐患排查', prompt: '帮我分析最近的安全隐患' },
  { label: '生成通知', prompt: '生成一份高处作业安全隐患整改通知' },
  { label: '每日简报', prompt: '生成今日外部风险简报' },
  { label: '制度查询', prompt: '查询临边作业安全管理要求' },
]

function scrollToBottom() {
  nextTick(() => {
    if (messagesEl.value) messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  })
}

function pushAssistant(content: string) {
  messages.value.push({ id: nextId++, role: 'assistant', content })
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

  // 普通中台问答
  messages.value.push({ id: nextId++, role: 'user', content: text })
  inputText.value = ''
  isTyping.value = true
  scrollToBottom()
  try {
    const response = await sendChatMessage({ message: text, channel: 'local_chat' })
    pushAssistant(response.message)
  } catch (error) {
    pushAssistant(`请求失败：${error instanceof Error ? error.message : String(error)}`)
  } finally {
    isTyping.value = false
    scrollToBottom()
  }
}

function handleQuickAction(prompt: string) {
  inputText.value = prompt
  sendMessage()
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
</script>

<template>
  <aside
    class="chatbot-panel"
    :class="{ 'chatbot-panel--hidden': !visible }"
    :style="visible ? { width: panelWidth + 'px' } : {}"
  >
    <div v-if="visible" class="chatbot-panel__resize" title="拖动调整宽度" @mousedown.prevent="startResize"></div>
    <div class="chatbot-panel__header">
      <div>
        <strong>赤瞳 AI</strong>
        <span>中台编排助手</span>
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
      <article
        v-for="message in messages"
        :key="message.id"
        class="chatbot-message"
        :class="`chatbot-message--${message.role}`"
      >
        {{ message.content }}
      </article>
      <article v-if="isTyping" class="chatbot-message chatbot-message--assistant">正在处理中...</article>
    </div>

    <!-- 改稿 Diff 审阅（与文档工作台共享会话） -->
    <div v-if="mode === 'edit' && showDiffPanel" class="chatbot-panel__diff">
      <DocmateDiffReview />
    </div>

    <div v-if="mode === 'chat'" class="chatbot-panel__quick">
      <button v-for="action in quickActions" :key="action.label" @click="handleQuickAction(action.prompt)">
        {{ action.label }}
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
  background: #1a1d23;
  border-left: 1px solid rgba(255, 255, 255, 0.06);
  color: #c9d1d9;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  height: 100%;
  overflow: hidden;
  position: relative;
  transition: opacity 0.2s ease;
  width: 380px;
}

.chatbot-panel--hidden {
  border-left: 0;
  opacity: 0;
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
  background: rgba(108, 140, 255, 0.4);
}

.chatbot-panel__header {
  align-items: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  justify-content: space-between;
  min-width: 0;
  padding: 12px 14px;
}

.chatbot-panel__header span {
  color: #6b7280;
  display: block;
  font-size: 11px;
}

.chatbot-panel__close {
  background: transparent;
  border: 0;
  color: #8b949e;
  font-size: 22px;
  cursor: pointer;
}

/* 文档上下文条 */
.doc-bar {
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
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
  color: #e8e8ec;
  font-size: 12px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-bar__stat {
  color: #6b7280;
  flex-shrink: 0;
  font-size: 11px;
}

.doc-bar__actions {
  align-items: center;
  display: flex;
  justify-content: space-between;
}

.mode-switch {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  display: flex;
  gap: 2px;
  padding: 2px;
}

.mode-switch button {
  background: transparent;
  border: 0;
  border-radius: 6px;
  color: #8b949e;
  cursor: pointer;
  font-size: 11px;
  padding: 4px 12px;
}

.mode-switch button.active {
  background: #3b82f6;
  color: #fff;
}

.doc-bar__unload {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  color: #8b949e;
  cursor: pointer;
  font-size: 11px;
  padding: 4px 10px;
}

.doc-bar__unload:hover {
  color: #fca5a5;
  border-color: rgba(239, 68, 68, 0.3);
}

.chatbot-panel__messages {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
  overflow-y: auto;
  padding: 12px;
}

.chatbot-message {
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.55;
  max-width: 88%;
  padding: 9px 11px;
  white-space: pre-wrap;
}

.chatbot-message--assistant {
  background: rgba(255, 255, 255, 0.05);
}

.chatbot-message--user {
  align-self: flex-end;
  background: rgba(59, 130, 246, 0.16);
  color: #93c5fd;
}

.chatbot-panel__diff {
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  max-height: 46%;
  min-width: 0;
  overflow-y: auto;
  padding: 10px 12px;
}

.chatbot-panel__quick {
  display: flex;
  gap: 6px;
  min-width: 0;
  overflow-x: auto;
  padding: 8px 12px;
}

.chatbot-panel__quick button {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  color: #8b949e;
  padding: 5px 10px;
  white-space: nowrap;
  cursor: pointer;
}

.chatbot-panel__input-area {
  align-items: flex-end;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  gap: 8px;
  min-width: 0;
  padding: 10px 12px;
}

.chatbot-panel__input-area textarea {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  color: #c9d1d9;
  flex: 1;
  outline: none;
  padding: 8px 10px;
  resize: none;
}

.chatbot-panel__input-area button {
  background: #3b82f6;
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
