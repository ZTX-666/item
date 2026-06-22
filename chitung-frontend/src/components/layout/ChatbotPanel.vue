<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useAiAssistant } from '../../composables/useAiAssistant'
import { useDocmateSession } from '../../composables/useDocmateSession'
import DocmateDiffReview from '../documents/DocmateDiffReview.vue'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  toggle: []
}>()

const {
  messages,
  inputText,
  isTyping,
  messagesEl,
  quickActions: assistantQuickActions,
  loadLatestHistory,
  sendMessage,
  handleQuickAction,
  handleKeydown,
  toolName,
  toolOk,
  toolSummary,
  cardTitle,
  cardSummary,
  cardActions,
  cardActionLabel,
  actionKey,
  actionRunning,
  handleCardAction,
  appliedSkillName,
  skillHighlights,
  skillNextActions,
  resultImages,
  resultReports,
} = useAiAssistant()

const docmate = useDocmateSession()
const panelWidth = ref(380)
let resizing = false
let startX = 0
let startWidth = 0

const panelQuickActions = computed(() => [
  {
    label: '文档改稿',
    prompt: docmate.isLoaded.value
      ? `使用 DocMate 文档改稿 Skill，基于当前文档「${docmate.docName.value || '未命名文档'}」生成修改建议。`
      : '使用 DocMate 文档改稿 Skill，指导我上传 DOCX 并进行差异审阅。',
    context: {
      skill_hint: 'docmate-edit',
      docmate: {
        doc_id: docmate.state.docId,
        source_path: docmate.state.sourcePath,
        file_name: docmate.docName.value,
        loaded: docmate.isLoaded.value,
      },
    },
  },
  ...assistantQuickActions.map((action) => ({ ...action, context: {} })),
])

const showDocmateReview = computed(
  () => docmate.hasWork.value || docmate.state.step === 'committing' || docmate.isDone.value,
)

function bindMessagesEl(el: unknown) {
  messagesEl.value = el instanceof HTMLElement ? el : null
}

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
  const delta = startX - event.clientX
  panelWidth.value = Math.min(760, Math.max(340, startWidth + delta))
}

function stopResize() {
  if (!resizing) return
  resizing = false
  window.removeEventListener('mousemove', onResize)
  window.removeEventListener('mouseup', stopResize)
  document.body.style.userSelect = ''
  document.body.style.cursor = ''
}

function handlePanelQuickAction(action: { prompt: string; context?: Record<string, unknown> }) {
  handleQuickAction(action.prompt, action.context ?? {})
}

function handleDocmateUnload() {
  docmate.unload()
}

onBeforeUnmount(stopResize)

watch(
  () => props.visible,
  (visible) => {
    if (visible) loadLatestHistory()
  },
  { immediate: true },
)
</script>

<template>
  <aside
    class="chatbot-panel"
    :class="{ 'chatbot-panel--hidden': !visible }"
    :style="visible ? { width: `${panelWidth}px` } : undefined"
  >
    <div v-if="visible" class="chatbot-panel__resize" title="拖动调整宽度" @mousedown.prevent="startResize"></div>
    <div class="chatbot-panel__header">
      <div>
        <strong>赤瞳 AI</strong>
        <span>中台编排助手</span>
      </div>
      <button class="chatbot-panel__close" title="关闭" @click="emit('toggle')">×</button>
    </div>
    <div v-if="docmate.isLoaded.value" class="docmate-context">
      <div class="docmate-context__main">
        <span class="docmate-context__mark">DOCX</span>
        <span class="docmate-context__name" :title="docmate.state.sourcePath">{{ docmate.docName.value }}</span>
        <span class="docmate-context__stat">{{ docmate.docStats.value.paragraph_count }} 段</span>
      </div>
      <button class="docmate-context__clear" title="移除当前文档" @click="handleDocmateUnload">移除</button>
    </div>
    <div :ref="bindMessagesEl" class="chatbot-panel__messages">
      <article
        v-for="message in messages"
        :key="message.id"
        class="chatbot-message"
        :class="`chatbot-message--${message.role}`"
      >
        <div class="chatbot-message__body">
          <p>{{ message.content }}</p>
          <div class="chatbot-message__meta">
            <span v-if="message.status" class="chatbot-message__status">{{ message.status }}</span>
            <span v-if="message.intent" class="chatbot-message__intent">意图 {{ message.intent }}</span>
            <span v-if="appliedSkillName(message)" class="chatbot-message__skill">
              Skill {{ appliedSkillName(message) }}
            </span>
            <span v-if="message.workflowName" class="chatbot-message__workflow">
              Workflow {{ message.workflowName }}
            </span>
          </div>
        </div>
        <div
          v-if="skillHighlights(message).length || skillNextActions(message).length"
          class="chatbot-message__skill-detail"
        >
          <p v-if="skillHighlights(message).length">{{ skillHighlights(message).join('；') }}</p>
          <div v-if="skillNextActions(message).length" class="chatbot-card__actions">
            <span v-for="action in skillNextActions(message)" :key="action">{{ action }}</span>
          </div>
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
              <button
                v-for="action in cardActions(card)"
                :key="String(action.id || action.action_id || action.label)"
                :disabled="actionRunning(actionKey(message, card, action))"
                @click="handleCardAction(message, card, action)"
              >
                {{ actionRunning(actionKey(message, card, action)) ? '执行中' : cardActionLabel(action) }}
              </button>
            </div>
          </article>
        </div>
        <div v-if="resultReports(message).length" class="chatbot-message__reports">
          <article v-for="report in resultReports(message)" :key="`${report.title}-${report.reportId || report.text}`" class="chatbot-report">
            <div class="chatbot-report__header">
              <strong>{{ report.title }}</strong>
              <span v-if="report.reportId">#{{ report.reportId }}</span>
            </div>
            <p v-if="report.text">{{ report.text }}</p>
            <div v-if="report.links.length" class="chatbot-report__links">
              <a v-for="link in report.links" :key="link.url" :href="link.url" target="_blank" rel="noreferrer">
                {{ link.label }}
              </a>
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
    <div v-if="showDocmateReview" class="chatbot-panel__docmate-review">
      <DocmateDiffReview />
    </div>
    <div class="chatbot-panel__quick">
      <button v-for="action in panelQuickActions" :key="action.label" @click="handlePanelQuickAction(action)">
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
      <button :disabled="!inputText.trim() || isTyping" @click="() => sendMessage()">发送</button>
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
  transition: width 0.2s ease, opacity 0.2s ease;
  width: 380px;
}

