<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { sendChatMessage } from '../../services/chitungApi'

defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  toggle: []
}>()

interface Message {
  id: number
  role: 'user' | 'assistant'
  content: string
  status?: '执行中' | '完成' | '失败'
  cards?: Array<Record<string, unknown>>
  toolResults?: Array<Record<string, unknown>>
  intent?: string
}

const messages = ref<Message[]>([
  {
    id: 1,
    role: 'assistant',
    content: '你好，我是赤瞳 AI 助手。可以帮你处理隐患、巡检、填表、制度查询和工作流编排。',
  },
])
const inputText = ref('')
const isTyping = ref(false)
const messagesEl = ref<HTMLElement | null>(null)
let nextId = 2

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

async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || isTyping.value) return
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
    const response = await sendChatMessage({ message: text, channel: 'local_chat' })
    updateAssistantMessage(assistantId, {
      content: response.message,
      status: '完成',
      cards: (response.payload?.cards as Array<Record<string, unknown>> | undefined) ?? [],
      toolResults: (response.payload?.toolResults as Array<Record<string, unknown>> | undefined) ?? [],
      intent: String((response.payload?.intent as Record<string, unknown> | undefined)?.intent || ''),
    })
  } catch (error) {
    updateAssistantMessage(assistantId, {
      content: `请求失败：${error instanceof Error ? error.message : String(error)}`,
      status: '失败',
    })
  } finally {
    isTyping.value = false
    scrollToBottom()
  }
}

function updateAssistantMessage(id: number, patch: Partial<Message>) {
  const index = messages.value.findIndex((message) => message.id === id)
  if (index >= 0) {
    messages.value[index] = { ...messages.value[index], ...patch }
  }
}

