<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import QRCode from 'qrcode'
import {
  getWhatsAppAgentListenerStatus,
  getWhatsAppAuthStatus,
  getWhatsAppGroups,
  ingestWhatsAppSearch,
  logoutWhatsAppAuth,
  refreshWhatsAppGroups,
  searchWhatsAppMessages,
  sendWhatsAppText,
  startWhatsAppAgentListener,
  startWhatsAppAuth,
  stopWhatsAppAgentListener,
  stopWhatsAppAuth,
} from '../services/chitungApi'

const query = ref('整改')
const loading = ref(false)
const ingesting = ref(false)
const sending = ref(false)
const authLoading = ref(false)
const groups = ref<Array<Record<string, unknown>>>([])
const rows = ref<Array<Record<string, unknown>>>([])
const errorText = ref('')
const hkPhone = ref('')
const qrDataUrl = ref('')
const authStatus = ref<Record<string, unknown> | null>(null)
const authTimer = ref<number | null>(null)
const agentLoading = ref(false)
const agentStatus = ref<Record<string, unknown> | null>(null)
const agentTimer = ref<number | null>(null)
const sendChat = ref('安全管理群')
const sendText = ref('【赤瞳安全智能平台】这是一条 WhatsApp 发送链路测试消息。')
const lastSend = ref<Record<string, unknown> | null>(null)
const lastIngest = ref<Record<string, unknown> | null>(null)

function toolData(resp: Record<string, unknown>): Record<string, unknown> {
  return (resp.data && typeof resp.data === 'object' ? resp.data : {}) as Record<string, unknown>
}

function normalizeGroup(group: Record<string, unknown>): Record<string, unknown> {
  return {
    ...group,
    id: group.id ?? group.JID ?? group.jid,
    name: group.name ?? group.Name ?? group.subject ?? group.id ?? group.JID,
  }
}

function selectGroup(group: Record<string, unknown>) {
  sendChat.value = String(group.id ?? group.JID ?? group.name ?? group.Name ?? '')
}

async function renderQr(payload: unknown) {
  const text = typeof payload === 'string' ? payload : ''
  qrDataUrl.value = text ? await QRCode.toDataURL(text, { width: 240, margin: 1 }) : ''
}

async function pollAuth() {
  try {
    const resp = await getWhatsAppAuthStatus(true)
    authStatus.value = toolData(resp)
    await renderQr(authStatus.value.qr_payload)
  } catch (error) {
    errorText.value = `登录状态读取失败：${error instanceof Error ? error.message : String(error)}`
  }
}

function startAuthPoller() {
  if (authTimer.value) window.clearInterval(authTimer.value)
  authTimer.value = window.setInterval(() => void pollAuth(), 2000)
}

async function pollAgent() {
  try {
    const resp = await getWhatsAppAgentListenerStatus(true)
    agentStatus.value = toolData(resp)
  } catch (error) {
    errorText.value = `Agent 监听状态读取失败：${error instanceof Error ? error.message : String(error)}`
  }
}

function startAgentPoller() {
  if (agentTimer.value) window.clearInterval(agentTimer.value)
  agentTimer.value = window.setInterval(() => void pollAgent(), 3000)
}

async function startAgentListener() {
  agentLoading.value = true
  errorText.value = ''
  try {
    agentStatus.value = toolData(await startWhatsAppAgentListener())
    startAgentPoller()
  } catch (error) {
    errorText.value = `启动 Agent 监听失败：${error instanceof Error ? error.message : String(error)}`
  } finally {
    agentLoading.value = false
  }
}

async function stopAgentListener() {
  agentLoading.value = true
  errorText.value = ''
  try {
    agentStatus.value = toolData(await stopWhatsAppAgentListener())
  } catch (error) {
    errorText.value = `停止 Agent 监听失败：${error instanceof Error ? error.message : String(error)}`
  } finally {
    agentLoading.value = false
  }
}

async function startQrLogin(mode: 'qr' | 'phone') {
  authLoading.value = true
  errorText.value = ''
  try {
    const resp = await startWhatsAppAuth({ phone: hkPhone.value || undefined, mode })
    if (resp.ok === false) {
      errorText.value = String(resp.summary || resp.error || 'WhatsApp 登录启动失败')
      authStatus.value = toolData(resp)
      return
    }
    authStatus.value = toolData(resp)
    await renderQr(authStatus.value.qr_payload)
    startAuthPoller()
  } catch (error) {
    errorText.value = `启动 WhatsApp 登录失败：${error instanceof Error ? error.message : String(error)}`
  } finally {
    authLoading.value = false
  }
}

async function stopLogin() {
  if (authTimer.value) window.clearInterval(authTimer.value)
  authTimer.value = null
  await stopWhatsAppAuth('user_stop')
  await pollAuth()
}

async function logoutLogin() {
  const ok = window.confirm('确认退出当前 WhatsApp 登录？退出后需要重新扫码或配对。')
  if (!ok) return
  if (authTimer.value) window.clearInterval(authTimer.value)
  authTimer.value = null
  authStatus.value = toolData(await logoutWhatsAppAuth(true))
}

