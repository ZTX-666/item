<script setup lang="ts">
import { reactive, watch } from 'vue'
import type { AppConfig, ConnectorSettingsStatus, LlmSettingsStatus, RuntimeStatus } from '../../types/domain'

const props = defineProps<{
  health: Record<string, unknown> | null
  llmSettings: LlmSettingsStatus | null
  connectorSettings: ConnectorSettingsStatus | null
  runtimeStatus: RuntimeStatus | null
  appConfig: AppConfig | null
  logDir?: string | null
  isSaving?: boolean
  isTestingLlm?: boolean
  isSavingConnectors?: boolean
  isSavingConfig?: boolean
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
  saveConfig: [payload: AppConfig]
  openLogDir: []
  restartServices: []
  refresh: []
}>()

const form = reactive({
  baseUrl: '',
  apiKey: '',
  model: '',
})

const configForm = reactive({
  projectName: '',
  defaultArea: '',
  location: '',
  cameraId: '',
  cameraName: '',
  cameraArea: '',
  cameraRtmpUrl: '',
  contractorId: '',
  contractorName: '',
  contractorContact: '',
  contractorChannel: '',
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
  () => props.appConfig,
  (config) => {
    if (!config) return
    const camera = config.cameras[0]
    const contractor = config.contractors[0]
    configForm.projectName = config.project.name
    configForm.defaultArea = config.project.default_area
    configForm.location = config.project.location
    configForm.cameraId = camera?.id || 'B2-Z1'
    configForm.cameraName = camera?.name || 'B2 区 1 号摄像头'
    configForm.cameraArea = camera?.area || config.project.default_area
    configForm.cameraRtmpUrl = camera?.rtmp_url || ''
    configForm.contractorId = contractor?.id || 'default'
    configForm.contractorName = contractor?.name || '待确认分包商'
    configForm.contractorContact = contractor?.contact || ''
    configForm.contractorChannel = contractor?.channel || ''
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

function saveConfig() {
  emit('saveConfig', {
    project: {
      name: configForm.projectName.trim() || '赤瞳示范项目',
      default_area: configForm.defaultArea.trim() || 'B2',
      location: configForm.location.trim() || 'Hong Kong',
    },
    cameras: [
      {
        id: configForm.cameraId.trim() || 'B2-Z1',
        name: configForm.cameraName.trim() || 'B2 区 1 号摄像头',
        area: configForm.cameraArea.trim() || configForm.defaultArea.trim() || 'B2',
        rtmp_url: configForm.cameraRtmpUrl.trim() || null,
        enabled: true,
      },
    ],
    contractors: [
      {
        id: configForm.contractorId.trim() || 'default',
        name: configForm.contractorName.trim() || '待确认分包商',
        contact: configForm.contractorContact.trim(),
        channel: configForm.contractorChannel.trim(),
        default_due_days: 3,
      },
    ],
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
        <p>{{ connectorSettings?.whatsapp.configured ? connectorSettings.whatsapp.archive_base_url : '需要启动 whatsapp-archive/app-server 或赤瞳灵讯本地服务。' }}</p>
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

    <form class="app-config-form" @submit.prevent="saveConfig">
      <label>
        <span>项目名称</span>
        <input v-model="configForm.projectName" placeholder="赤瞳示范项目" />
      </label>
      <label>
        <span>默认区域</span>
        <input v-model="configForm.defaultArea" placeholder="B2" />
      </label>
      <label>
        <span>摄像头名称</span>
        <input v-model="configForm.cameraName" placeholder="B2 区 1 号摄像头" />
      </label>
      <label>
        <span>RTMP 地址</span>
        <input v-model="configForm.cameraRtmpUrl" placeholder="rtmp://..." />
      </label>
      <label>
        <span>分包商</span>
        <input v-model="configForm.contractorName" placeholder="分包商名称" />
      </label>
      <label>
        <span>联系人/渠道</span>
        <input v-model="configForm.contractorContact" placeholder="WhatsApp / 电话 / 飞书" />
      </label>
      <button class="primary-soft-button" type="submit" :disabled="isSavingConfig">
        {{ isSavingConfig ? '保存中' : '保存项目配置' }}
      </button>
    </form>
  </section>
</template>
