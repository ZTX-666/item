<script setup lang="ts">
import { watch, onBeforeUnmount, onMounted, computed } from 'vue'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import { DiffDeletion, DiffInsertion } from '@/extensions/DiffHighlight'
import { StickySelectionHighlight } from '@/extensions/StickySelectionHighlight'
import { Underline } from '@/extensions/Underline'
import { useEditorAi } from '@/composables/useEditorAi'
import type { RevisionResult } from '@/types'
import AiBubbleMenu from './AiBubbleMenu.vue'
import InlineDiffMenu from './InlineDiffMenu.vue'

const MAX_REGENERATE = 3

const props = defineProps<{
  content: string
  fileName: string
  agentBusy?: boolean
}>()

const emit = defineEmits<{
  update: [html: string]
  toast: [message: string, type?: 'success' | 'info' | 'error']
  reviewChange: [reviewing: boolean]
  historyChange: []
  regenerateStart: []
  regenerateEnd: [payload: { ok: boolean; error?: string; revision?: RevisionResult }]
  aiStateChange: [state: string]
  thinkingLogChange: [log: string]
  agentCommand: [command: string]
}>()

let isUpdatingFromProp = false
let suppressFileSync = false

const editor = useEditor({
  extensions: [
    StarterKit,
    Placeholder.configure({
      placeholder: '选中要修改的文字，上方会出现操作条 — 直接说话或输入指令…',
    }),
    StickySelectionHighlight,
    Underline,
    DiffDeletion,
    DiffInsertion,
  ],
  content: props.content,
  editorProps: {
    attributes: { class: 'prose-editor' },
    handleDOMEvents: {
      mouseup: () => {
        onEditorMouseUp()
        return false
      },
    },
    handleClick: (_view, pos) => {
      onEditorClick(pos)
      return false
    },
  },
  onBlur: () => {
    onEditorBlur()
  },
  onUpdate: ({ editor: ed }) => {
    onDocumentUpdate()
    if (!isUpdatingFromProp && !suppressFileSync) {
      emit('update', ed.getHTML())
    }
  },
  onSelectionUpdate: () => {
    onSelectionUpdate()
  },
})

const {
  aiState,
  revisionHistory,
  regenerateCount,
  regenerating,
  thinkingLog,
  lockSelection,
  getLockedRect,
  getDiffAnchorRect,
  getLockedText,
  acceptReview,
  applyRevisionResult,
  rejectReview,
  regenerateCommand,
  cancelThinking,
  showReviewFromResult,
  captureSelectionAnchor,
  onSelectionUpdate,
  onDocumentUpdate,
  onEditorMouseUp,
  onEditorClick,
  onEditorBlur,
  getFullText,
  locateText,
} = useEditorAi(editor)

const reviewing = computed(() => aiState.value === 'reviewing')
const formatDisabled = computed(() => !editor.value || aiState.value === 'thinking' || reviewing.value)
const docStats = computed(() => {
  const text = editor.value?.getText({ blockSeparator: '\n' }).trim() || ''
  const chars = text.replace(/\s/g, '').length
  const paragraphs = text ? text.split(/\n+/).filter((p) => p.trim()).length : 0
  const readingMinutes = Math.max(1, Math.ceil(chars / 450))
  return { chars, paragraphs, readingMinutes }
})

watch(
  reviewing,
  (value) => {
    emit('reviewChange', value)
  },
  { immediate: true },
)

watch(aiState, (value) => emit('aiStateChange', value), { immediate: true })
watch(thinkingLog, (value) => emit('thinkingLogChange', value))

watch(reviewing, (value) => {
  suppressFileSync = value
})

watch(
  () => aiState.value === 'thinking',
  (value) => {
    if (value) suppressFileSync = true
    else if (!reviewing.value) suppressFileSync = false
  },
)

watch(
  () => props.content,
  (newContent) => {
    if (!editor.value) return
    if (reviewing.value || aiState.value === 'thinking') return
    if (editor.value.getHTML() !== newContent) {
      isUpdatingFromProp = true
      editor.value.commands.setContent(newContent, false)
      isUpdatingFromProp = false
    }
  },
)

async function handleBubbleSubmit(command: string) {
  if (props.agentBusy || aiState.value === 'thinking' || aiState.value === 'reviewing') {
    emit('toast', '当前已有任务进行中，请完成或终止后再开始新任务', 'info')
    return
  }
  captureSelectionAnchor()
  emit('agentCommand', command)
}

