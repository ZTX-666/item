<script setup lang="ts">
import { BubbleMenu } from '@tiptap/vue-3'
import type { Editor } from '@tiptap/vue-3'

const props = defineProps<{
  editor: Editor | undefined
  reviewing: boolean
  regenerating?: boolean
  getDiffAnchorRect: () => DOMRect | null
  regenerateCount: number
  maxRegenerate: number
}>()

const emit = defineEmits<{
  accept: []
  reject: []
  regenerate: []
}>()

function shouldShow() {
  return props.reviewing
}

function tippyOptions() {
  return {
    duration: 80,
    placement: 'bottom' as const,
    interactive: true,
    appendTo: () => document.body,
    getReferenceClientRect: () => props.getDiffAnchorRect() ?? new DOMRect(0, 0, 0, 0),
  }
}
</script>

<template>
  <BubbleMenu
    v-if="editor && reviewing"
    :editor="editor"
    :should-show="shouldShow"
    :tippy-options="tippyOptions()"
    class="inline-diff-menu"
  >
    <div class="diff-actions">
      <button class="btn-accept" type="button" title="Ctrl+Enter" @mousedown.stop @click.stop="emit('accept')">
        采纳 ✓ <kbd>Ctrl+↵</kbd>
      </button>
      <button class="btn-reject" type="button" title="Esc" @mousedown.stop @click.stop="emit('reject')">
        拒绝 ✗ <kbd>Esc</kbd>
      </button>
      <button
        class="btn-regen-icon"
        type="button"
        :disabled="regenerateCount >= maxRegenerate || regenerating"
        :title="regenerateCount >= maxRegenerate ? `最多 ${maxRegenerate} 次` : '重新生成 (温度递增)'"
        @mousedown.stop
        @click.stop="emit('regenerate')"
      >
        <span v-if="regenerating" class="regen-spinner" />
        <span v-else>🔄</span>
      </button>
    </div>
  </BubbleMenu>
</template>

<style scoped>
.diff-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: var(--bg-base);
  border: 1px solid var(--border-light);
  border-radius: 10px;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4);
}

.btn-accept {
  padding: 5px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
  background: var(--green);
  color: #1e1e1e;
}

.btn-reject {
  padding: 5px 10px;
  border-radius: 6px;
  font-size: 12px;
  background: var(--bg-hover);
  color: var(--text-muted);
}

.btn-regen-icon {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  font-size: 13px;
  background: var(--bg-hover);
  color: var(--text-secondary);
  padding: 0;
  margin-left: 2px;
}

.btn-regen-icon:hover:not(:disabled) {
  background: var(--accent-muted);
  color: var(--accent);
}

.btn-regen-icon:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.regen-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid var(--border-light);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

kbd {
  font-size: 10px;
  opacity: 0.8;
  margin-left: 2px;
}
</style>
