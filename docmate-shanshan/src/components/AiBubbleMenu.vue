<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { BubbleMenu } from '@tiptap/vue-3'
import type { Editor } from '@tiptap/vue-3'
import type { EditorAiState } from '@/composables/useEditorAi'
import { useAgentDraft } from '@/composables/useAgentDraft'

const props = defineProps<{
  editor: Editor | undefined
  aiState: EditorAiState
  agentBusy?: boolean
  thinkingLog: string
  getLockedRect: () => DOMRect | null
}>()

const emit = defineEmits<{
  submit: [command: string]
  cancel: []
  riskScan: []
  toast: [message: string, type?: 'success' | 'info' | 'error']
}>()

const inputRef = ref<HTMLInputElement | null>(null)
const thinkingRef = ref<HTMLElement | null>(null)
const showSlashMenu = ref(false)
const { agentDraft, clearAgentDraft } = useAgentDraft()

const QUICK = [
  { label: '正式', cmd: '把选中文本改得更正式' },
  { label: '精简', cmd: '精简选中文本，去掉冗余' },
  { label: '润色', cmd: '润色选中文本' },
  { label: '风险', cmd: '__risk__' },
]

const slashCommands = [
  { id: 'formal', name: '正式', desc: '转为正式公文语体', cmd: '把选中文本改得更正式' },
  { id: 'concise', name: '精简', desc: '精简冗余表述', cmd: '精简选中文本，去掉冗余' },
  { id: 'polish', name: '润色', desc: '润色文字表达', cmd: '润色选中文本' },
  { id: 'risk', name: '风险', desc: '检查合规风险', cmd: '__risk__' },
]

const isThinking = computed(() => props.aiState === 'thinking' || props.agentBusy)
const isBusy = computed(() => isThinking.value || props.aiState === 'reviewing')
const canSend = computed(() => !isBusy.value && agentDraft.value.trim().length > 0)

const canShow = computed(() => {
  if (props.aiState === 'reviewing') return false
  return props.aiState === 'selected' || props.aiState === 'thinking'
})

watch(
  () => props.thinkingLog,
  () => {
    nextTick(() => {
      if (thinkingRef.value) thinkingRef.value.scrollTop = thinkingRef.value.scrollHeight
    })
  },
)

watch(agentDraft, (v) => {
  showSlashMenu.value = v === '/'
})

function shouldShow() {
  if (!canShow.value) return false
  return !!props.getLockedRect()
}

function tippyOptions() {
  return {
    duration: 80,
    placement: 'top' as const,
    interactive: true,
    appendTo: () => document.body,
    getReferenceClientRect: () => props.getLockedRect() ?? new DOMRect(0, 0, 0, 0),
  }
}

function guardEditorBlur(e: MouseEvent) {
  e.preventDefault()
}

function runQuick(cmd: string) {
  if (isBusy.value) return
  if (cmd === '__risk__') {
    emit('riskScan')
    return
  }
  emit('submit', cmd)
}

function handleSlashCommand(cmd: { cmd: string }) {
  showSlashMenu.value = false
  clearAgentDraft()
  runQuick(cmd.cmd)
}

function handleSubmit() {
  const t = agentDraft.value.trim()
  if (!t || isBusy.value) return
  clearAgentDraft()
  showSlashMenu.value = false
  emit('submit', t)
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && showSlashMenu.value) {
    showSlashMenu.value = false
    clearAgentDraft()
    return
  }
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSubmit()
  }
}
</script>