function handleQuickAction(prompt: string) {
  inputText.value = prompt
  sendMessage()
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    sendMessage()
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

function resultImages(message: Message) {
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

function collectImagesFromValue(value: unknown, images: Array<{ title: string; url: string; caption?: string }>) {
  if (!value || typeof value !== 'object') return
  const record = value as Record<string, unknown>
  for (const key of ['annotated_url', 'snapshot_url', 'image_url', 'thumbnail_url']) {
    const url = record[key]
    if (typeof url === 'string' && url) {
      images.push({ title: String(record.title || key), url, caption: String(record.camera_name || record.source_name || '') })
    }
  }
  for (const key of ['report', 'data', 'briefing']) collectImagesFromValue(record[key], images)
  for (const key of ['report_images', 'images', 'items', 'cameras']) {
    const list = record[key]
    if (!Array.isArray(list)) continue
    for (const item of list) collectImagesFromValue(item, images)
  }
}
</script>

<template>
  <aside class="chatbot-panel" :class="{ 'chatbot-panel--hidden': !visible }">
    <div class="chatbot-panel__header">
      <div>
        <strong>赤瞳 AI</strong>
        <span>中台编排助手</span>
      </div>
      <button class="chatbot-panel__close" title="关闭" @click="emit('toggle')">×</button>
    </div>
    <div ref="messagesEl" class="chatbot-panel__messages">
      <article
        v-for="message in messages"
        :key="message.id"
        class="chatbot-message"
        :class="`chatbot-message--${message.role}`"
      >
        <div class="chatbot-message__body">
          <p>{{ message.content }}</p>
          <span v-if="message.status" class="chatbot-message__status">{{ message.status }}</span>
        </div>
        <div v-if="message.toolResults?.length" class="chatbot-message__tools">
          <article
            v-for="(result, index) in message.toolResults"
            :key="`${message.id}-tool-${index}`"
            class="chatbot-tool-result"
            :class="{ 'chatbot-tool-result--failed': !toolOk(result) }"
          >
            <strong>{{ toolName(result) }}</strong>
            <span>{{ toolOk(result) ? '完成' : '失败' }}</span>
            <p>{{ toolSummary(result) }}</p>
          </article>
        </div>
        <div v-if="message.cards?.length" class="chatbot-message__cards">
          <article v-for="(card, index) in message.cards" :key="`${message.id}-card-${index}`" class="chatbot-card">
            <strong>{{ cardTitle(card) }}</strong>
            <p>{{ cardSummary(card) }}</p>
            <div v-if="cardActions(card).length" class="chatbot-card__actions">
              <span v-for="action in cardActions(card)" :key="String(action.id || action.label)">
                {{ action.label || action.id }}
              </span>
            </div>
          </article>
        </div>
        <div v-if="resultImages(message).length" class="chatbot-message__images">
          <figure v-for="image in resultImages(message)" :key="image.url" class="chatbot-result-image">
            <img :src="image.url" :alt="image.title" />
            <figcaption>{{ image.caption || image.title }}</figcaption>
          </figure>
        </div>
      </article>
    </div>
    <div class="chatbot-panel__quick">
      <button v-for="action in quickActions" :key="action.label" @click="handleQuickAction(action.prompt)">
        {{ action.label }}
      </button>
    </div>
    <div class="chatbot-panel__input-area">
      <textarea
        v-model="inputText"
        placeholder="输入消息，Enter 发送，Shift+Enter 换行"
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
  transition: width 0.2s ease, opacity 0.2s ease;
  width: 360px;
}

.chatbot-panel--hidden {
  border-left: 0;
  opacity: 0;
  width: 0;
}

.chatbot-panel__header {
  align-items: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  justify-content: space-between;
  min-width: 360px;
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
}

.chatbot-panel__messages {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 10px;
  min-width: 360px;
  overflow-y: auto;
  padding: 12px;
}

.chatbot-message {
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.55;
  max-width: 88%;
  padding: 9px 11px;
}

.chatbot-message--assistant {
  background: rgba(255, 255, 255, 0.05);
}

.chatbot-message--user {
  align-self: flex-end;
  background: rgba(59, 130, 246, 0.16);
  color: #93c5fd;
}

.chatbot-message__body {
  display: grid;
  gap: 6px;
}

.chatbot-message__body p {
  margin: 0;
  white-space: pre-wrap;
}

.chatbot-message__status {
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 999px;
  color: #9ca3af;
  font-size: 11px;
  justify-self: start;
  padding: 2px 7px;
}

.chatbot-message__tools,
.chatbot-message__cards,
.chatbot-message__images {
  display: grid;
  gap: 8px;
  margin-top: 8px;
}

.chatbot-tool-result,
.chatbot-card {
  background: rgba(15, 23, 42, 0.42);
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 8px;
  display: grid;
  gap: 4px;
  padding: 8px;
}

.chatbot-tool-result strong,
.chatbot-card strong {
  color: #e5e7eb;
}

.chatbot-tool-result span {
  color: #34d399;
  font-size: 11px;
}

.chatbot-tool-result--failed span {
  color: #f87171;
}

.chatbot-tool-result p,
.chatbot-card p {
  color: #9ca3af;
  margin: 0;
}

.chatbot-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chatbot-card__actions span {
  border: 1px solid rgba(59, 130, 246, 0.28);
  border-radius: 999px;
  color: #93c5fd;
  font-size: 11px;
  padding: 2px 7px;
}

.chatbot-result-image {
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 8px;
  margin: 0;
  overflow: hidden;
}

.chatbot-result-image img {
  aspect-ratio: 16 / 9;
  background: #111827;
  display: block;
  object-fit: cover;
  width: 100%;
}

.chatbot-result-image figcaption {
  color: #9ca3af;
  font-size: 11px;
  padding: 6px 8px;
}

.chatbot-panel__quick {
  display: flex;
  gap: 6px;
  min-width: 360px;
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
}

.chatbot-panel__input-area {
  align-items: flex-end;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  gap: 8px;
  min-width: 360px;
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
}

.chatbot-panel__input-area button:disabled {
  cursor: not-allowed;
  opacity: 0.35;
}
</style>
