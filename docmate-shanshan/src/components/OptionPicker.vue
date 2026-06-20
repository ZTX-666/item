<script setup lang="ts">
import { computed } from 'vue'
import type { RevisionProposal } from '@/types'

const props = defineProps<{
  proposal: RevisionProposal
  reviewing?: boolean
  active?: boolean
}>()

const emit = defineEmits<{
  apply: [proposalId: string]
  reject: [proposalId: string]
  preview: [proposalId: string]
}>()

const option = computed(() => props.proposal.options[0])
const newText = computed(() => option.value?.text ?? '')
const oldText = computed(() => props.proposal.oldText?.trim() ?? '')
const operation = computed(() => props.proposal.operation || inferOperation())

function inferOperation(): RevisionProposal['operation'] {
  if (!oldText.value && newText.value) return 'insert'
  if (oldText.value && !newText.value.trim()) return 'delete'
  return 'replace'
}

const opLabel = computed(() => {
  if (operation.value === 'insert') return '新增'
  if (operation.value === 'delete') return '删除'
  return '修改'
})

const isPending = computed(() => props.proposal.status === 'pending')
const isSynced = computed(() => props.active && props.reviewing && isPending.value)

function handleApply() {
  if (!isPending.value) return
  emit('apply', props.proposal.id)
}

function handlePreview() {
  emit('preview', props.proposal.id)
}
</script>

<template>
  <div class="chat-diff" :class="[proposal.status, { synced: isSynced }]">
    <button
      type="button"
      class="diff-box"
      :title="isPending ? '点击同步到文档' : '点击定位'"
      @click="handlePreview"
    >
      <div class="diff-head">
        <span class="op-tag">{{ opLabel }}</span>
        <span v-if="isSynced" class="sync-tag">↗ 文档已同步</span>
        <span v-else-if="isPending" class="sync-hint">点击预览</span>
      </div>
      <div v-if="oldText" class="diff-old">{{ oldText }}</div>
      <div v-if="operation !== 'delete'" class="diff-new">
        {{ newText || '（空）' }}
      </div>
      <div v-else class="diff-new delete-hint">（删除以上内容）</div>
    </button>

    <div v-if="isPending" class="action-row">
      <button class="btn-accept" type="button" @mousedown.stop @click.stop="handleApply">
        Apply
      </button>
      <button class="btn-reject" type="button" @mousedown.stop @click.stop="emit('reject', proposal.id)">
        拒绝
      </button>
    </div>

    <div v-else class="diff-done" :class="proposal.status">
      {{ proposal.status === 'accepted' ? '✓ 已应用' : '✗ 已拒绝' }}
    </div>
  </div>
</template>

<style scoped>
.chat-diff {
  margin-top: 6px;
}

.chat-diff.accepted,
.chat-diff.rejected {
  opacity: 0.88;
}

.diff-box {
  width: 100%;
  text-align: left;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  overflow: hidden;
  background: var(--bg-base);
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.diff-box:hover {
  border-color: var(--accent);
}

.chat-diff.synced .diff-box {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px rgba(0, 122, 204, 0.25);
}

.diff-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  background: var(--bg-hover);
  border-bottom: 1px solid var(--border);
}

.op-tag {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-secondary);
}

.sync-tag {
  font-size: 10px;
  color: var(--accent);
}

.sync-hint {
  font-size: 10px;
  color: var(--text-muted);
  margin-left: auto;
}

.diff-old {
  padding: 8px 10px;
  background: rgba(241, 76, 76, 0.12);
  font-size: 12px;
  line-height: 1.55;
  color: var(--red);
  text-decoration: line-through;
  word-break: break-word;
  max-height: 96px;
  overflow: auto;
}

.diff-new {
  padding: 8px 10px;
  background: rgba(78, 201, 176, 0.12);
  font-size: 12px;
  line-height: 1.55;
  color: var(--green);
  word-break: break-word;
  max-height: 120px;
  overflow: auto;
}

.diff-new.delete-hint {
  color: var(--text-muted);
  font-style: italic;
}

.action-row {
  display: flex;
  gap: 6px;
  margin-top: 6px;
}

.btn-accept,
.btn-reject {
  flex: 1;
  padding: 6px 0;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
}

.btn-accept {
  background: var(--green);
  color: #1e1e1e;
}

.btn-reject {
  background: var(--bg-hover);
  color: var(--text-muted);
  border: 1px solid var(--border-light);
}

.diff-done {
  margin-top: 4px;
  font-size: 11px;
  padding: 0 2px;
}

.diff-done.accepted {
  color: var(--green);
}

.diff-done.rejected {
  color: var(--text-muted);
}
</style>
