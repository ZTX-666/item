<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{
  submit: [payload: { message: string; area: string }]
}>()

const message = ref('')

function submit() {
  const trimmed = message.value.trim()
  if (!trimmed) return
  emit('submit', { message: trimmed, area: 'all' })
  message.value = ''
}
</script>

<template>
  <form class="command-bar" @submit.prevent="submit">
    <div class="command-bar__mark">快捷指令</div>
    <input
      v-model="message"
      class="command-bar__input"
      placeholder="输入指令，例如：检查 B2 摄像头 / 生成今日简报 / 帮我填 T006"
    />
    <button class="command-bar__submit" type="submit">执行</button>
  </form>
</template>
