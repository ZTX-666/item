<script setup lang="ts">
import { ref } from 'vue'
import { sendChatMessage } from '../services/chitungApi'

const input = ref('')
const loading = ref(false)
const messages = ref<Array<{ role: 'user' | 'assistant'; text: string }>>([
  { role: 'assistant', text: '你好，我是赤瞳助手。你可以让我生成风险简报、隐患流程或表格草稿。' },
])

async function submit() {
  const text = input.value.trim()
  if (!text || loading.value) return
  messages.value.push({ role: 'user', text })
  input.value = ''
  loading.value = true
  try {
    const resp = await sendChatMessage({ message: text, channel: 'local_chat' })
    messages.value.push({ role: 'assistant', text: resp.message })
  } catch (error) {
    messages.value.push({ role: 'assistant', text: `请求失败：${error instanceof Error ? error.message : String(error)}` })
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="assistant-page panel">
    <div class="panel__header">
      <div>
        <h2>AI 对话助手</h2>
        <p>已对齐中台 `/api/chat/message`，可用于日常任务编排。</p>
      </div>
    </div>
    <div class="chat-area">
      <article v-for="(msg, idx) in messages" :key="idx" class="msg" :class="`msg--${msg.role}`">
        {{ msg.text }}
      </article>
    </div>
    <div class="chat-input">
      <textarea v-model="input" rows="3" placeholder="输入：例如“请生成今天外部风险简报”" />
      <button class="primary-soft-button" :disabled="loading" @click="submit">{{ loading ? '发送中...' : '发送' }}</button>
    </div>
  </main>
</template>

<style scoped>
.assistant-page { height: calc(100vh - 110px); display: flex; flex-direction: column; }
.chat-area { flex: 1; overflow: auto; display: flex; flex-direction: column; gap: 10px; padding: 8px 0; }
.msg { padding: 10px 12px; border-radius: 10px; max-width: 80%; line-height: 1.5; }
.msg--assistant { background: #f4f7fb; border: 1px solid #e3e8f0; }
.msg--user { background: #0e2841; color: #fff; align-self: flex-end; }
.chat-input { display: grid; gap: 8px; }
textarea { width: 100%; resize: vertical; border: 1px solid #d9dee7; border-radius: 8px; padding: 10px; }
</style>
