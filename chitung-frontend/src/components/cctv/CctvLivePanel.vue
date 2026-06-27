<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

interface CctvGatewayHealth {
  ok: boolean
  hasBearer: boolean
  cacheFile: string
  channelCount: number
  channelUpdatedAt: string | null
  gateway: string
  orgId: string
  playerUrl: string
  error?: string
}

const props = withDefaults(defineProps<{
  title?: string
  subtitle?: string
  compact?: boolean
  actionLabel?: string
  busyLabel?: string
  busy?: boolean
  showAction?: boolean
}>(), {
  title: 'CCTV 实时画面',
  subtitle: 'EZVIZ 实时播放（11 路）',
  compact: false,
  actionLabel: '发起视觉巡检',
  busyLabel: '巡检中',
  busy: false,
  showAction: true,
})

const emit = defineEmits<{
  patrol: []
}>()

const CCTV_GATEWAY_BASE_URL =
  import.meta.env.VITE_CCTV_GATEWAY_URL?.replace(/\/$/, '') || 'http://127.0.0.1:3457'

const health = ref<CctvGatewayHealth | null>(null)
const isChecking = ref(false)
const isRefreshingChannels = ref(false)
const playerRevision = ref(0)
const note = ref('正在检查本地 CCTV 网关')

const playerSrc = computed(() => `${CCTV_GATEWAY_BASE_URL}/player?embedded=1&live=1&v=${playerRevision.value}`)
const healthUrl = computed(() => `${CCTV_GATEWAY_BASE_URL}/api/health`)
const isPlayable = computed(() => (health.value?.channelCount ?? 0) > 0)

const statusText = computed(() => {
  if (isChecking.value) return '正在检查网关'
  if (!health.value) return note.value
  if (isPlayable.value) return `已加载 ${health.value.channelCount} 路通道`
  if (health.value.hasBearer) return '已连接令牌，等待拉取通道'
  return '等待 C-SMART 令牌或通道缓存'
})

const statusDotClass = computed(() => {
  if (isPlayable.value) return 'status-dot--green'
  return 'status-dot--orange'
})

const updatedAtText = computed(() => {
  if (!health.value?.channelUpdatedAt) return '暂无'
  return new Date(health.value.channelUpdatedAt).toLocaleString('zh-CN', { hour12: false })
})

