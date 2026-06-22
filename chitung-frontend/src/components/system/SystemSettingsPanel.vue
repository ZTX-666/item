<script setup lang="ts">
import { reactive, watch } from 'vue'
import type { ConnectorSettingsStatus, LlmSettingsStatus, RuntimeStatus } from '../../types/domain'

const props = defineProps<{
  health: Record<string, unknown> | null
  llmSettings: LlmSettingsStatus | null
  connectorSettings: ConnectorSettingsStatus | null
  runtimeStatus: RuntimeStatus | null
  logDir?: string | null
  isSaving?: boolean
  isTestingLlm?: boolean
  isSavingConnectors?: boolean
  isRestartingServices?: boolean
}>()

const emit = defineEmits<{
  saveLlm: [payload: { baseUrl: string; apiKey: string; model: string }]
  testLlm: []
  saveConnectors: [payload: {
    whatsappArchiveBaseUrl: string
    feishuWebhookUrl: string
    feishuWebhookSecret: string
    feishuAppId: string
    feishuAppSecret: string
    feishuVerificationToken: string
    feishuEncryptKey: string
    feishuApiBaseUrl: string
  }]
  openLogDir: []
  restartServices: []
  refresh: []
}>()

const form = reactive({
  baseUrl: '',
  apiKey: '',
  model: '',
})

const connectorForm = reactive({
  whatsappArchiveBaseUrl: '',
  feishuWebhookUrl: '',
  feishuWebhookSecret: '',
  feishuAppId: '',
  feishuAppSecret: '',
  feishuVerificationToken: '',
  feishuEncryptKey: '',
  feishuApiBaseUrl: '',
})

watch(
  () => props.llmSettings,
  (settings) => {
    if (!settings) return
    form.baseUrl = settings.base_url || ''
    form.model = settings.model || ''
  },
  { immediate: true },
)

watch(
  () => props.connectorSettings,
  (settings) => {
    if (!settings) return
    connectorForm.whatsappArchiveBaseUrl = settings.whatsapp.archive_base_url || 'http://127.0.0.1:8787'
    connectorForm.feishuWebhookUrl = settings.feishu.webhook_url || ''
    connectorForm.feishuAppId = settings.feishu.app_id || ''
    connectorForm.feishuApiBaseUrl = settings.feishu.api_base_url || 'https://open.feishu.cn'
  },
  { immediate: true },
)

function save() {
  emit('saveLlm', {
    baseUrl: form.baseUrl.trim(),
    apiKey: form.apiKey.trim(),
    model: form.model.trim(),
  })
}

function saveConnectors() {
  emit('saveConnectors', {
    whatsappArchiveBaseUrl: connectorForm.whatsappArchiveBaseUrl.trim(),
    feishuWebhookUrl: connectorForm.feishuWebhookUrl.trim(),
    feishuWebhookSecret: connectorForm.feishuWebhookSecret.trim(),
    feishuAppId: connectorForm.feishuAppId.trim(),
    feishuAppSecret: connectorForm.feishuAppSecret.trim(),
    feishuVerificationToken: connectorForm.feishuVerificationToken.trim(),
    feishuEncryptKey: connectorForm.feishuEncryptKey.trim(),
    feishuApiBaseUrl: connectorForm.feishuApiBaseUrl.trim() || 'https://open.feishu.cn',
  })
}
</script>

