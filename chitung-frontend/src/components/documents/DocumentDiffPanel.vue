<script setup lang="ts">
import type { DocumentRevisionPreview } from '../../types/domain'

defineProps<{
  revision: DocumentRevisionPreview
}>()

const emit = defineEmits<{
  accept: []
  reject: []
  regenerate: []
}>()
</script>

<template>
  <section class="panel document-diff-panel">
    <div class="panel__header">
      <div>
        <h2>AI 文档改写预览</h2>
        <p>{{ revision.title }} · {{ revision.source }}</p>
      </div>
      <div class="diff-stat-group" aria-label="文档修改统计">
        <span class="diff-stat diff-stat--add">+{{ revision.additions }}</span>
        <span class="diff-stat diff-stat--remove">-{{ revision.deletions }}</span>
      </div>
    </div>

    <div class="diff-instruction">
      <span>指令</span>
      <strong>{{ revision.instruction }}</strong>
    </div>

    <div class="document-diff" aria-label="AI 文档改写差异">
      <p
        v-for="line in revision.lines"
        :key="line.id"
        class="document-diff__line"
        :class="`document-diff__line--${line.type}`"
      >
        <span class="document-diff__marker">
          {{ line.type === 'added' ? '+' : line.type === 'removed' ? '-' : ' ' }}
        </span>
        <span>{{ line.text }}</span>
      </p>
    </div>

    <div class="diff-actions-bar">
      <span class="diff-status" :class="`diff-status--${revision.status}`">
        {{ revision.status === 'accepted' ? '已采纳' : revision.status === 'rejected' ? '已拒绝' : '待人工确认' }}
      </span>
      <button class="mini-button" type="button" @click="emit('regenerate')">重新生成</button>
      <button class="mini-button" type="button" @click="emit('reject')">拒绝</button>
      <button class="primary-soft-button" type="button" @click="emit('accept')">采纳修改</button>
    </div>
  </section>
</template>