async function fetchGatewayHealth() {
  const response = await fetch(healthUrl.value)
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`)
  }
  return await response.json() as CctvGatewayHealth
}

async function refreshHealth() {
  isChecking.value = true
  note.value = '正在检查本地 CCTV 网关'
  try {
    try {
      health.value = await fetchGatewayHealth()
    } catch (firstError) {
      if (!window.chitungDesktop?.ensureCctvGateway) {
        throw firstError
      }
      note.value = '网关无响应，正在拉起本地 CCTV 网关'
      const ensured = await window.chitungDesktop.ensureCctvGateway()
      if (!ensured.ok) {
        throw new Error(ensured.error || 'CCTV 网关启动失败')
      }
      health.value = await fetchGatewayHealth()
    }
    note.value = health.value.ok ? '网关已响应' : '网关已响应，尚未加载通道'
  } catch (error) {
    health.value = null
    note.value = `网关不可用：${error instanceof Error ? error.message : String(error)}`
  } finally {
    isChecking.value = false
  }
}

async function refreshChannels() {
  isRefreshingChannels.value = true
  note.value = '正在向 C-SMART 拉取通道'
  try {
    const response = await fetch(`${CCTV_GATEWAY_BASE_URL}/api/csmart/channels/refresh`, { method: 'POST' })
    if (!response.ok) {
      const body = await response.json().catch(() => ({}))
      throw new Error(String(body.error || `HTTP ${response.status}`))
    }
    playerRevision.value += 1
    await refreshHealth()
  } catch (error) {
    note.value = `通道刷新失败：${error instanceof Error ? error.message : String(error)}`
  } finally {
    isRefreshingChannels.value = false
  }
}

function reloadPlayer() {
  playerRevision.value += 1
}

onMounted(refreshHealth)
</script>

<template>
  <section class="panel cctv-live-panel" :class="{ 'cctv-live-panel--compact': compact }">
    <div class="panel__header cctv-live-panel__header">
      <div>
        <h2>{{ title }}</h2>
        <p>{{ subtitle }}</p>
      </div>
      <div class="cctv-live-panel__status">
        <span class="status-dot" :class="statusDotClass" />
        {{ statusText }}
      </div>
    </div>

    <div class="cctv-live-panel__metrics">
      <div>
        <span>通道</span>
        <strong>{{ health?.channelCount ?? 0 }} 路</strong>
      </div>
      <div>
        <span>组织</span>
        <strong>{{ health?.orgId || '未连接' }}</strong>
      </div>
      <div>
        <span>缓存</span>
        <strong>{{ updatedAtText }}</strong>
      </div>
    </div>

    <div v-if="!isPlayable" class="cctv-live-panel__notice">
      <span>C-SMART</span>
      <strong>{{ health?.hasBearer ? '已连接令牌，等待通道缓存。' : '缺少令牌或通道缓存。' }}</strong>
    </div>

    <div class="cctv-live-panel__player-shell">
      <iframe
        :key="playerRevision"
        :src="playerSrc"
        class="cctv-live-panel__player"
        title="C-SMART CCTV player"
        allow="autoplay; fullscreen"
      />
    </div>

    <div class="cctv-live-panel__actions">
      <button class="mini-button" type="button" :disabled="isChecking" @click="refreshHealth">
        {{ isChecking ? '检查中' : '刷新状态' }}
      </button>
      <button class="mini-button" type="button" :disabled="isRefreshingChannels" @click="refreshChannels">
        {{ isRefreshingChannels ? '刷新中' : '刷新通道' }}
      </button>
      <button class="mini-button" type="button" @click="reloadPlayer">重载播放器</button>
      <button v-if="showAction" class="primary-soft-button" type="button" :disabled="busy" @click="emit('patrol')">
        {{ busy ? busyLabel : actionLabel }}
      </button>
    </div>
  </section>
</template>

<style scoped>
.cctv-live-panel {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.cctv-live-panel--compact {
  background: transparent;
  border: 0;
  box-shadow: none;
  padding: 0;
}

.cctv-live-panel__header {
  align-items: center;
  gap: 12px;
}

.cctv-live-panel__status {
  align-items: center;
  color: var(--text-secondary);
  display: flex;
  flex-shrink: 0;
  font-size: 12px;
  gap: 6px;
  max-width: 260px;
  text-align: right;
}

.cctv-live-panel__metrics {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-bottom: 10px;
}

.cctv-live-panel__metrics div,
.cctv-live-panel__notice {
  background: var(--bg-subtle);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  min-width: 0;
  padding: 8px 10px;
}

.cctv-live-panel__metrics span,
.cctv-live-panel__notice span {
  color: var(--text-secondary);
  display: block;
  font-size: 11px;
  margin-bottom: 3px;
}

.cctv-live-panel__metrics strong,
.cctv-live-panel__notice strong {
  color: var(--text-primary);
  display: block;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cctv-live-panel__notice {
  margin-bottom: 10px;
}

.cctv-live-panel__player-shell {
  aspect-ratio: 6 / 5;
  background: #0b1220;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  flex: none;
  margin-inline: auto;
  min-height: 0;
  overflow: hidden;
  width: min(100%, 1120px);
}

.cctv-live-panel--compact .cctv-live-panel__player-shell {
  background: transparent;
  border: 0;
  border-radius: 0;
  min-height: 0;
}

.cctv-live-panel__player {
  border: 0;
  display: block;
  height: 100%;
  min-height: 0;
  width: 100%;
}

.cctv-live-panel__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
  margin-top: 10px;
}

@media (max-width: 760px) {
  .cctv-live-panel__header {
    align-items: flex-start;
    flex-direction: column;
  }

  .cctv-live-panel__status {
    max-width: none;
    text-align: left;
  }

  .cctv-live-panel__metrics {
    grid-template-columns: 1fr;
  }

  .cctv-live-panel__actions {
    justify-content: flex-start;
  }
}
</style>
