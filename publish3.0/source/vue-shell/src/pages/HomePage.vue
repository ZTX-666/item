<template>
  <section class="card">
    <h2>系统状态</h2>
    <p v-if="loading">加载中…</p>
    <p v-else-if="error" class="status-bad">{{ error }}</p>
    <template v-else-if="status">
      <p>
        登录状态：
        <strong :class="status.authenticated ? 'status-ok' : 'status-bad'">
          {{ status.authStatusText }}
        </strong>
      </p>
      <p>同步：{{ status.syncRunning ? '运行中' : '已停止' }}</p>
      <p>{{ status.mediaProgressText }}</p>
      <p>当前手机号：{{ status.currentPhone || '—' }}</p>
      <p>wacli：{{ status.wacliExeExists ? '已安装' : '未安装（请在 WPF 中配置环境）' }}</p>
      <div class="row">
        <button class="primary" @click="refresh">刷新</button>
        <button @click="startSync" :disabled="!status.wacliExeExists">启动同步</button>
        <button @click="stopSync">停止同步</button>
      </div>
    </template>
  </section>

  <section class="card" v-if="status">
    <h3>详情</h3>
    <pre>{{ status.statusDetail }}</pre>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getStatus, startSync as apiStartSync, stopSync as apiStopSync, type AppStatus } from '../api/wacli'

const status = ref<AppStatus | null>(null)
const loading = ref(true)
const error = ref('')

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    status.value = await getStatus()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

async function startSync() {
  await apiStartSync()
  await refresh()
}

async function stopSync() {
  await apiStopSync()
  await refresh()
}

onMounted(refresh)
</script>