.chatbot-panel--hidden {
  border-left: 0;
  opacity: 0;
  width: 0;
}

.chatbot-panel__resize {
  bottom: 0;
  cursor: col-resize;
  left: 0;
  position: absolute;
  top: 0;
  width: 6px;
  z-index: 5;
}

.chatbot-panel__resize:hover {
  background: rgba(96, 165, 250, 0.28);
}

.chatbot-panel__header {
  align-items: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  justify-content: space-between;
  min-width: 340px;
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

.docmate-context {
  align-items: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  gap: 8px;
  justify-content: space-between;
  min-width: 340px;
  padding: 8px 12px;
}

.docmate-context__main {
  align-items: center;
  display: flex;
  gap: 7px;
  min-width: 0;
}

.docmate-context__mark {
  border: 1px solid rgba(96, 165, 250, 0.35);
  border-radius: 5px;
  color: #93c5fd;
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.4px;
  padding: 2px 5px;
}

.docmate-context__name {
  color: #e5e7eb;
  font-size: 12px;
  font-weight: 650;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.docmate-context__stat {
  color: #6b7280;
  flex-shrink: 0;
  font-size: 11px;
}

.docmate-context__clear {
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 6px;
  color: #8b949e;
  flex-shrink: 0;
  font-size: 11px;
  padding: 3px 8px;
}

.docmate-context__clear:hover {
  border-color: rgba(248, 113, 113, 0.35);
  color: #fca5a5;
}

.chatbot-panel__messages {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 10px;
  min-width: 340px;
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

.chatbot-message__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chatbot-message__status,
.chatbot-message__intent,
.chatbot-message__skill,
.chatbot-message__workflow {
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 999px;
  color: #9ca3af;
  font-size: 11px;
  justify-self: start;
  padding: 2px 7px;
}

.chatbot-message__intent {
  border-color: rgba(96, 165, 250, 0.28);
  color: #93c5fd;
}

.chatbot-message__skill {
  border: 1px solid rgba(248, 113, 113, 0.26);
  color: #fca5a5;
}

.chatbot-message__workflow {
  border-color: rgba(52, 211, 153, 0.24);
  color: #6ee7b7;
}

.chatbot-message__skill-detail {
  background: rgba(127, 29, 29, 0.18);
  border: 1px solid rgba(248, 113, 113, 0.16);
  border-radius: 8px;
  display: grid;
  gap: 6px;
  margin-top: 8px;
  padding: 8px;
}

.chatbot-message__skill-detail p {
  color: #fecaca;
  margin: 0;
}

.chatbot-message__tools,
.chatbot-message__cards,
.chatbot-message__reports,
.chatbot-message__images {
  display: grid;
  gap: 8px;
  margin-top: 8px;
}

.chatbot-tool-result,
.chatbot-card,
.chatbot-report {
  background: rgba(15, 23, 42, 0.42);
  border: 1px solid rgba(148, 163, 184, 0.14);
  border-radius: 8px;
  display: grid;
  gap: 4px;
  padding: 8px;
}

.chatbot-tool-result strong,
.chatbot-card strong,
.chatbot-report strong {
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
.chatbot-card p,
.chatbot-report p {
  color: #9ca3af;
  margin: 0;
  white-space: pre-wrap;
}

.chatbot-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chatbot-card__actions span,
.chatbot-card__actions button,
.chatbot-report__links a {
  background: transparent;
  border: 1px solid rgba(59, 130, 246, 0.28);
  border-radius: 999px;
  color: #93c5fd;
  font-size: 11px;
  padding: 2px 7px;
  text-decoration: none;
}

.chatbot-card__actions button:disabled {
  cursor: wait;
  opacity: 0.55;
}

.chatbot-report__header {
  align-items: center;
  display: flex;
  gap: 6px;
  justify-content: space-between;
}

.chatbot-report__header span {
  color: #64748b;
  font-size: 11px;
}

.chatbot-report__links {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
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

.chatbot-panel__docmate-review {
  --review-border: rgba(255, 255, 255, 0.08);
  --review-hover: rgba(255, 255, 255, 0.06);
  --review-muted: #8b949e;
  --review-panel: rgba(255, 255, 255, 0.03);
  --review-text: #c9d1d9;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  max-height: 45%;
  min-width: 340px;
  overflow-y: auto;
  padding: 10px 12px;
}

.chatbot-panel__quick {
  display: flex;
  gap: 6px;
  min-width: 340px;
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
  min-width: 340px;
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
