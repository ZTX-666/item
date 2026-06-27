<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  getRiskCardStats,
  getExternalInfoMonitorStatus,
  listExternalInfoEvents,
  listExternalInfoMonitorRuns,
  listExternalRiskBriefingReports,
  listRiskCards,
  runExternalInfoMonitorAsync,
  saveExternalInfoMonitorSettings,
} from '../services/chitungApi'
import { useJobPolling } from '../composables/useJobPolling'
import type {
  ExternalInfoEvent,
  ExternalMonitorRun,
  ExternalMonitorStatus,
  ExternalRiskBriefingReport,
  RiskCard,
  RiskCardStats,
} from '../types/domain'

// ── Card data state ──────────────────────────────────────────────
const cards = ref<RiskCard[]>([])
const stats = ref<RiskCardStats | null>(null)
const loading = ref(false)
const cardsError = ref('')

// ── Filter state ─────────────────────────────────────────────────
const filterCategory = ref('')
const filterPriority = ref('')
const filterKeyword = ref('')
const filterDateFrom = ref('')
const filterDateTo = ref('')

// ── Briefing trigger state (preserved from original) ─────────────
const area = ref('香港项目')
const focus = ref('施工安全、天气预警、工伤意外')
const selectedSources = ref(['weather', 'official', 'media'])
const deliveryMode = ref<'draft' | 'feishu'>('draft')
const recipient = ref('项目安全群')
const isRunning = ref(false)
const briefingError = ref('')
const responseSummary = ref('')
const briefingText = ref('')
const toolResults = ref<Array<Record<string, unknown>>>([])
const showBriefingResult = ref(false)
const monitorStatus = ref<ExternalMonitorStatus | null>(null)
const monitorRuns = ref<ExternalMonitorRun[]>([])
const monitorEvents = ref<ExternalInfoEvent[]>([])
const listenIntervalMinutes = ref(60)
const lookbackHours = ref(24)
const isAutoListening = ref(true)
const listenStatus = ref('正在读取后端监听状态')
const { activeJob, jobError, poll: pollJob } = useJobPolling()

const sourceOptions = [
  { id: 'weather', label: '香港天文台' },
  { id: 'official', label: '官方安全更新' },
  { id: 'media', label: '白名单媒体' },
]

// ── History state (preserved from original) ──────────────────────
const historyReports = ref<ExternalRiskBriefingReport[]>([])
const showHistory = ref(false)
const historyError = ref('')

const totalCollected = computed(() => stats.value?.total ?? cards.value.length)

const usageTrail = computed(() =>
  monitorRuns.value.slice(0, 6).map((run) => ({
    id: run.run_id,
    title: run.status === 'success' ? '监听完成' : run.status,
    time: formatDate(run.started_at),
    detail: `新增卡片 ${run.card_count} · 原始讯息 ${run.new_raw_count} · 告警 ${run.alert_count}`,
  })),
)

const headerUsageText = computed(() => {
  const parts: string[] = []
  if (totalCollected.value) parts.push(`累计采集 ${totalCollected.value} 张卡片`)
  if (monitorRuns.value.length) parts.push(`最近 ${monitorRuns.value.length} 次运行`)
  if (historyReports.value.length) parts.push(`${historyReports.value.length} 份历史简报`)
  return parts.length ? parts.join(' · ') : '暂无采集记录，可点击「立即监听」或等待常驻调度'
})

// ── Dashboard stats ──────────────────────────────────────────────
const activeWeatherCount = computed(() => {
  return cards.value.filter((c) => c.source_category === 'weather').length
})

// ── Card filtering helpers ───────────────────────────────────────
const categoryTabs = [
  { id: '', label: '全部', emoji: '' },
  { id: 'weather', label: '天气气象', emoji: '\u{1F324}\u{FE0F}' },
  { id: 'official', label: '官方监管', emoji: '\u{1F3DB}\u{FE0F}' },
  { id: 'media', label: '媒体报道', emoji: '\u{1F4F0}' },
]

const priorityOptions = [
  { id: '', label: '全部' },
  { id: 'P0', label: 'P0' },
  { id: 'P1', label: 'P1' },
  { id: 'P2', label: 'P2' },
]

const lookbackOptions = [
  { id: 1, label: '1小时' },
  { id: 6, label: '6小时' },
  { id: 24, label: '24小时' },
  { id: 168, label: '7天' },
]