function handleRiskScan() {
  if (props.agentBusy || aiState.value === 'thinking' || aiState.value === 'reviewing') {
    emit('toast', '当前已有任务进行中，请完成或终止后再开始新任务', 'info')
    return
  }
  captureSelectionAnchor()
  emit('agentCommand', '风险检查')
}

function handleCancelThinking() {
  cancelThinking()
  emit('toast', '已终止当前任务', 'info')
}

function handleAccept() {
  if (acceptReview()) {
    setTimeout(() => {
      if (editor.value) emit('update', editor.value.getHTML())
      emit('historyChange')
      emit('toast', '已应用修改', 'success')
    }, 400)
  } else {
    emit('toast', '应用失败：选区已失效', 'error')
  }
}

function handleReject() {
  rejectReview()
  setTimeout(() => {
    if (editor.value) emit('update', editor.value.getHTML())
    emit('historyChange')
    emit('toast', '已拒绝，可继续输入指令', 'info')
  }, 320)
}

async function handleRegenerate() {
  if (props.agentBusy) {
    emit('toast', '闪闪正在处理任务，请稍后再重新生成', 'info')
    return
  }
  emit('regenerateStart')
  const result = await regenerateCommand()
  if (result.ok && editor.value) {
    emit('update', editor.value.getHTML())
  }
  emit('regenerateEnd', {
    ok: result.ok,
    error: result.error,
    revision: result.revision,
  })
  if (result.ok) {
    emit('toast', '已重新生成，Ctrl+Enter 采纳或 Esc 拒绝', 'success')
  } else {
    emit('toast', result.error || '重新生成失败', 'error')
  }
}

function isTypingTarget(el: EventTarget | null) {
  if (!(el instanceof HTMLElement)) return false
  const tag = el.tagName
  if (tag === 'TEXTAREA' || tag === 'INPUT' || tag === 'SELECT' || tag === 'BUTTON') return true
  if (el.isContentEditable) return true
  return !!el.closest('.composer-box, .bubble-input')
}

function onGlobalKeydown(e: KeyboardEvent) {
  if (!reviewing.value) return
  if (isTypingTarget(e.target)) return

  if (e.key === 'Escape') {
    e.preventDefault()
    handleReject()
    return
  }

  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
    e.preventDefault()
    handleAccept()
  }
}

function notifyHistoryChange() {
  emit('historyChange')
}

function runFormat(action: 'bold' | 'italic' | 'underline') {
  if (formatDisabled.value || !editor.value) return
  const chain = editor.value.chain().focus()
  if (action === 'bold') chain.toggleBold().run()
  else if (action === 'italic') chain.toggleItalic().run()
  else chain.toggleMark('underline').run()
}

defineExpose({
  getFullText,
  getLockedText,
  getRevisionHistory: () => revisionHistory.value,
  showReviewFromResult,
  captureSelectionAnchor,
  lockSelection,
  locateText,
  regenerateCommand,
  isReviewing: () => reviewing.value,
  applyRevisionResult: (result: RevisionResult, command: string) => {
    if (applyRevisionResult(result, command)) {
      if (editor.value) emit('update', editor.value.getHTML())
      notifyHistoryChange()
      return true
    }
    return false
  },
  acceptReview: () => {
    if (acceptReview()) {
      setTimeout(() => {
        if (editor.value) emit('update', editor.value.getHTML())
        notifyHistoryChange()
      }, 400)
      return true
    }
    return false
  },
  rejectReview: () => {
    rejectReview()
    setTimeout(() => {
      if (editor.value) emit('update', editor.value.getHTML())
      notifyHistoryChange()
    }, 320)
  },
})

onMounted(() => {
  document.addEventListener('keydown', onGlobalKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onGlobalKeydown)
  editor.value?.destroy()
})
</script>

