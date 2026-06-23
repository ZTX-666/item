<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getJobStats, listJobs } from '../services/chitungApi'
import type { JobRun, JobStats } from '../types/domain'

const jobs = ref<JobRun[]>([])
const stats = ref<JobStats | null>(null)
const loading = ref(false)
const error = ref('')
const selectedModule = ref('')

const modules = computed(() => Object.keys(stats.value?.by_module ?? {}))

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    const [nextStats, nextJobs] = await Promise.all([
      getJobStats(),
      listJobs({ sourceModule: selectedModule.value || undefined, limit: 80 }),
    ])
    stats.value = nextStats
    jobs.value = nextJobs
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

function formatTime(value?: string | null): string {
  if (!value) return '-'
  try {
    return new Date(value).toLocaleString('zh-CN')
  } catch {
    return value
  }
}

function statusText(status: string): string {
  const map: Record<string, string> = {
    queued: '排队中',
    running: '执行中',
    success: '已完成',
    failed: '失败',
  }
  return map[status] || status
}

onMounted(refresh)
</script>

<template>
  <main class="workbench">
    <section class="hero-panel">
      <div>
        <p class="eyebrow">Execution Center</p>
        <h1>统一执行中心</h1>
        <p>集中查看 Skill、Agent、自动化、RAG 上传、视觉检测、外部讯息监听等任务状态。</p>
      </div>
      <button class="primary-soft-button" :disabled="loading" @click="refresh">
        {{ loading ? '刷新中...' : '刷新任务' }}
      </button>
    </section>

    <section class="execution-stats">
      <article class="execution-stat-card">
        <span>任务总数</span>
        <strong>{{ stats?.total ?? 0 }}</strong>
      </article>
      <article class="execution-stat-card">
        <span>执行中</span>
        <strong>{{ stats?.by_status?.running ?? 0 }}</strong>
      </article>
      <article class="execution-stat-card">
        <span>已完成</span>
        <strong>{{ stats?.by_status?.success ?? 0 }}</strong>
      </article>
      <article class="execution-stat-card">
        <span>失败</span>
        <strong>{{ stats?.by_status?.failed ?? 0 }}</strong>
      </article>
    </section>

    <section class="panel">
      <div class="panel__header">
        <div>
          <h2>任务流</h2>
          <p>按模块过滤最近执行记录，后续可扩展为 SSE 实时订阅。</p>
        </div>
        <select v-model="selectedModule" class="execution-filter" @change="refresh">
          <option value="">全部模块</option>
          <option v-for="module in modules" :key="module" :value="module">{{ module }}</option>
        </select>
      </div>
      <p v-if="error" class="execution-error">{{ error }}</p>
      <div class="execution-list">
        <article v-for="job in jobs" :key="job.job_id" class="execution-row">
          <div>
            <strong>{{ job.title }}</strong>
            <p>{{ job.source_module }} · {{ job.job_type }} · {{ formatTime(job.created_at) }}</p>
          </div>
          <div class="execution-progress">
            <span :class="`execution-status execution-status--${job.status}`">{{ statusText(job.status) }}</span>
            <progress :value="job.progress" max="100"></progress>
            <small>{{ job.progress }}%</small>
          </div>
        </article>
        <p v-if="!jobs.length && !loading" class="execution-empty">暂无统一任务记录。</p>
      </div>
    </section>
  </main>
</template>

<style scoped>
.execution-stats {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-bottom: 16px;
}

.execution-stat-card,
.execution-row {
  background: var(--card-bg);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}

.execution-stat-card {
  display: grid;
  gap: 6px;
  padding: 14px;
}

.execution-stat-card span,
.execution-row p,
.execution-empty {
  color: var(--text-secondary);
}

.execution-stat-card strong {
  font-size: 24px;
}

.execution-filter {
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 8px 10px;
}

.execution-error {
  color: var(--color-error);
}

.execution-list {
  display: grid;
  gap: 10px;
}

.execution-row {
  align-items: center;
  display: grid;
  gap: 12px;
  grid-template-columns: minmax(0, 1fr) 220px;
  padding: 12px 14px;
}

.execution-row p {
  margin: 4px 0 0;
}

.execution-progress {
  display: grid;
  gap: 5px;
}

.execution-progress progress {
  width: 100%;
}

.execution-status {
  color: var(--text-secondary);
  font-size: 12px;
}

.execution-status--failed {
  color: var(--color-error);
}

.execution-status--running {
  color: var(--brand-blue);
}
</style>