// ── Data fetching ────────────────────────────────────────────────
async function fetchCards() {
  loading.value = true
  cardsError.value = ''
  try {
    const res = await listRiskCards({
      category: filterCategory.value || undefined,
      priority: filterPriority.value || undefined,
      date_from: filterDateFrom.value || undefined,
      date_to: filterDateTo.value || undefined,
      keyword: filterKeyword.value || undefined,
      limit: 200,
    })
    cards.value = res.cards
  } catch (err) {
    cardsError.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

async function fetchStats() {
  try {
    stats.value = await getRiskCardStats()
  } catch {
    // Stats are best-effort; silently ignore errors
  }
}

async function refresh() {
  await Promise.all([fetchCards(), fetchStats(), fetchMonitorStatus(), fetchMonitorRuns(), fetchMonitorEvents()])
}

// ── Briefing trigger (preserved logic) ───────────────────────────
function toggleSource(sourceId: string) {
  if (selectedSources.value.includes(sourceId)) {
    selectedSources.value = selectedSources.value.filter((item) => item !== sourceId)
  } else {
    selectedSources.value = [...selectedSources.value, sourceId]
  }
}

async function triggerBriefing() {
  if (isRunning.value) return
  isRunning.value = true
  briefingError.value = ''
  responseSummary.value = ''
  briefingText.value = ''
  toolResults.value = []
  showBriefingResult.value = true

  try {
    const response = await runExternalInfoMonitorAsync()
    responseSummary.value = `外部讯息监听已提交后台任务：${response.job_id}`
    void pollJob(response.job_id, async (job) => {
      const result = job.result || {}
      const run = (result.run as ExternalMonitorRun | undefined) ?? null
      const workflow = (result.workflow as Record<string, unknown> | undefined) ?? {}
      responseSummary.value = run
        ? `后台监听完成：新增 ${run.new_raw_count} 条原始讯息，新增 ${run.new_event_count} 个事件，生成 ${run.card_count} 张卡片，触发 ${run.alert_count} 个告警。`
        : String(workflow.reply || '外部讯息监听已完成')
      toolResults.value = (workflow.tool_results as Array<Record<string, unknown>> | undefined) ?? []
      const cardList = (workflow.cards as Array<Record<string, unknown>> | undefined) ?? []
      const externalCard = cardList.find((card) => card.card_type === 'external_risk_briefing')
      const cardData = (externalCard?.data as Record<string, unknown> | undefined) ?? {}
      briefingText.value = extractBriefingText(cardData, toolResults.value)
      await refresh()
      await loadBriefingHistory()
      isRunning.value = false
    })
  } catch (err) {
    briefingError.value = err instanceof Error ? err.message : String(err)
    isRunning.value = false
  }
}

function normalizeListenInterval(value: number): number {
  if (!Number.isFinite(value)) return 60
  return Math.max(5, Math.min(Math.round(value), 24 * 60))
}

async function saveListenSettings() {
  listenIntervalMinutes.value = normalizeListenInterval(listenIntervalMinutes.value)
  const status = await saveExternalInfoMonitorSettings({
    enabled: isAutoListening.value,
    interval_minutes: listenIntervalMinutes.value,
    lookback_hours: lookbackHours.value,
    sources: selectedSources.value,
    keywords: focus.value.split(/[、,，\s]+/).map((item) => item.trim()).filter(Boolean),
    area: area.value,
    delivery_mode: deliveryMode.value,
    recipient: deliveryMode.value === 'feishu' ? recipient.value : '',
  })
  applyMonitorStatus(status)
}

async function toggleAutoListening() {
  isAutoListening.value = !isAutoListening.value
  await saveListenSettings()
}

async function fetchMonitorStatus() {
  try {
    const status = await getExternalInfoMonitorStatus()
    applyMonitorStatus(status)
  } catch (err) {
    listenStatus.value = err instanceof Error ? err.message : String(err)
  }
}

async function fetchMonitorRuns() {
  monitorRuns.value = await listExternalInfoMonitorRuns(8)
}

async function fetchMonitorEvents() {
  monitorEvents.value = await listExternalInfoEvents(8, lookbackHours.value)
}

function applyMonitorStatus(status: ExternalMonitorStatus) {
  monitorStatus.value = status
  isAutoListening.value = status.settings.enabled
  listenIntervalMinutes.value = status.settings.interval_minutes
  lookbackHours.value = status.settings.lookback_hours || lookbackHours.value
  selectedSources.value = status.settings.sources?.length ? status.settings.sources : selectedSources.value
  area.value = status.settings.area || area.value
  deliveryMode.value = status.settings.delivery_mode || deliveryMode.value
  recipient.value = status.settings.recipient || recipient.value
  listenStatus.value = status.running
    ? '后端正在监听外部讯息'
    : status.settings.enabled
      ? `后端常驻监听中，下次运行：${status.next_run_at ? formatDate(status.next_run_at) : '等待调度'}`
      : '后端监听已暂停'
}

function extractBriefingText(
  cardData: Record<string, unknown>,
  results: Array<Record<string, unknown>>,
): string {
  const direct = cardData.briefing_text
  if (typeof direct === 'string' && direct.trim()) return direct.trim()

  const briefing = cardData.briefing
  const fromCard = textFromToolResult(briefing)
  if (fromCard) return fromCard

  const result = results.find(
    (item) => item.tool === 'draft_daily_risk_briefing' || item.source === 'draft_daily_risk_briefing',
  )
  return textFromToolResult(result) || ''
}

function textFromToolResult(value: unknown): string {
  if (!value || typeof value !== 'object') return ''
  const result = value as Record<string, unknown>
  const items = Array.isArray(result.items) ? result.items : []
  for (const item of items) {
    if (item && typeof item === 'object') {
      const text = (item as Record<string, unknown>).text
      if (typeof text === 'string' && text.trim()) return text.trim()
    }
  }
  return ''
}

// ── History (preserved logic) ────────────────────────────────────
async function loadBriefingHistory() {
  historyError.value = ''
  try {
    historyReports.value = await listExternalRiskBriefingReports(20)
    if (historyReports.value.length) {
      showHistory.value = true
    }
  } catch (err) {
    historyError.value = err instanceof Error ? err.message : String(err)
  }
}

function applyHistoryReport(report: ExternalRiskBriefingReport) {
  responseSummary.value = report.summary || '已加载历史简报'
  briefingText.value = report.briefing_text
  toolResults.value = report.tool_results ?? []
  showBriefingResult.value = true
}

// ── Formatting helpers ───────────────────────────────────────────
function formatDate(value: string | null): string {
  if (!value) return '-'
  try {
    return new Date(value).toLocaleString('zh-CN')
  } catch {
    return value
  }
}

function formatEventDate(value: string | null): string {
  if (!value) return ''
  try {
    return new Date(value).toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return value
  }
}

const currentDateTime = ref('')
let dateTimeTimer: ReturnType<typeof setInterval> | null = null
let statusTimer: ReturnType<typeof setInterval> | null = null
function updateDateTime() {
  currentDateTime.value = new Date().toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

// ── Card class helpers ───────────────────────────────────────────
function cardClass(card: RiskCard): string {
  return `risk-card--${card.source_category}`
}

function priorityClass(priority: string): string {
  return `priority-badge--${priority}`
}

function priorityLabel(priority: string): string {
  if (priority === 'P0') return 'P0 紧急'
  if (priority === 'P1') return 'P1 重要'
  return 'P2 关注'
}

// ── Lifecycle ────────────────────────────────────────────────────
onMounted(() => {
  updateDateTime()
  refresh()
  loadBriefingHistory()
  dateTimeTimer = setInterval(updateDateTime, 1000)
  statusTimer = setInterval(() => {
    void fetchMonitorStatus()
  }, 15000)
})

onBeforeUnmount(() => {
  if (dateTimeTimer) {
    clearInterval(dateTimeTimer)
    dateTimeTimer = null
  }
  if (statusTimer) {
    clearInterval(statusTimer)
    statusTimer = null
  }
})
</script>

<template>
  <main class="risk-page">
    <!-- ── Page Header ─────────────────────────────────────── -->
    <header class="risk-header">
      <div class="risk-header__left">
        <h1 class="risk-header__title">外部讯息监听</h1>
        <p class="risk-header__datetime">{{ currentDateTime }}</p>
        <p class="risk-header__usage">{{ headerUsageText }}</p>
      </div>
      <div class="risk-header__actions">
        <span class="listen-pill" :class="{ 'listen-pill--paused': !isAutoListening }">
          {{ isAutoListening ? '监听中' : '已暂停' }}
        </span>
        <button class="risk-header__refresh" :disabled="loading" @click="refresh">
          <span v-if="loading" class="spinner" />
          {{ loading ? '加载中...' : '刷新' }}
        </button>
      </div>
    </header>

    <section class="listen-panel">
      <div>
        <h2>常驻监听</h2>
        <p>{{ listenStatus }}。系统会按设定频率自动采集天气、官方监管和白名单媒体讯息。</p>
        <p v-if="monitorStatus?.last_error" class="listen-panel__error">最近错误：{{ monitorStatus.last_error }}</p>
      </div>
      <div class="listen-panel__controls">
        <label class="listen-panel__field">
          <span>每</span>
          <input v-model.number="listenIntervalMinutes" type="number" min="5" max="1440" step="5" />
          <span>分钟启动一次</span>
        </label>
        <label class="listen-panel__field">
          <span>时间窗口</span>
          <select v-model.number="lookbackHours" @change="saveListenSettings">
            <option v-for="option in lookbackOptions" :key="option.id" :value="option.id">
              {{ option.label }}
            </option>
          </select>
        </label>
        <button type="button" class="listen-panel__button" @click="saveListenSettings">
          保存频率
        </button>
        <button type="button" class="listen-panel__button listen-panel__button--ghost" @click="toggleAutoListening">
          {{ isAutoListening ? '暂停监听' : '开启监听' }}
        </button>
        <button type="button" class="listen-panel__button listen-panel__button--primary" :disabled="isRunning" @click="triggerBriefing">
          {{ isRunning ? '监听中...' : '立即监听' }}
        </button>
      </div>
      <p v-if="activeJob" class="listen-panel__job">
        后台任务：{{ activeJob.title }} · {{ activeJob.status }} · {{ activeJob.progress }}%
      </p>
      <p v-if="jobError" class="listen-panel__error">后台任务错误：{{ jobError }}</p>
    </section>

    <section class="monitor-console">
      <div class="monitor-card">
        <h3>最近运行</h3>
        <div v-if="monitorRuns.length" class="monitor-list">
          <div v-for="run in monitorRuns.slice(0, 3)" :key="run.run_id" class="monitor-row">
            <strong>{{ run.status }}</strong>
            <span>{{ formatDate(run.started_at) }}</span>
            <small>卡片 {{ run.card_count }} · 新讯息 {{ run.new_raw_count }} · 告警 {{ run.alert_count }}</small>
          </div>
        </div>
        <p v-else class="monitor-empty">暂无运行记录</p>
      </div>
      <div class="monitor-card">
        <h3>来源健康</h3>
        <div v-if="monitorStatus?.sources?.length" class="monitor-list">
          <div v-for="source in monitorStatus.sources.slice(0, 4)" :key="source.source_key" class="monitor-row">
            <strong>{{ source.source_name || source.source_key }}</strong>
            <span>{{ source.last_success_at ? '正常' : '等待采集' }}</span>
            <small>{{ source.last_item_count }} 条 · 失败 {{ source.failure_count }}</small>
          </div>
        </div>
        <p v-else class="monitor-empty">等待来源状态</p>
      </div>
      <div class="monitor-card">
        <h3>事件聚合</h3>
        <div v-if="monitorEvents.length" class="monitor-list">
          <div v-for="event in monitorEvents.slice(0, 3)" :key="event.event_id" class="monitor-row">
            <strong>{{ event.priority }} · {{ event.title }}</strong>
            <span>风险 {{ event.risk_score }} / 相关 {{ event.relevance_score }}</span>
            <small>{{ event.source_count }} 个来源 · {{ event.reason_codes.join('、') }}</small>
          </div>
        </div>
        <p v-else class="monitor-empty">暂无聚合事件</p>
      </div>
    </section>

    <section v-if="usageTrail.length" class="usage-trail">
      <div class="usage-trail__header">
        <h2>最近采集痕迹</h2>
        <span>近 {{ usageTrail.length }} 次监听运行</span>
      </div>
      <div class="usage-trail__list">
        <article v-for="item in usageTrail" :key="item.id" class="usage-trail__item">
          <strong>{{ item.title }}</strong>
          <span>{{ item.time }}</span>
          <small>{{ item.detail }}</small>
        </article>
      </div>
    </section>

    <!-- ── Dashboard Overview ──────────────────────────────── -->
    <section class="dashboard">
      <div class="stat-card stat-card--p0">
        <div class="stat-card__value">{{ stats?.P0 ?? 0 }}</div>
        <div class="stat-card__label">P0 紧急</div>
      </div>
      <div class="stat-card stat-card--p1">
        <div class="stat-card__value">{{ stats?.P1 ?? 0 }}</div>
        <div class="stat-card__label">P1 重要</div>
      </div>
      <div class="stat-card stat-card--p2">
        <div class="stat-card__value">{{ stats?.P2 ?? 0 }}</div>
        <div class="stat-card__label">P2 关注</div>
      </div>
      <div class="stat-card stat-card--weather">
        <div class="stat-card__value">{{ activeWeatherCount }}</div>
        <div class="stat-card__label">活跃天气警告</div>
      </div>
    </section>

    <!-- ── Filter Toolbar ──────────────────────────────────── -->
    <section class="filter-toolbar">
      <div class="filter-tabs">
        <button
          v-for="tab in categoryTabs"
          :key="tab.id"
          type="button"
          class="filter-tab"
          :class="{ 'filter-tab--active': filterCategory === tab.id }"
          @click="filterCategory = tab.id; fetchCards()"
        >
          <span v-if="tab.emoji" class="filter-tab__emoji">{{ tab.emoji }}</span>
          {{ tab.label }}
        </button>
      </div>

      <div class="filter-controls">
        <div class="filter-group">
          <span class="filter-label">优先级</span>
          <div class="filter-segments">
            <button
              v-for="opt in priorityOptions"
              :key="opt.id"
              type="button"
              class="filter-segment"
              :class="{ 'filter-segment--active': filterPriority === opt.id }"
              @click="filterPriority = opt.id; fetchCards()"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>

        <div class="filter-group">
          <span class="filter-label">日期</span>
          <input
            v-model="filterDateFrom"
            type="date"
            class="filter-date"
            @change="fetchCards"
          />
          <span class="filter-date-sep">~</span>
          <input
            v-model="filterDateTo"
            type="date"
            class="filter-date"
            @change="fetchCards"
          />
        </div>

        <div class="filter-group filter-group--search">
          <input
            v-model="filterKeyword"
            type="text"
            class="filter-search"
            placeholder="搜索关键词..."
            @keyup.enter="fetchCards"
          />
          <button class="filter-search__btn" @click="fetchCards">搜索</button>
        </div>
      </div>
    </section>

    <!-- ── Card Grid ───────────────────────────────────────── -->
    <section class="card-grid-area">
      <div class="card-grid-area__header">
        <h2>已采集讯息卡片 ({{ totalCollected }})</h2>
        <span>展示天气、官方监管与白名单媒体的结构化风险卡片</span>
      </div>
      <p v-if="cardsError" class="error-msg">{{ cardsError }}</p>
      <div v-if="cards.length === 0 && !loading" class="empty-state">
        当前筛选下暂无卡片。
        <template v-if="totalCollected">请调整筛选条件，或点击「立即监听」采集最新讯息。</template>
        <template v-else>点击「立即监听」开始首次采集。</template>
      </div>
      <div class="card-grid">
        <article
          v-for="card in cards"
          :key="card.card_id"
          class="risk-card"
          :class="cardClass(card)"
        >
          <!-- Card header: category icon + source name + priority badge -->
          <div class="risk-card__header">
            <div class="risk-card__source">
              <span class="risk-card__cat-icon">
                {{ card.source_category === 'weather' ? '\u{1F324}\u{FE0F}' : card.source_category === 'official' ? '\u{1F3DB}\u{FE0F}' : '\u{1F4F0}' }}
              </span>
              <span class="risk-card__source-name">{{ card.source_name }}</span>
            </div>
            <span class="priority-badge" :class="priorityClass(card.priority)">
              {{ priorityLabel(card.priority) }}
            </span>
          </div>

          <!-- Card body: emoji + title + meta + keywords -->
          <div class="risk-card__body">
            <h3 class="risk-card__title">
              <span class="risk-card__emoji">{{ card.emoji_tag }}</span>
              {{ card.title }}
            </h3>
            <div class="risk-card__meta">
              <span v-if="card.event_date" class="risk-card__date">
                {{ formatEventDate(card.event_date) }}
              </span>
              <span v-if="card.location" class="risk-card__location">
                {{ '\u00B7' }} {{ card.location }}
              </span>
            </div>
            <p v-if="card.summary" class="risk-card__summary">{{ card.summary }}</p>
            <div v-if="card.keywords.length" class="risk-card__keywords">
              <span v-for="kw in card.keywords" :key="kw" class="keyword-tag">
                #{{ kw }}
              </span>
            </div>
          </div>

          <!-- Card footer: recommended action + status + link -->
          <div class="risk-card__footer">
            <p v-if="card.recommended_action" class="risk-card__action">
              <span class="action-icon">{{ '\u{1F4A1}' }}</span>
              {{ card.recommended_action }}
            </p>
            <div class="risk-card__links">
              <span v-if="!card.is_confirmed" class="confirm-status confirm-status--pending">
                {{ '\u26A0\uFE0F' }} 待官方确认
              </span>
              <span v-else class="confirm-status confirm-status--confirmed">
                {{ '\u2705' }} 已确认
              </span>
              <a
                v-if="card.source_url"
                :href="card.source_url"
                target="_blank"
                rel="noreferrer"
                class="risk-card__source-link"
              >
                {{ '\u{1F517}' }} 查看原文
              </a>
            </div>
          </div>
        </article>
      </div>
    </section>

    <!-- ── Briefing Trigger Area ──────────────────────────── -->
    <section class="briefing-trigger">
      <div class="briefing-trigger__header" @click="showBriefingResult = !showBriefingResult">
        <h2>{{ '\u{1F4CB}' }} 外部讯息简报</h2>
        <span class="toggle-icon">{{ showBriefingResult ? '\u25BC' : '\u25B6' }}</span>
      </div>
      <div v-show="showBriefingResult || isRunning" class="briefing-trigger__body">
        <div class="briefing-form">
          <label class="briefing-form__field">
            <span>项目范围</span>
            <input v-model="area" type="text" />
          </label>
          <label class="briefing-form__field">
            <span>关注主题</span>
            <textarea v-model="focus" rows="2" />
          </label>
          <div class="briefing-form__field">
            <span>来源</span>
            <div class="briefing-form__sources">
              <button
                v-for="source in sourceOptions"
                :key="source.id"
                type="button"
                class="briefing-form__source"
                :class="{ 'briefing-form__source--active': selectedSources.includes(source.id) }"
                @click="toggleSource(source.id)"
              >
                {{ source.label }}
              </button>
            </div>
          </div>
          <div class="briefing-form__field">
            <span>输出</span>
            <div class="briefing-form__segments">
              <button
                type="button"
                :class="{ 'briefing-form__segment--active': deliveryMode === 'draft' }"
                @click="deliveryMode = 'draft'"
              >
                草稿
              </button>
              <button
                type="button"
                :class="{ 'briefing-form__segment--active': deliveryMode === 'feishu' }"
                @click="deliveryMode = 'feishu'"
              >
                飞书
              </button>
            </div>
          </div>
          <label v-if="deliveryMode === 'feishu'" class="briefing-form__field">
            <span>联系人或群</span>
            <input v-model="recipient" type="text" />
          </label>
          <button
            class="briefing-form__run"
            :disabled="isRunning"
            @click="triggerBriefing"
          >
            {{ isRunning ? '监听中...' : '手动生成简报' }}
          </button>
        </div>

        <div v-if="briefingText" class="briefing-result">
          <div class="briefing-result__summary">{{ responseSummary }}</div>
          <pre class="briefing-result__text">{{ briefingText }}</pre>
        </div>
        <p v-if="briefingError" class="error-msg">{{ briefingError }}</p>
      </div>
    </section>

    <!-- ── History Reports (collapsible) ──────────────────── -->
    <section class="history-section">
      <div class="history-section__header" @click="showHistory = !showHistory">
        <h2>{{ '\u{1F4DA}' }} 历史简报 ({{ historyReports.length }})</h2>
        <span class="toggle-icon">{{ showHistory ? '\u25BC' : '\u25B6' }}</span>
      </div>
      <div v-show="showHistory" class="history-section__body">
        <p v-if="historyError" class="error-msg">{{ historyError }}</p>
        <div v-if="historyReports.length === 0 && !historyError" class="empty-state">
          暂无历史简报。
        </div>
        <div class="history-list">
          <button
            v-for="report in historyReports"
            :key="report.report_id"
            type="button"
            class="history-item"
            @click="applyHistoryReport(report)"
          >
            <strong>{{ report.title }}</strong>
            <span>{{ formatDate(report.created_at) }}</span>
          </button>
        </div>
      </div>
    </section>
  </main>
</template>

<style scoped>
.risk-page {
  background: #0a0e1a;
  color: #e0e0e0;
  min-height: 100vh;
  padding: 24px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* ── Page Header ────────────────────────────────────────── */
.risk-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.risk-header__title {
  font-size: 28px;
  font-weight: 700;
  color: #f0f0f0;
  margin: 0;
}

.risk-header__datetime {
  font-size: 14px;
  color: #8892a6;
  margin: 4px 0 0;
}

.risk-header__usage {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--risk-muted);
}

.usage-trail {
  background: var(--risk-surface);
  border: 1px solid var(--risk-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-sm);
  margin-bottom: 20px;
  padding: 14px 16px;
}

.usage-trail__header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.usage-trail__header h2 {
  margin: 0;
  font-size: 15px;
  color: var(--risk-text);
}

.usage-trail__header span {
  color: var(--risk-faint);
  font-size: 12px;
}

.usage-trail__list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
}

.usage-trail__item {
  background: var(--risk-surface-soft);
  border: 1px solid var(--risk-border);
  border-radius: var(--radius-md);
  display: grid;
  gap: 2px;
  padding: 10px 12px;
}

.usage-trail__item strong {
  color: var(--risk-text);
  font-size: 13px;
}

.usage-trail__item span,
.usage-trail__item small {
  color: var(--risk-faint);
  font-size: 12px;
}

.card-grid-area__header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.card-grid-area__header h2 {
  margin: 0;
  font-size: 16px;
  color: var(--risk-text);
}

.card-grid-area__header span {
  color: var(--risk-faint);
  font-size: 12px;
}

.risk-header__refresh {
  background: #1a2332;
  border: 1px solid #2a3a52;
  border-radius: 8px;
  color: #e0e0e0;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  padding: 10px 20px;
  transition: all 0.2s;
}

.risk-header__refresh:hover:not(:disabled) {
  background: #243447;
  border-color: #3a5278;
}

.risk-header__refresh:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid #3a5278;
  border-top-color: #60a5fa;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ── Dashboard ──────────────────────────────────────────── */
.dashboard {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  border-radius: 12px;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  border: 1px solid transparent;
}

.stat-card--p0 {
  background: #3b1414;
  border-color: #5c1f1f;
}

.stat-card--p1 {
  background: #2e1a08;
  border-color: #4a2c10;
}

.stat-card--p2 {
  background: #0c2e1a;
  border-color: #1a4a2c;
}

.stat-card--weather {
  background: #0c2744;
  border-color: #1e4d7b;
}

.stat-card__value {
  font-size: 42px;
  font-weight: 800;
  line-height: 1;
}

.stat-card--p0 .stat-card__value { color: #ef4444; }
.stat-card--p1 .stat-card__value { color: #f97316; }
.stat-card--p2 .stat-card__value { color: #22c55e; }
.stat-card--weather .stat-card__value { color: #60a5fa; }

.stat-card__label {
  font-size: 13px;
  color: #a0aec0;
  margin-top: 8px;
}

/* ── Filter Toolbar ─────────────────────────────────────── */
.filter-toolbar {
  background: #0f1524;
  border: 1px solid #1a2332;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 20px;
}

.filter-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.filter-tab {
  background: #1a2332;
  border: 1px solid #2a3a52;
  border-radius: 8px;
  color: #8892a6;
  cursor: pointer;
  font-size: 14px;
  padding: 8px 16px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 6px;
}

.filter-tab:hover {
  background: #243447;
  color: #c0c8d8;
}

.filter-tab--active {
  background: #1a3a5c !important;
  border-color: #3a6a9a !important;
  color: #60a5fa !important;
}

.filter-tab__emoji {
  font-size: 16px;
}

.filter-controls {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
  align-items: flex-end;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.filter-group--search {
  flex-direction: row;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.filter-label {
  font-size: 12px;
  color: #6b7280;
  font-weight: 600;
}

.filter-segments {
  display: flex;
  gap: 4px;
}

.filter-segment {
  background: #1a2332;
  border: 1px solid #2a3a52;
  border-radius: 6px;
  color: #8892a6;
  cursor: pointer;
  font-size: 13px;
  padding: 6px 12px;
  transition: all 0.2s;
}

.filter-segment--active {
  background: #2a4a2a !important;
  border-color: #3a6a3a !important;
  color: #34d399 !important;
}

.filter-date {
  background: #1a2332;
  border: 1px solid #2a3a52;
  border-radius: 6px;
  color: #e0e0e0;
  font-size: 13px;
  padding: 6px 10px;
  color-scheme: dark;
}

.filter-date-sep {
  color: #6b7280;
  font-size: 13px;
}

.filter-search {
  background: #1a2332;
  border: 1px solid #2a3a52;
  border-radius: 6px;
  color: #e0e0e0;
  font-size: 13px;
  padding: 6px 12px;
  width: 200px;
}

.filter-search:focus {
  outline: none;
  border-color: #3a6a9a;
}

.filter-search__btn {
  background: #1a3a5c;
  border: 1px solid #3a6a9a;
  border-radius: 6px;
  color: #60a5fa;
  cursor: pointer;
  font-size: 13px;
  padding: 6px 14px;
  transition: all 0.2s;
}

.filter-search__btn:hover {
  background: #244a6c;
}

/* ── Card Grid ──────────────────────────────────────────── */
.card-grid-area {
  margin-bottom: 24px;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 16px;
}

.empty-state {
  color: #6b7280;
  font-size: 14px;
  padding: 40px;
  text-align: center;
}

.error-msg {
  color: #ef4444;
  font-size: 14px;
  padding: 12px;
  background: #2a1414;
  border-radius: 8px;
  border: 1px solid #5c1f1f;
  margin-bottom: 12px;
}

/* ── Risk Card ──────────────────────────────────────────── */
.risk-card {
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid;
  border-left: 4px solid;
  transition: all 0.2s ease;
  display: flex;
  flex-direction: column;
}

.risk-card:hover {
  transform: translateY(-2px);
  filter: brightness(1.08);
}

/* weather */
.risk-card--weather {
  background: #0c2744;
  border-color: #1e4d7b;
  border-left-color: #60a5fa;
}

/* official */
.risk-card--official {
  background: #0c2e22;
  border-color: #1a6b48;
  border-left-color: #34d399;
}

/* media */
.risk-card--media {
  background: #331f0a;
  border-color: #7a4f12;
  border-left-color: #fbbf24;
}

.risk-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.risk-card__source {
  display: flex;
  align-items: center;
  gap: 8px;
}

.risk-card__cat-icon {
  font-size: 18px;
}

.risk-card__source-name {
  font-size: 13px;
  color: #a0aec0;
  font-weight: 500;
}

.priority-badge {
  font-size: 12px;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 12px;
  color: #fff;
}

.priority-badge--P0 {
  background: #dc2626;
}

.priority-badge--P1 {
  background: #ea580c;
}

.priority-badge--P2 {
  background: #16a34a;
}

.risk-card__body {
  padding: 14px 16px;
  flex: 1;
}

.risk-card__title {
  font-size: 16px;
  font-weight: 600;
  color: #f0f0f0;
  margin: 0 0 8px;
  line-height: 1.4;
}

.risk-card__emoji {
  margin-right: 6px;
}

.risk-card__meta {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 8px;
}

.risk-card__date {
  margin-right: 4px;
}

.risk-card__summary {
  font-size: 13px;
  color: #a0aec0;
  line-height: 1.5;
  margin: 0 0 10px;
}

.risk-card__keywords {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.keyword-tag {
  font-size: 12px;
  color: #8892a6;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 4px;
  padding: 2px 8px;
}

.risk-card__footer {
  padding: 12px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.risk-card__action {
  font-size: 13px;
  color: #c0c8d8;
  margin: 0 0 8px;
  display: flex;
  align-items: flex-start;
  gap: 6px;
}

.action-icon {
  flex-shrink: 0;
}

.risk-card__links {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.confirm-status {
  font-size: 12px;
}

.confirm-status--pending {
  color: #fbbf24;
}

.confirm-status--confirmed {
  color: #34d399;
}

.risk-card__source-link {
  font-size: 12px;
  color: #60a5fa;
  text-decoration: none;
  transition: color 0.2s;
}

.risk-card__source-link:hover {
  color: #93c5fd;
}

/* ── Briefing Trigger ───────────────────────────────────── */
.briefing-trigger {
  background: #0f1524;
  border: 1px solid #1a2332;
  border-radius: 12px;
  margin-bottom: 20px;
  overflow: hidden;
}

.briefing-trigger__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  cursor: pointer;
  user-select: none;
}

.briefing-trigger__header h2 {
  font-size: 16px;
  font-weight: 600;
  color: #e0e0e0;
  margin: 0;
}

.toggle-icon {
  color: #6b7280;
  font-size: 12px;
}

.briefing-trigger__body {
  padding: 0 20px 20px;
}

.briefing-form {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

.briefing-form__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.briefing-form__field > span {
  font-size: 12px;
  color: #6b7280;
  font-weight: 600;
}

.briefing-form__field input,
.briefing-form__field textarea {
  background: #1a2332;
  border: 1px solid #2a3a52;
  border-radius: 8px;
  color: #e0e0e0;
  font: inherit;
  font-size: 14px;
  padding: 8px 12px;
  resize: vertical;
}

.briefing-form__field input:focus,
.briefing-form__field textarea:focus {
  outline: none;
  border-color: #3a6a9a;
}

.briefing-form__sources,
.briefing-form__segments {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.briefing-form__source,
.briefing-form__segments button {
  background: #1a2332;
  border: 1px solid #2a3a52;
  border-radius: 8px;
  color: #8892a6;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  padding: 6px 12px;
  transition: all 0.2s;
}

.briefing-form__source--active,
.briefing-form__segment--active {
  background: #1a3a5c !important;
  border-color: #3a6a9a !important;
  color: #60a5fa !important;
}

.briefing-form__run {
  grid-column: 1 / -1;
  background: #1a3a5c;
  border: 1px solid #3a6a9a;
  border-radius: 8px;
  color: #60a5fa;
  cursor: pointer;
  font-size: 15px;
  font-weight: 600;
  padding: 12px;
  transition: all 0.2s;
}

.briefing-form__run:hover:not(:disabled) {
  background: #244a6c;
}

.briefing-form__run:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.briefing-result {
  margin-top: 16px;
}

.briefing-result__summary {
  font-size: 14px;
  color: #a0aec0;
  margin-bottom: 8px;
}

.briefing-result__text {
  background: #0a0e1a;
  border: 1px solid #1a2332;
  border-radius: 8px;
  color: #dbeafe;
  font-size: 13px;
  line-height: 1.7;
  margin: 0;
  max-height: 400px;
  overflow: auto;
  padding: 14px;
  white-space: pre-wrap;
}

/* ── History Section ────────────────────────────────────── */
.history-section {
  background: #0f1524;
  border: 1px solid #1a2332;
  border-radius: 12px;
  overflow: hidden;
}

.history-section__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  cursor: pointer;
  user-select: none;
}

.history-section__header h2 {
  font-size: 16px;
  font-weight: 600;
  color: #e0e0e0;
  margin: 0;
}

.history-section__body {
  padding: 0 20px 20px;
}

.history-list {
  display: grid;
  gap: 8px;
}

.history-item {
  background: #1a2332;
  border: 1px solid #2a3a52;
  border-radius: 8px;
  cursor: pointer;
  display: grid;
  gap: 4px;
  padding: 10px 14px;
  text-align: left;
  transition: all 0.2s;
}

.history-item:hover {
  background: #243447;
  border-color: #3a5278;
}

.history-item strong {
  color: #e0e0e0;
  font-size: 14px;
}

.history-item span {
  color: #6b7280;
  font-size: 12px;
}

/* ── Theme Alignment Overrides ──────────────────────────── */
.risk-page {
  --risk-surface: var(--bg-white);
  --risk-surface-soft: var(--bg-subtle);
  --risk-surface-hover: var(--bg-hover);
  --risk-text: var(--text-primary);
  --risk-muted: var(--text-secondary);
  --risk-faint: var(--text-muted);
  --risk-border: var(--border-light);
  --risk-border-strong: var(--border-normal);
  --risk-accent: var(--brand-cyan);
  --risk-accent-soft: rgb(15 158 213 / 12%);
  --risk-success-soft: rgb(63 158 45 / 12%);
  --risk-warning-soft: rgb(233 113 50 / 13%);
  --risk-error-soft: rgb(231 0 18 / 12%);
  background: var(--bg-page);
  color: var(--risk-text);
  font-family: var(--font-family);
}

.risk-header__title,
.briefing-trigger__header h2,
.history-section__header h2,
.risk-card__title,
.history-item strong {
  color: var(--risk-text);
}

.risk-header__datetime,
.risk-card__source-name,
.risk-card__summary,
.briefing-result__summary,
.risk-card__action {
  color: var(--risk-muted);
}

.filter-label,
.briefing-form__field > span,
.risk-card__meta,
.filter-date-sep,
.toggle-icon,
.history-item span,
.empty-state,
.keyword-tag {
  color: var(--risk-faint);
}

.risk-header__actions,
.listen-panel__controls,
.listen-panel__field {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.listen-pill {
  border: 1px solid rgb(63 158 45 / 35%);
  border-radius: var(--radius-round);
  background: var(--risk-success-soft);
  color: var(--color-success);
  font-size: 12px;
  font-weight: 700;
  padding: 6px 10px;
}

.listen-pill--paused {
  border-color: rgb(233 113 50 / 35%);
  background: var(--risk-warning-soft);
  color: var(--color-warning);
}

.listen-panel {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  background: var(--risk-surface);
  border: 1px solid var(--risk-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-sm);
  margin-bottom: 20px;
  padding: 16px 18px;
}

.listen-panel h2 {
  color: var(--risk-text);
  font-size: 16px;
  margin: 0 0 4px;
}

.listen-panel p {
  color: var(--risk-muted);
  font-size: 13px;
}

.listen-panel__field {
  color: var(--risk-muted);
  font-size: 13px;
  white-space: nowrap;
}

.listen-panel__field input,
.listen-panel__field select {
  width: 82px;
  background: var(--risk-surface-soft);
  border: 1px solid var(--risk-border-strong);
  border-radius: var(--radius-md);
  color: var(--risk-text);
  padding: 6px 8px;
}

.listen-panel__error {
  color: var(--color-error) !important;
  margin-top: 6px;
}

.listen-panel__job {
  background: var(--risk-surface-soft);
  border: 1px solid var(--risk-border);
  border-radius: var(--radius-md);
  color: var(--risk-muted);
  padding: 6px 10px;
}

.listen-panel__button {
  background: var(--risk-surface-soft);
  border: 1px solid var(--risk-border-strong);
  border-radius: var(--radius-md);
  color: var(--risk-text);
  font-size: 13px;
  padding: 8px 12px;
}

.listen-panel__button:hover:not(:disabled) {
  background: var(--risk-surface-hover);
  border-color: var(--brand-cyan);
}

.listen-panel__button--ghost {
  color: var(--risk-muted);
}

.listen-panel__button--primary,
.briefing-form__run,
.filter-search__btn {
  background: var(--risk-accent-soft);
  border-color: rgb(15 158 213 / 35%);
  color: var(--risk-accent);
}

.listen-panel__button--primary:hover:not(:disabled),
.briefing-form__run:hover:not(:disabled),
.filter-search__btn:hover {
  background: rgb(15 158 213 / 18%);
}

.monitor-console {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 20px;
}

.monitor-card {
  background: var(--risk-surface);
  border: 1px solid var(--risk-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-sm);
  padding: 14px;
}

.monitor-card h3 {
  color: var(--risk-text);
  font-size: 14px;
  margin: 0 0 10px;
}

.monitor-list {
  display: grid;
  gap: 8px;
}

.monitor-row {
  background: var(--risk-surface-soft);
  border: 1px solid var(--risk-border);
  border-radius: var(--radius-md);
  display: grid;
  gap: 2px;
  padding: 9px 10px;
}

.monitor-row strong {
  color: var(--risk-text);
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.monitor-row span,
.monitor-row small,
.monitor-empty {
  color: var(--risk-faint);
  font-size: 12px;
}

.risk-header__refresh,
.filter-toolbar,
.briefing-trigger,
.history-section,
.risk-card,
.history-item,
.filter-tab,
.filter-segment,
.filter-date,
.filter-search,
.briefing-form__field input,
.briefing-form__field textarea,
.briefing-form__source,
.briefing-form__segments button,
.briefing-result__text {
  background: var(--risk-surface);
  border-color: var(--risk-border);
  color: var(--risk-text);
  box-shadow: var(--shadow-xs);
}

.risk-header__refresh:hover:not(:disabled),
.filter-tab:hover,
.history-item:hover {
  background: var(--risk-surface-hover);
  border-color: var(--risk-border-strong);
  color: var(--risk-text);
}

.filter-tab--active,
.briefing-form__source--active,
.briefing-form__segment--active {
  background: var(--risk-accent-soft) !important;
  border-color: rgb(15 158 213 / 35%) !important;
  color: var(--risk-accent) !important;
}

.filter-segment--active {
  background: var(--risk-success-soft) !important;
  border-color: rgb(63 158 45 / 35%) !important;
  color: var(--color-success) !important;
}

.stat-card {
  box-shadow: var(--shadow-sm);
}

.stat-card--p0 {
  background: var(--risk-error-soft);
  border-color: rgb(231 0 18 / 24%);
}

.stat-card--p1,
.risk-card--media {
  background: var(--risk-warning-soft);
  border-color: rgb(233 113 50 / 24%);
}

.stat-card--p2,
.risk-card--official {
  background: var(--risk-success-soft);
  border-color: rgb(63 158 45 / 24%);
}

.stat-card--weather,
.risk-card--weather {
  background: var(--risk-accent-soft);
  border-color: rgb(15 158 213 / 24%);
}

.risk-card__header,
.risk-card__footer {
  border-color: var(--risk-border);
}

.keyword-tag {
  background: var(--risk-surface-soft);
}

.error-msg {
  background: var(--risk-error-soft);
  border-color: rgb(231 0 18 / 30%);
  color: var(--color-error);
}

.filter-date {
  color-scheme: light;
}

:global(:root[data-theme='dark']) .filter-date {
  color-scheme: dark;
}

/* ── Responsive ─────────────────────────────────────────── */
@media (max-width: 900px) {
  .dashboard {
    grid-template-columns: repeat(2, 1fr);
  }

  .filter-controls {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .filter-group--search {
    margin-left: 0;
  }

  .briefing-form {
    grid-template-columns: 1fr;
  }

  .listen-panel {
    align-items: flex-start;
    flex-direction: column;
  }

  .monitor-console {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 600px) {
  .dashboard {
    grid-template-columns: 1fr;
  }

  .card-grid {
    grid-template-columns: 1fr;
  }
}
</style>
