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

const CCTV_GATEWAY_BASE_URL =
  import.meta.env.VITE_CCTV_GATEWAY_URL?.replace(/\/$/, '') || 'http://127.0.0.1:3457'

const health = ref<CctvGatewayHealth | null>(null)
const isChecking = ref(false)
const isRefreshingChannels = ref(false)
const playerRevision = ref(0)
const note = ref('正在检查本地 CCTV 网关')

const playerSrc = computed(() => `${CCTV_GATEWAY_BASE_URL}/player?live=1&v=${playerRevision.value}`)
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
      throw new Error(body.error || `HTTP ${response.status}`)
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

function openStandalonePlayer() {
  window.open(playerSrc.value, '_blank', 'noopener,noreferrer')
}

onMounted(refreshHealth)
</script>

<template>
  <main class="workbench cctv-page">
    <section class="hero-panel">
      <div>
        <p class="eyebrow">Chitung Guardian</p>
        <h1>赤瞳守护者 · CCTV 实时播放</h1>
        <p>C-SMART 原生 iframe 播放器 · EZUIKit WebSocket 通道 · 本地网关转接</p>
      </div>
      <div class="hero-panel__status">
        <span class="status-dot" :class="statusDotClass" />
        {{ statusText }}
      </div>
    </section>

    <section class="cctv-control-strip">
      <div class="cctv-metric">
        <span>本地网关</span>
        <strong>{{ CCTV_GATEWAY_BASE_URL }}</strong>
      </div>
      <div class="cctv-metric">
        <span>组织</span>
        <strong>{{ health?.orgId || '未连接' }}</strong>
      </div>
      <div class="cctv-metric">
        <span>通道</span>
        <strong>{{ health?.channelCount ?? 0 }} 路</strong>
      </div>
      <div class="cctv-metric">
        <span>缓存时间</span>
        <strong>{{ updatedAtText }}</strong>
      </div>
      <div class="cctv-actions">
        <button class="mini-button" type="button" :disabled="isChecking" @click="refreshHealth">
          {{ isChecking ? '检查中' : '刷新状态' }}
        </button>
        <button class="mini-button" type="button" :disabled="isRefreshingChannels" @click="refreshChannels">
          {{ isRefreshingChannels ? '刷新中' : '刷新通道' }}
        </button>
        <button class="primary-soft-button" type="button" @click="reloadPlayer">重载播放器</button>
        <button class="mini-button" type="button" @click="openStandalonePlayer">独立窗口</button>
      </div>
    </section>

    <section v-if="!isPlayable" class="panel cctv-runtime-panel">
      <div class="panel__header">
        <div>
          <h2>运行状态</h2>
          <p>{{ note }}</p>
        </div>
      </div>
      <div class="cctv-runtime-grid">
        <div>
          <span>C-SMART Bearer</span>
          <strong>{{ health?.hasBearer ? '已就绪' : '缺失' }}</strong>
        </div>
        <div>
          <span>通道缓存</span>
          <strong>{{ health?.cacheFile || 'csmart-channel-list-latest.json' }}</strong>
        </div>
        <div>
          <span>播放器来源</span>
          <strong>{{ health?.playerUrl || 'custom.c-smart.hk' }}</strong>
        </div>
      </div>
    </section>

    <section class="cctv-player-shell" aria-label="CCTV player">
      <iframe
        :key="playerRevision"
        :src="playerSrc"
        class="cctv-player"
        title="C-SMART CCTV player"
        allow="autoplay; fullscreen"
      />
    </section>
  </main>
</template>

<style scoped>
.cctv-page {
  display: flex;
  flex-direction: column;
  min-height: 100%;
}

.cctv-control-strip {
  align-items: stretch;
  background: var(--bg-white);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-sm);
  display: grid;
  gap: 12px;
  grid-template-columns: 1.4fr minmax(120px, 0.6fr) minmax(100px, 0.45fr) minmax(160px, 0.8fr) auto;
  margin-bottom: 16px;
  padding: 12px;
}

.cctv-metric {
  background: var(--bg-subtle);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-width: 0;
  padding: 9px 10px;
}

.cctv-metric span {
  color: var(--text-secondary);
  font-size: 12px;
}

.cctv-metric strong {
  color: var(--text-primary);
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cctv-actions {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.cctv-runtime-panel {
  margin-bottom: 16px;
}

.cctv-runtime-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.cctv-runtime-grid div {
  background: var(--bg-subtle);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  min-width: 0;
  padding: 10px 12px;
}

.cctv-runtime-grid span {
  color: var(--text-secondary);
  display: block;
  font-size: 12px;
  margin-bottom: 4px;
}

.cctv-runtime-grid strong {
  color: var(--text-primary);
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cctv-player-shell {
  background: #0b1220;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-xl);
  flex: 1;
  min-height: 620px;
  overflow: hidden;
}

.cctv-player {
  border: 0;
  display: block;
  height: 100%;
  min-height: 620px;
  width: 100%;
}

@media (max-width: 1180px) {
  .cctv-control-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .cctv-actions {
    grid-column: 1 / -1;
    justify-content: flex-start;
  }
}

@media (max-width: 760px) {
  .hero-panel {
    align-items: flex-start;
    flex-direction: column;
    gap: 12px;
  }

  .cctv-control-strip,
  .cctv-runtime-grid {
    grid-template-columns: 1fr;
  }

  .cctv-player-shell,
  .cctv-player {
    min-height: 560px;
  }
}
</style>
