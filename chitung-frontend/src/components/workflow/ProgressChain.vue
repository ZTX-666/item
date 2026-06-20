<script setup lang="ts">
import type { WorkflowStep } from '../../types/domain'

defineProps<{
  steps: WorkflowStep[]
}>()
</script>

<template>
  <div class="progress-chain" aria-label="工具执行进度">
    <template v-for="(step, index) in steps" :key="step.id">
      <div class="progress-step" :class="`progress-step--${step.status}`">
        <span class="progress-step__circle">
          {{ step.status === 'done' ? '✓' : index + 1 }}
        </span>
        <span class="progress-step__label">{{ step.label }}</span>
      </div>
      <span v-if="index < steps.length - 1" class="progress-step__connector" :class="{ 'progress-step__connector--done': step.status === 'done' }" />
    </template>
  </div>
</template>