<template>
  <div class="editor-area writing-board" :class="{ thinking: aiState === 'thinking' }">
    <div class="writing-toolbar">
      <div class="toolbar-left">
        <span class="writing-title">{{ fileName }}</span>
        <span class="doc-stats">
          {{ docStats.chars }} 字 · {{ docStats.paragraphs }} 段 · 约 {{ docStats.readingMinutes }} 分钟
        </span>
        <Transition name="status-chip" mode="out-in">
          <span v-if="aiState === 'selected'" key="selected" class="state-chip selected">已选定</span>
          <span v-else-if="aiState === 'thinking'" key="thinking" class="state-chip thinking">AI 生成中…</span>
          <span v-else-if="aiState === 'reviewing'" key="reviewing" class="state-chip reviewing">Ctrl+Enter 采纳 · Esc 拒绝 · 🔄 重新生成</span>
        </Transition>
      </div>
      <div class="toolbar-actions">
        <div class="format-group" aria-label="文本格式">
          <button
            class="toolbar-btn format-btn"
            :class="{ active: editor?.isActive('bold') }"
            title="加粗 Ctrl+B"
            aria-label="加粗"
            :disabled="formatDisabled"
            @click="runFormat('bold')"
          >
            B
          </button>
          <button
            class="toolbar-btn format-btn italic"
            :class="{ active: editor?.isActive('italic') }"
            title="斜体 Ctrl+I"
            aria-label="斜体"
            :disabled="formatDisabled"
            @click="runFormat('italic')"
          >
            I
          </button>
          <button
            class="toolbar-btn format-btn underline"
            :class="{ active: editor?.isActive('underline') }"
            title="下划线 Ctrl+U"
            aria-label="下划线"
            :disabled="formatDisabled"
            @click="runFormat('underline')"
          >
            U
          </button>
        </div>
        <button
          class="toolbar-btn icon-only"
          title="撤销"
          aria-label="撤销"
          :disabled="!editor?.can().undo()"
          @click="editor?.chain().focus().undo().run()"
        >
          <svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.7">
            <path d="M6.5 4H3v3.5" stroke-linecap="round" stroke-linejoin="round" />
            <path d="M3.4 6.7A5 5 0 1 1 5 11.8" stroke-linecap="round" />
          </svg>
        </button>
        <button
          class="toolbar-btn icon-only"
          title="重做"
          aria-label="重做"
          :disabled="!editor?.can().redo()"
          @click="editor?.chain().focus().redo().run()"
        >
          <svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.7">
            <path d="M9.5 4H13v3.5" stroke-linecap="round" stroke-linejoin="round" />
            <path d="M12.6 6.7A5 5 0 1 0 11 11.8" stroke-linecap="round" />
          </svg>
        </button>
      </div>
    </div>

    <div class="editor-body writing-body">
      <EditorContent :editor="editor" />
      <AiBubbleMenu
        :editor="editor"
        :ai-state="aiState"
        :agent-busy="agentBusy"
        :thinking-log="thinkingLog"
        :get-locked-rect="getLockedRect"
        @submit="handleBubbleSubmit"
        @cancel="handleCancelThinking"
        @risk-scan="handleRiskScan"
        @toast="(m, t) => emit('toast', m, t)"
      />
      <InlineDiffMenu
        :editor="editor"
        :reviewing="reviewing"
        :regenerating="regenerating"
        :get-diff-anchor-rect="getDiffAnchorRect"
        :regenerate-count="regenerateCount"
        :max-regenerate="MAX_REGENERATE"
        @accept="handleAccept"
        @reject="handleReject"
        @regenerate="handleRegenerate"
      />
    </div>
  </div>
</template>

<style scoped>
.writing-board {
  background: var(--bg-editor);
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  position: relative;
}

.writing-toolbar {
  height: var(--toolbar-height);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  flex-shrink: 0;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.writing-title {
  font-size: 13px;
  color: var(--text-secondary);
}

.doc-stats {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
}

.state-chip {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
}

.state-chip.selected {
  background: var(--accent-muted);
  color: var(--accent);
}

.state-chip.thinking {
  background: rgba(220, 220, 170, 0.15);
  color: #dcdcaa;
}

.state-chip.reviewing {
  background: rgba(78, 201, 176, 0.15);
  color: var(--green);
}

.status-chip-enter-active { transition: all 0.2s ease; }
.status-chip-leave-active { transition: all 0.15s ease; }
.status-chip-enter-from { opacity: 0; transform: translateY(-4px); }
.status-chip-leave-to { opacity: 0; transform: translateY(4px); }

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.format-group {
  display: flex;
  align-items: center;
  gap: 4px;
  padding-right: 8px;
  margin-right: 2px;
  border-right: 1px solid var(--border);
}

.toolbar-btn {
  border-radius: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}

.toolbar-btn.format-btn {
  width: 28px;
  height: 28px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid transparent;
  background: transparent;
  font-size: 13px;
  font-weight: 700;
}

.toolbar-btn.format-btn.italic {
  font-style: italic;
}

.toolbar-btn.format-btn.underline {
  text-decoration: underline;
}

.toolbar-btn.format-btn.active {
  color: var(--accent);
  background: var(--accent-muted);
  border-color: rgba(0, 122, 204, 0.35);
}

.toolbar-btn.icon-only {
  width: 30px;
  height: 30px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.02);
}

.toolbar-btn:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.toolbar-btn:disabled {
  opacity: 0.35;
}

.writing-body {
  flex: 1;
  overflow-y: auto;
  padding: 40px 10%;
  position: relative;
}
</style>
