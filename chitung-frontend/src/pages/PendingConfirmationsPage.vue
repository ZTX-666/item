<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { getPendingConfirmations, resolvePendingConfirmation } from '../services/chitungApi'
import type { PendingConfirmation } from '../types/domain'

const props = defineProps<{
  refreshTick?: number
}>()

const items = ref<PendingConfirmation[]>([])
const isLoading = ref(false)
const isResolving = ref(false)
const statusFilter = ref('pending')
const errorMessage = ref('')

const filteredItems = computed(() => {
  if (statusFilter.value === 'all') return items.value
  return items.value.filter((item) => String(item.status || '').toLowerCase() === statusFilter.value.toLowerCase())
})

async function refresh() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    items.value = await getPendingConfirmations({
      status: statusFilter.value === 'all' ? undefined : statusFilter.value,
      limit: 100,
    })
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
    items.value = []
  } finally {
    isLoading.value = false
  }
}

async function handleResolve(confirmationId: string, decision: 'approve' | 'reject') {
  isResolving.value = true
  errorMessage.value = ''
  try {
    await resolvePendingConfirmation({
      confirmationId,
      decision,
      notes: decision === 'approve' ? 'Approved from pending confirmations page.' : 'Rejected from pending confirmations page.',
    })
    await refresh()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    isResolving.value = false
  }
}

function riskTone(level?: string) {
  const normalized = String(level || 'medium').toLowerCase()
  if (normalized === 'critical' || normalized === 'high') return 'red'
  if (normalized === 'low') return 'green'
  return 'orange'
}

onMounted(refresh)

watch(
  () => props.refreshTick,
  () => {
    void refresh()
  },
)
</script>

<template>
  <main class="workbench">
    <section class="hero-panel">
      <div>
        <p class="eyebrow">Confirmation Queue</p>
        <h1>待确认动作</h1>
        <p>人工确认后再执行外发、整改通知生成等高风险动作。</p>
      </div>
      <div class="hero-panel__status">
        <span class="status-dot status-dot--green" />
        当前 {{ filteredItems.length }} 条
      </div>
    </section>

    <section class="panel" style="margin-bottom: 12px;">
      <div class="template-search-bar">
        <select v-model="statusFilter" @change="refresh">
          <option value="pending">待确认</option>
          <option value="approved">已批准</option>
          <option value="rejected">已拒绝</option>
          <option value="executed">已执行</option>
          <option value="failed">执行失败</option>
          <option value="all">全部</option>
        </select>
        <button class="primary-soft-button" :disabled="isLoading" @click="refresh">
          {{ isLoading ? '刷新中' : '刷新' }}
        </button>
      </div>
      <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
    </section>

    <section class="panel">
      <div v-if="isLoading" class="empty-state">加载中…</div>
      <div v-else-if="!filteredItems.length" class="empty-state">
        暂无{{ statusFilter === 'pending' ? '待确认' : '' }}记录。可通过聊天卡片或飞书回调创建确认项。
      </div>
      <div v-else class="confirmation-list">
        <article v-for="item in filteredItems" :key="item.confirmation_id" class="confirmation-card">
          <header class="confirmation-card__header">
            <div>
              <h3>{{ item.title }}</h3>
              <p>{{ item.summary || '无摘要' }}</p>
            </div>
            <span class="risk-pill" :class="`risk-pill--${riskTone(item.risk_level)}`">
              {{ item.risk_level || 'medium' }}
            </span>
          </header>
          <dl class="confirmation-card__meta">
            <div><dt>动作类型</dt><dd>{{ item.action_type }}</dd></div>
            <div><dt>来源</dt><dd>{{ item.source_channel || 'local_web' }}</dd></div>
            <div><dt>状态</dt><dd>{{ item.status }}</dd></div>
            <div><dt>创建时间</dt><dd>{{ item.created_at || '-' }}</dd></div>
          </dl>
          <footer v-if="item.status === 'pending'" class="confirmation-card__actions">
            <button class="primary-button" :disabled="isResolving" @click="handleResolve(item.confirmation_id, 'approve')">
              批准并执行
            </button>
            <button class="ghost-button" :disabled="isResolving" @click="handleResolve(item.confirmation_id, 'reject')">
              拒绝
            </button>
          </footer>
        </article>
      </div>
    </section>
  </main>
</template>

<style scoped>
.confirmation-list {
  display: grid;
  gap: 12px;
}

.confirmation-card {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.02);
}

.confirmation-card__header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.confirmation-card__header h3 {
  margin: 0 0 4px;
}

.confirmation-card__header p {
  margin: 0;
  color: var(--text-muted, #9aa4b2);
}

.confirmation-card__meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 8px 16px;
  margin: 0 0 12px;
}

.confirmation-card__meta dt {
  font-size: 12px;
  color: var(--text-muted, #9aa4b2);
}

.confirmation-card__meta dd {
  margin: 2px 0 0;
}

.confirmation-card__actions {
  display: flex;
  gap: 8px;
}

.risk-pill {
  align-self: flex-start;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  text-transform: uppercase;
}

.risk-pill--red { background: rgba(239, 68, 68, 0.15); color: #fca5a5; }
.risk-pill--orange { background: rgba(249, 115, 22, 0.15); color: #fdba74; }
.risk-pill--green { background: rgba(34, 197, 94, 0.15); color: #86efac; }

.empty-state,
.error-text {
  color: var(--text-muted, #9aa4b2);
}

.error-text {
  margin-top: 8px;
  color: #fca5a5;
}
</style>