<template>
  <BubbleMenu
    v-if="editor"
    :editor="editor"
    :should-show="shouldShow"
    :tippy-options="tippyOptions()"
    class="ai-bubble-menu"
  >
    <div class="bubble-inner">
      <div v-if="isThinking" class="thinking-panel" @mousedown="guardEditorBlur">
        <div class="thinking-bar" />
        <div class="thinking-head">
          <span class="thinking-title">深度思考</span>
          <button class="stop-btn" type="button" title="终止" @click="emit('cancel')">
            <span class="stop-icon" />
          </button>
        </div>
        <pre ref="thinkingRef" class="thinking-body">{{ thinkingLog || '任务已同步到右侧闪闪面板，正在分析…' }}</pre>
      </div>

      <template v-else>
        <div class="quick-row" @mousedown="guardEditorBlur">
          <button
            v-for="q in QUICK"
            :key="q.label"
            class="shortcut-chip"
            type="button"
            :disabled="isBusy"
            @click="runQuick(q.cmd)"
          >
            {{ q.label }}
          </button>
        </div>

        <div class="composer">
          <div v-if="showSlashMenu" class="slash-menu">
            <button
              v-for="cmd in slashCommands"
              :key="cmd.id"
              type="button"
              class="slash-item"
              @mousedown="guardEditorBlur"
              @click="handleSlashCommand(cmd)"
            >
              <span class="slash-name">/{{ cmd.name }}</span>
              <span class="slash-desc">{{ cmd.desc }}</span>
            </button>
          </div>
          <input
            ref="inputRef"
            v-model="agentDraft"
            class="bubble-input"
            placeholder="说怎么改… / 命令 · Enter 发送"
            :disabled="isBusy"
            @mousedown.stop
            @click.stop
            @keydown="onKeydown"
          />
          <div class="composer-actions" @mousedown="guardEditorBlur">
            <button
              class="action-btn send"
              type="button"
              title="Apply 执行"
              :disabled="!canSend"
              @click="handleSubmit"
            >
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5">
                <path d="M12 19V5M12 5l-5 5M12 5l5 5" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
          </div>
        </div>
      </template>
    </div>
  </BubbleMenu>
</template>

<style scoped>
.ai-bubble-menu {
  z-index: 60;
}

.bubble-inner {
  background: var(--bg-base);
  border: 1px solid var(--border-light);
  border-radius: 14px;
  box-shadow: 0 10px 32px rgba(0, 0, 0, 0.45);
  padding: 10px;
  min-width: 320px;
  max-width: 440px;
}

.thinking-panel {
  min-width: 300px;
}

.thinking-bar {
  height: 2px;
  margin: -2px -2px 8px;
  border-radius: 2px 2px 0 0;
  background: linear-gradient(90deg, transparent, var(--accent), transparent);
  background-size: 200% 100%;
  animation: thinking-shimmer 1.5s ease-in-out infinite;
}

@keyframes thinking-shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.thinking-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.thinking-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
}

.thinking-body {
  margin: 0;
  padding: 8px 10px;
  max-height: 140px;
  overflow: auto;
  font-size: 11px;
  line-height: 1.5;
  color: var(--text-muted);
  background: var(--bg-input);
  border-radius: 8px;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
}

.stop-btn {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: var(--bg-hover);
  display: flex;
  align-items: center;
  justify-content: center;
}

.stop-icon {
  width: 8px;
  height: 8px;
  background: var(--red);
  border-radius: 1px;
}

.quick-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.shortcut-chip {
  padding: 2px 8px;
  font-size: 11px;
  border-radius: 999px;
  background: var(--bg-hover);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}

.shortcut-chip:hover:not(:disabled) {
  background: var(--accent-muted);
  color: var(--accent);
}

.shortcut-chip:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.composer {
  position: relative;
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--bg-input);
  border: 1px solid var(--border-light);
  border-radius: 10px;
  padding: 4px 6px 4px 10px;
}

.slash-menu {
  position: absolute;
  bottom: 100%;
  left: 0;
  right: 0;
  margin-bottom: 6px;
  background: var(--bg-panel);
  border: 1px solid var(--border-light);
  border-radius: 8px;
  box-shadow: 0 -4px 16px rgba(0, 0, 0, 0.3);
  padding: 4px;
  animation: slide-up 0.15s ease;
}

@keyframes slide-up {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

.slash-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 6px 10px;
  border-radius: 4px;
  font-size: 12px;
  text-align: left;
}

.slash-item:hover {
  background: var(--bg-hover);
}

.slash-name {
  color: var(--accent);
  font-weight: 500;
}

.slash-desc {
  color: var(--text-muted);
  font-size: 11px;
}

.bubble-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 13px;
  color: var(--text-primary);
  outline: none;
  min-width: 0;
}

.bubble-input::placeholder {
  color: var(--text-muted);
}

.composer-actions {
  flex-shrink: 0;
}

.action-btn {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
}

.action-btn.send {
  background: var(--accent);
  color: white;
}

.action-btn.send:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.action-btn.send:not(:disabled):hover {
  background: var(--accent-hover);
}
</style>
