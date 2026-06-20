<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getWhatsAppGroups, searchWhatsAppMessages } from '../services/chitungApi'

const query = ref('整改')
const loading = ref(false)
const groups = ref<Array<Record<string, unknown>>>([])
const rows = ref<Array<Record<string, unknown>>>([])
const errorText = ref('')

async function loadGroups() {
  try {
    const resp = await getWhatsAppGroups()
    const data = (resp as { data?: { items?: Array<Record<string, unknown>> } }).data
    groups.value = data?.items ?? []
  } catch (error) {
    errorText.value = `群组读取失败：${error instanceof Error ? error.message : String(error)}`
  }
}

async function search() {
  loading.value = true
  errorText.value = ''
  try {
    const resp = await searchWhatsAppMessages({ q: query.value, limit: 20 })
    const data = (resp as { data?: { rows?: Array<Record<string, unknown>> } }).data
    rows.value = data?.rows ?? []
  } catch (error) {
    errorText.value = `搜索失败：${error instanceof Error ? error.message : String(error)}`
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadGroups()
  await search()
})
</script>

<template>
  <main class="whats-page panel">
    <div class="panel__header">
      <div>
        <h2>WhatsApp 消息管理</h2>
        <p>已对齐中台 `/api/whatsapp/groups` 与 `/api/whatsapp/search`。</p>
      </div>
    </div>

    <div class="ops-row">
      <input v-model="query" placeholder="输入关键词，如：整改 / 发票 / 吊运" @keydown.enter="search" />
      <button class="primary-soft-button" :disabled="loading" @click="search">{{ loading ? '搜索中...' : '搜索消息' }}</button>
    </div>

    <p v-if="errorText" class="err">{{ errorText }}</p>

    <section class="split">
      <article class="box">
        <h3>群组（{{ groups.length }}）</h3>
        <ul>
          <li v-for="group in groups" :key="String(group.id || Math.random())">
            {{ group.name || group.id || '未命名群组' }}
          </li>
        </ul>
      </article>
      <article class="box">
        <h3>消息结果（{{ rows.length }}）</h3>
        <ul>
          <li v-for="row in rows" :key="String(row.message_id || row.id || Math.random())">
            <strong>{{ row.chat_name || row.chat_id || 'chat' }}：</strong>{{ row.text || row.content || '(无文本)' }}
          </li>
        </ul>
      </article>
    </section>
  </main>
</template>

<style scoped>
.whats-page { min-height: calc(100vh - 110px); }
.ops-row { display: flex; gap: 8px; margin-bottom: 10px; }
input { flex: 1; border: 1px solid #d9dee7; border-radius: 8px; padding: 10px; }
.split { display: grid; grid-template-columns: 1fr 2fr; gap: 12px; }
.box { border: 1px solid #e3e8f0; border-radius: 10px; padding: 10px; min-height: 360px; }
.box ul { margin: 8px 0 0 18px; }
.err { color: #c91b1b; margin-bottom: 10px; }
@media (max-width: 900px) { .split { grid-template-columns: 1fr; } }
</style>
