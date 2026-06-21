<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{
  submit: [payload: { message: string; area: string }]
}>()

const message = ref('')
const selectedArea = ref('B2')

function submit() {
  const trimmed = message.value.trim()
  if (!trimmed) return
  emit('submit', { message: trimmed, area: selectedArea.value })
  message.value = ''
}
</script>

<template>
  <form class="command-bar" @submit.prevent="submit">
    <div class="command-bar__mark">AI</div>
    <select v-model="selectedArea" class="command-bar__context" aria-label="当前区域">
      <option value="B2">B2 区</option>
      <option value="A3">A3 区</option>
      <option value="all">全项目</option>
    </select>
    <input
      v-model="message"
      class="command-bar__input"
      placeholder="输入指令，例如：检查 B2 摄像头 / 生成今日简报 / 帮我填 T006"
    />
    <button class="command-bar__submit" type="submit">Go</button>
  </form>
</template>