async function loadGroups() {
  try {
    const resp = await getWhatsAppGroups()
    const data = (resp as { data?: { items?: Array<Record<string, unknown>> } }).data
    groups.value = (data?.items ?? []).map(normalizeGroup)
  } catch (error) {
    errorText.value = `群组读取失败：${error instanceof Error ? error.message : String(error)}`
  }
}

async function refreshGroups() {
  loading.value = true
  errorText.value = ''
  try {
    const resp = await refreshWhatsAppGroups()
    const data = (resp as { data?: { groups?: Array<Record<string, unknown>> } }).data
    groups.value = (data?.groups ?? []).map(normalizeGroup)
  } catch (error) {
    errorText.value = `群组刷新失败：${error instanceof Error ? error.message : String(error)}`
  } finally {
    loading.value = false
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

async function ingestSearch() {
  ingesting.value = true
  errorText.value = ''
  try {
    lastIngest.value = await ingestWhatsAppSearch({ q: query.value, limit: 20, autoRoute: true })
  } catch (error) {
    errorText.value = `转入工作流失败：${error instanceof Error ? error.message : String(error)}`
  } finally {
    ingesting.value = false
  }
}

async function sendDraft() {
  sending.value = true
  errorText.value = ''
  try {
    lastSend.value = await sendWhatsAppText({ chat: sendChat.value, text: sendText.value, confirmed: false, dryRun: true })
  } catch (error) {
    errorText.value = `生成发送草稿失败：${error instanceof Error ? error.message : String(error)}`
  } finally {
    sending.value = false
  }
}

async function sendConfirmed() {
  sending.value = true
  errorText.value = ''
  try {
    lastSend.value = await sendWhatsAppText({ chat: sendChat.value, text: sendText.value, confirmed: true, dryRun: false })
  } catch (error) {
    errorText.value = `确认发送失败：${error instanceof Error ? error.message : String(error)}`
  } finally {
    sending.value = false
  }
}

onMounted(async () => {
  await pollAuth()
  await pollAgent()
  await loadGroups()
  await search()
})

onUnmounted(() => {
  if (authTimer.value) window.clearInterval(authTimer.value)
  if (agentTimer.value) window.clearInterval(agentTimer.value)
})
</script>

<template>
  <main class="whats-page panel">
    <div class="panel__header">
      <div>
        <h2>WhatsApp 双向运维</h2>
        <p>入站：搜索归档消息并转入隐患工作流；出站：人工确认后通过 wacli 发送 WhatsApp 消息。</p>
      </div>
    </div>

    <section class="box login-box">
      <h3>登录配对（二维码 / 香港手机号）</h3>
      <p class="hint">输入香港手机号后可走配对码模式；不输入也可以直接启动二维码登录。扫码/确认后，wacli 会持续同步 WhatsApp 数据。</p>
      <div class="ops-row">
        <input v-model="hkPhone" placeholder="香港手机号，如 91234567 或 +85291234567" />
        <button class="primary-soft-button" :disabled="authLoading" @click="startQrLogin('qr')">生成二维码</button>
        <button class="secondary-button" :disabled="authLoading || !hkPhone" @click="startQrLogin('phone')">手机号配对</button>
        <button class="ghost-button" @click="stopLogin">停止</button>
        <button class="danger-button" @click="logoutLogin">退出登录</button>
      </div>
      <div class="login-grid">
        <div class="qr-card">
          <img v-if="qrDataUrl" :src="qrDataUrl" alt="WhatsApp login QR" />
          <div v-else class="qr-placeholder">等待二维码 payload</div>
        </div>
        <div>
          <p><strong>状态：</strong>{{ authStatus?.status || 'idle' }}</p>
          <p><strong>配对码：</strong><span class="pair-code">{{ authStatus?.pairing_code || '—' }}</span></p>
          <p><strong>手机号：</strong>{{ authStatus?.phone || '—' }}</p>
          <details>
            <summary>登录日志</summary>
            <pre>{{ JSON.stringify(authStatus?.logs || [], null, 2) }}</pre>
          </details>
        </div>
      </div>
    </section>

    <section class="box agent-box">
      <h3>Agent 监听（触发词自动回复）</h3>
      <p class="hint">默认只响应包含 @赤瞳、#赤瞳、/ai、问赤瞳、赤瞳： 的新消息；普通群消息只同步入库，不自动刷屏。</p>
      <div class="ops-row">
        <button class="primary-soft-button" :disabled="agentLoading" @click="startAgentListener">
          {{ agentLoading ? '处理中...' : '启动 Agent 监听' }}
        </button>
        <button class="secondary-button" :disabled="agentLoading" @click="stopAgentListener">停止 Agent 监听</button>
        <button class="secondary-button" :disabled="agentLoading" @click="pollAgent">刷新状态</button>
      </div>
      <p><strong>监听状态：</strong>{{ agentStatus?.status || 'idle' }}</p>
      <p><strong>已同步消息：</strong>{{ agentStatus?.messages_synced ?? 0 }}</p>
      <details>
        <summary>监听日志</summary>
        <pre>{{ JSON.stringify(agentStatus?.logs || [], null, 2) }}</pre>
      </details>
    </section>

    <div class="ops-row">
      <input v-model="query" placeholder="输入关键词，如：整改 / 发票 / 吊运" @keydown.enter="search" />
      <button class="primary-soft-button" :disabled="loading" @click="search">{{ loading ? '搜索中...' : '搜索消息' }}</button>
      <button class="secondary-button" :disabled="loading" @click="refreshGroups">刷新群组</button>
      <button class="secondary-button" :disabled="ingesting" @click="ingestSearch">{{ ingesting ? '转入中...' : '转入工作流' }}</button>
    </div>

    <p v-if="errorText" class="err">{{ errorText }}</p>

    <section class="box send-box">
      <h3>出站发送（人工确认）</h3>
      <div class="ops-row">
        <input v-model="sendChat" placeholder="WhatsApp 群组/Chat ID" />
        <button class="secondary-button" :disabled="sending" @click="sendDraft">生成草稿</button>
        <button class="danger-button" :disabled="sending" @click="sendConfirmed">确认发送</button>
      </div>
      <textarea v-model="sendText" rows="3" placeholder="输入要发送的 WhatsApp 消息" />
      <pre v-if="lastSend">{{ JSON.stringify(lastSend, null, 2) }}</pre>
    </section>

    <section class="split">
      <article class="box">
        <h3>群组（{{ groups.length }}）</h3>
        <ul>
          <li v-for="group in groups" :key="String(group.id || Math.random())" @click="selectGroup(group)">
            {{ group.name || group.id || '未命名群组' }}
          </li>
        </ul>
      </article>
      <article class="box">
        <h3>消息结果（{{ rows.length }}）</h3>
        <pre v-if="lastIngest">转入结果：{{ JSON.stringify(lastIngest, null, 2) }}</pre>
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
.ops-row { display: flex; gap: 8px; margin-bottom: 10px; align-items: stretch; }
input, textarea {
  border: 1px solid var(--border-normal);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  outline: none;
  padding: 9px 11px;
  transition: border-color var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease);
}
input { flex: 1; }
textarea { width: 100%; resize: vertical; line-height: 1.6; }
input:focus, textarea:focus { border-color: var(--brand-cyan); box-shadow: var(--ring); }
.send-box { margin-bottom: 12px; }
.login-box { margin-bottom: 12px; min-height: auto; }
.box h3 { font-size: 14px; font-weight: 700; color: var(--text-primary); margin: 0 0 4px; }
.hint { color: var(--text-secondary); font-size: 13px; margin: 0 0 10px; }
.login-grid { display: grid; grid-template-columns: 280px 1fr; gap: 14px; align-items: start; }
.login-grid p { margin: 0 0 6px; color: var(--text-primary); }
.qr-card { display: grid; place-items: center; min-height: 260px; background: var(--bg-subtle); border: 1.5px dashed var(--border-strong); border-radius: var(--radius-lg); }
.qr-card img { width: 240px; height: 240px; border-radius: var(--radius-sm); }
.qr-placeholder { color: var(--text-muted); font-size: 13px; }
.pair-code { font-family: var(--font-mono); font-size: 24px; font-weight: 700; color: var(--brand-red); letter-spacing: 1px; }
.split { display: grid; grid-template-columns: 1fr 2fr; gap: 12px; }
.box { border: 1px solid var(--border-light); border-radius: var(--radius-lg); padding: 14px; min-height: 360px; background: var(--bg-white); }
.box ul { margin: 8px 0 0; padding: 0; list-style: none; }
.box li { cursor: pointer; margin-bottom: 4px; padding: 6px 8px; border-radius: var(--radius-sm); transition: background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease); }
.box li:hover { background: var(--bg-hover); color: var(--brand-red); }
.err { color: var(--brand-red); font-size: 13px; margin-bottom: 10px; }
details summary { color: var(--text-secondary); cursor: pointer; font-size: 12px; }
pre { white-space: pre-wrap; background: var(--bg-subtle); border: 1px solid var(--border-light); border-radius: var(--radius-md); color: var(--text-secondary); padding: 10px; max-height: 220px; overflow: auto; font-family: var(--font-mono); font-size: 12px; }
.danger-button { background: linear-gradient(135deg, #ef2034, var(--brand-red-dark)); border: 0; box-shadow: 0 2px 8px rgb(231 0 18 / 22%); color: #fff; }
.danger-button:hover:not(:disabled) { box-shadow: 0 4px 14px rgb(231 0 18 / 32%); transform: translateY(-1px); }
@media (max-width: 900px) { .split { grid-template-columns: 1fr; } }
</style>
