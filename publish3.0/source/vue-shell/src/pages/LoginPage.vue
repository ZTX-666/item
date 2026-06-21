<template>
  <section class="card">
    <h2>登录配对</h2>
    <p>通过 Local API 调用原 C# 的 wacli 登录能力。</p>

    <div class="row">
      <button class="primary" @click="onQrStart">二维码登录</button>
      <input v-model="phone" placeholder="+8613800138000" />
      <button @click="onPhoneStart">手机号登录</button>
      <button @click="onStop">停止</button>
    </div>

    <p v-if="pairingCode">配对码：<strong>{{ pairingCode }}</strong></p>

    <div class="qr" v-if="qrSrc">
      <img :src="qrSrc" alt="QR Code" />
    </div>
  </section>

  <section class="card">
    <h3>认证日志</h3>
    <div class="log">{{ logs.join('\n') || '等待事件…' }}</div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import {
  qrPngBase64,
  startPhoneAuth,
  startQrAuth,
  stopAuth,
  subscribeAuthEvents,
} from '../api/wacli'

const phone = ref('')
const pairingCode = ref('')
const qrSrc = ref('')
const logs = ref<string[]>([])
let unsubscribe: (() => void) | null = null

function pushLog(line: string) {
  logs.value = [...logs.value.slice(-200), line]
}

async function showQr(payload: string) {
  const res = await qrPngBase64(payload)
  if (res.ok && res.pngBase64) {
    qrSrc.value = `data:image/png;base64,${res.pngBase64}`
  }
}

onMounted(() => {
  unsubscribe = subscribeAuthEvents({
    onLog: pushLog,
    onQr: (payload) => { void showQr(payload) },
    onPairing: (code) => { pairingCode.value = code },
    onAuthState: (state) => pushLog(`[auth_state] ${state}`),
  })
})

onUnmounted(() => unsubscribe?.())

async function onQrStart() {
  pairingCode.value = ''
  qrSrc.value = ''
  logs.value = []
  const res = await startQrAuth()
  if (!res.ok) pushLog(res.error ?? '启动失败')
}

async function onPhoneStart() {
  pairingCode.value = '等待…'
  qrSrc.value = ''
  logs.value = []
  const res = await startPhoneAuth(phone.value)
  if (!res.ok) pushLog(res.error ?? '启动失败')
}

async function onStop() {
  await stopAuth()
  pushLog('已停止认证')
}
</script>
