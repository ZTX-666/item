<script setup lang="ts">
import type { HazardCase } from '../../types/domain'

defineProps<{
  hazards: HazardCase[]
}>()

const emit = defineEmits<{
  confirm: [caseId: string]
  workflow: [action: 'rectification-notice' | 'contractor-confirm' | 'close-review', caseId: string]
  viewAll: []
}>()
</script>

<template>
  <section class="panel">
    <div class="panel__header">
      <div>
        <h2>活跃隐患</h2>
        <p>优先处理超期和高风险事项</p>
      </div>
      <button class="link-button" @click="emit('viewAll')">查看全部</button>
    </div>

    <div class="hazard-list">
      <article v-for="hazard in hazards" :key="hazard.id" class="hazard-row">
        <span class="hazard-row__bar" :class="`hazard-row__bar--${hazard.riskLevel}`" />
        <div class="hazard-row__main">
          <strong>{{ hazard.title }}</strong>
          <span>{{ hazard.id }} · {{ hazard.area }}</span>
        </div>
        <span class="tag" :class="`tag--${hazard.riskLevel}`">{{ hazard.status }}</span>
        <span class="hazard-row__due">{{ hazard.dueText }}</span>
        <button class="mini-button" @click="emit('confirm', hazard.id)">确认</button>
        <button class="mini-button" @click="emit('workflow', 'rectification-notice', hazard.id)">通知</button>
        <button class="mini-button" @click="emit('workflow', 'contractor-confirm', hazard.id)">分包</button>
        <button class="mini-button" @click="emit('workflow', 'close-review', hazard.id)">关闭</button>
      </article>
    </div>
  </section>
</template>