<template>
  <section class="panel system-settings-panel">
    <div class="panel__header">
      <div>
        <h2>系统设置</h2>
        <p>本地服务健康状态与统一大模型 API</p>
      </div>
      <button class="mini-button" type="button" @click="emit('refresh')">刷新</button>
      <button class="mini-button" type="button" @click="emit('openLogDir')">打开日志</button>
      <button class="mini-button" type="button" :disabled="isRestartingServices" @click="emit('restartServices')">
        {{ isRestartingServices ? '重启中' : '重启服务' }}
      </button>
    </div>

    <div class="system-status-grid">
      <div class="system-status-card">
        <span>中台</span>
        <strong :class="health ? 'system-ok' : 'system-bad'">
          {{ health ? '已连接' : '未连接' }}
        </strong>
      </div>
      <div class="system-status-card">
        <span>工具层</span>
        <strong :class="runtimeStatus?.toolbox.ok ? 'system-ok' : 'system-warn'">
          {{ runtimeStatus?.toolbox.ok ? '核心可用' : '部分不可用' }}
        </strong>
      </div>
      <div class="system-status-card">
        <span>LLM Gateway</span>
        <strong :class="llmSettings?.configured ? 'system-ok' : 'system-warn'">
          {{ llmSettings?.configured ? '已配置' : '未配置' }}
        </strong>
      </div>
      <div class="system-status-card">
        <span>当前模型</span>
        <strong>{{ llmSettings?.model || '待填写' }}</strong>
      </div>
    </div>

    <div v-if="runtimeStatus" class="runtime-tool-grid">
      <div>
        <h3>必需能力</h3>
        <p
          v-for="item in runtimeStatus.toolbox.required"
          :key="item.name"
          class="runtime-tool-row"
        >
          <span :class="item.ok ? 'status-dot status-dot--green' : 'status-dot status-dot--orange'" />
          <strong>{{ item.name }}</strong>
          <small>{{ item.ok ? '可用' : item.error || '不可用' }}</small>
        </p>
      </div>
      <div>
        <h3>可选集成</h3>
        <p
          v-for="item in runtimeStatus.toolbox.optional"
          :key="item.name"
          class="runtime-tool-row"
        >
          <span :class="item.ok ? 'status-dot status-dot--green' : 'status-dot status-dot--orange'" />
          <strong>{{ item.name }}</strong>
          <small>{{ item.ok ? '可用' : item.configured === false ? '未配置' : item.error || '不可用' }}</small>
        </p>
      </div>
    </div>

    <div class="connector-hints">
      <div>
        <strong>WhatsApp</strong>
        <p>{{ connectorSettings?.whatsapp.configured ? connectorSettings.whatsapp.archive_base_url : '需要启动 whatsapp-archive/app-server 或赤瞳聆讯本地服务。' }}</p>
      </div>
      <div>
        <strong>飞书</strong>
        <p>{{ connectorSettings?.feishu.configured ? 'App 已配置，重启工具层后生效。' : '需要配置 Feishu App ID/Secret、事件 Token 和回调地址。' }}</p>
      </div>
    </div>

    <form class="connector-settings-form" @submit.prevent="saveConnectors">
      <label>
        <span>WhatsApp Archive URL</span>
        <input v-model="connectorForm.whatsappArchiveBaseUrl" placeholder="http://127.0.0.1:8787" />
      </label>
      <label>
        <span>Feishu API Base URL</span>
        <input v-model="connectorForm.feishuApiBaseUrl" placeholder="https://open.feishu.cn" />
      </label>
      <label>
        <span>Feishu Webhook URL</span>
        <input v-model="connectorForm.feishuWebhookUrl" placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/..." />
      </label>
      <label>
        <span>Webhook Secret</span>
        <input v-model="connectorForm.feishuWebhookSecret" type="password" :placeholder="connectorSettings?.feishu.webhook_secret_masked || '可选'" />
      </label>
      <label>
        <span>Feishu App ID</span>
        <input v-model="connectorForm.feishuAppId" placeholder="cli_..." />
      </label>
      <label>
        <span>Feishu App Secret</span>
        <input v-model="connectorForm.feishuAppSecret" type="password" :placeholder="connectorSettings?.feishu.app_secret_masked || 'app secret'" />
      </label>
      <label>
        <span>Event Token</span>
        <input v-model="connectorForm.feishuVerificationToken" type="password" :placeholder="connectorSettings?.feishu.verification_token_masked || 'verification token'" />
      </label>
      <label>
        <span>Encrypt Key</span>
        <input v-model="connectorForm.feishuEncryptKey" type="password" :placeholder="connectorSettings?.feishu.encrypt_key_masked || '可选'" />
      </label>
      <button class="primary-soft-button" type="submit" :disabled="isSavingConnectors">
        {{ isSavingConnectors ? '保存中' : '保存连接器配置' }}
      </button>
    </form>

    <form class="llm-settings-form" @submit.prevent="save">
      <label>
        <span>LLM Base URL</span>
        <input v-model="form.baseUrl" placeholder="https://api.example.com/v1/chat/completions" />
      </label>
      <label>
        <span>LLM API Key</span>
        <input v-model="form.apiKey" type="password" :placeholder="llmSettings?.api_key_masked || 'sk-...'" />
      </label>
      <label>
        <span>Model</span>
        <input v-model="form.model" placeholder="gpt-4o-mini / deepseek-chat / ..." />
      </label>
      <button class="primary-soft-button" type="submit" :disabled="isSaving">
        {{ isSaving ? '保存中' : '保存统一模型配置' }}
      </button>
      <button class="mini-button" type="button" :disabled="isTestingLlm" @click="emit('testLlm')">
        {{ isTestingLlm ? '测试中' : '测试连接' }}
      </button>
    </form>
  </section>
</template>
