<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { listExternalRiskBriefingReports, sendChatMessage } from '../services/chitungApi'
import type { ExternalRiskBriefingReport } from '../types/domain'

type StepStatus = 'pending' | 'active' | 'done' | 'failed'

interface MonitorStep {
  id: string
  label: string
  tool: string
  status: StepStatus
  detail: string
}

interface ReportImage {
  title: string
  url: string
  caption?: string
}

interface ReportLink {
  title: string
  source: string
  url?: string
}

const sourceOptions = [
  { id: 'weather', label: '香港天文台' },
  { id: 'official', label: '官方安全更新' },
  { id: 'media', label: '白名单媒体' },
]

const baseSteps: MonitorStep[] = [
  { id: 'weather', label: '天气预警', tool: 'fetch_hko_weather', status: 'pending', detail: '待运行' },
  { id: 'updates', label: '安全新闻', tool: 'fetch_hk_safety_updates', status: 'pending', detail: '待运行' },
  { id: 'persist', label: '风险入库', tool: 'persist_external_risk_items', status: 'pending', detail: '待运行' },
  { id: 'briefing', label: '生成简报', tool: 'draft_daily_risk_briefing', status: 'pending', detail: '待运行' },
]

const area = ref('香港项目')
const focus = ref('施工安全、天气预警、工伤意外')
const selectedSources = ref(['weather', 'official', 'media'])
const deliveryMode = ref<'draft' | 'feishu'>('draft')
const recipient = ref('项目安全群')
const isRunning = ref(false)
const error = ref('')
const responseSummary = ref('')
const briefingText = ref('')
const toolResults = ref<Array<Record<string, unknown>>>([])
const reportImages = ref<ReportImage[]>([])
const reportLinks = ref<ReportLink[]>([])
const steps = ref<MonitorStep[]>(copySteps())
const briefingHistory = ref<ExternalRiskBriefingReport[]>([])
const selectedReportId = ref<number | null>(null)
const historyError = ref('')

const hasResult = computed(() => Boolean(responseSummary.value || briefingText.value || reportImages.value.length))

function copySteps(): MonitorStep[] {
  return baseSteps.map((step) => ({ ...step }))
}

function toggleSource(sourceId: string) {
  if (selectedSources.value.includes(sourceId)) {
    selectedSources.value = selectedSources.value.filter((item) => item !== sourceId)
  } else {
    selectedSources.value = [...selectedSources.value, sourceId]
  }
}

function buildPrompt() {
  const sourceText = sourceOptions
    .filter((source) => selectedSources.value.includes(source.id))
    .map((source) => source.label)
    .join('、')
  const deliveryText = deliveryMode.value === 'feishu' ? `生成后准备发送到飞书：${recipient.value}` : '只生成草稿'
  return `生成今日外部风险简报。项目范围：${area.value}。关注：${focus.value}。来源：${sourceText || '默认白名单来源'}。${deliveryText}。`
}

async function runMonitor() {
  if (isRunning.value) return
  isRunning.value = true
  error.value = ''
  responseSummary.value = ''
  briefingText.value = ''
  toolResults.value = []
  reportImages.value = []
  reportLinks.value = []
  selectedReportId.value = null
  steps.value = copySteps().map((step, index) => ({
    ...step,
    status: index === 0 ? 'active' : 'pending',
    detail: index === 0 ? '运行中' : '等待前序步骤',
  }))

  try {
    const response = await sendChatMessage({
      message: buildPrompt(),
      context: {
        entry: 'external_risk_monitor_page',
        area: area.value,
        focus: focus.value,
        sources: selectedSources.value,
        delivery_mode: deliveryMode.value,
        recipient: deliveryMode.value === 'feishu' ? recipient.value : '',
      },
    })
    responseSummary.value = response.message
    toolResults.value = (response.payload?.toolResults as Array<Record<string, unknown>> | undefined) ?? []
    const cards = (response.payload?.cards as Array<Record<string, unknown>> | undefined) ?? []
    const externalCard = cards.find((card) => card.card_type === 'external_risk_briefing')
    const cardData = (externalCard?.data as Record<string, unknown> | undefined) ?? {}

    briefingText.value = extractBriefingText(cardData, toolResults.value)
    reportImages.value = extractReportImages(cardData, toolResults.value)
    reportLinks.value = extractReportLinks(cardData, toolResults.value)
    steps.value = resolveSteps(toolResults.value)
    const reportId = Number(
      cardData.briefing_report_id ||
        ((cardData.briefing_report as Record<string, unknown> | undefined)?.report_id ?? 0),
    )
    await loadBriefingHistory()
    if (reportId) {
      const saved = briefingHistory.value.find((item) => item.report_id === reportId)
      if (saved) applyBriefingRecord(saved)
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
    steps.value = steps.value.map((step) =>
      step.status === 'active' ? { ...step, status: 'failed', detail: '执行失败' } : step,
    )
  } finally {
    isRunning.value = false
  }
}

async function loadBriefingHistory() {
  historyError.value = ''
  try {
    briefingHistory.value = await listExternalRiskBriefingReports(20)
    if (!briefingText.value && briefingHistory.value[0]) {
      applyBriefingRecord(briefingHistory.value[0])
    }
  } catch (err) {
    historyError.value = err instanceof Error ? err.message : String(err)
  }
}

function applyBriefingRecord(report: ExternalRiskBriefingReport) {
  selectedReportId.value = report.report_id
  responseSummary.value = report.summary || '已加载历史简报'
  briefingText.value = report.briefing_text
  reportImages.value = report.report_images ?? []
  reportLinks.value = report.report_links ?? []
  toolResults.value = report.tool_results ?? []
}

function formatDate(value: string) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

function resolveSteps(results: Array<Record<string, unknown>>): MonitorStep[] {
  return baseSteps.map((step) => {
    const result = results.find((item) => item.tool_name === step.tool || item.tool === step.tool || item.source === step.tool)
    if (!result) return { ...step, status: 'done', detail: '中台已处理' }
    const ok = result.ok !== false
    const summary = summarizeResult(result)
    return { ...step, status: ok ? 'done' : 'failed', detail: summary }
  })
}

function summarizeResult(result: Record<string, unknown>) {
  const summary = result.summary
  if (typeof summary === 'string') return summary
  if (summary && typeof summary === 'object') {
    const value = summary as Record<string, unknown>
    if (typeof value.matched_item_count === 'number') return `匹配 ${value.matched_item_count} 条`
    if (typeof value.item_count === 'number') return `入库 ${value.item_count} 条`
    if (typeof value.total_items === 'number') return `汇总 ${value.total_items} 条`
    if (typeof value.report_image_count === 'number') return `配图 ${value.report_image_count} 张`
  }
  if (typeof result.error === 'string') return result.error
  return '已完成'
}

function extractBriefingText(cardData: Record<string, unknown>, results: Array<Record<string, unknown>>) {
  const direct = cardData.briefing_text
  if (typeof direct === 'string' && direct.trim()) return direct.trim()

  const briefing = cardData.briefing
  const fromCard = textFromToolResult(briefing)
  if (fromCard) return fromCard

  const result = results.find((item) => item.tool === 'draft_daily_risk_briefing' || item.source === 'draft_daily_risk_briefing')
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

function extractReportImages(cardData: Record<string, unknown>, results: Array<Record<string, unknown>>): ReportImage[] {
  const candidates = [
    cardData.report_images,
    cardData.images,
    cardData.briefing,
    ...results,
  ]
  const images: ReportImage[] = []
  for (const candidate of candidates) {
    if (!candidate || typeof candidate !== 'object') continue
    const value = candidate as Record<string, unknown>
    const rawImages = Array.isArray(value.report_images)
      ? value.report_images
      : Array.isArray(value.images)
        ? value.images
        : []
    for (const rawImage of rawImages) {
      if (!rawImage || typeof rawImage !== 'object') continue
      const item = rawImage as Record<string, unknown>
      const url = String(item.url || item.image_url || item.path || '')
      if (!url) continue
      images.push({
        title: String(item.title || item.source || '简报配图'),
        url,
        caption: typeof item.caption === 'string' ? item.caption : undefined,
      })
    }
  }
  return images.slice(0, 6)
}

function extractReportLinks(cardData: Record<string, unknown>, results: Array<Record<string, unknown>>): ReportLink[] {
  const updateResult = cardData.updates || results.find((item) => item.tool === 'fetch_hk_safety_updates' || item.source === 'hk_safety_updates')
  if (!updateResult || typeof updateResult !== 'object') return []
  const items = Array.isArray((updateResult as Record<string, unknown>).items)
    ? ((updateResult as Record<string, unknown>).items as Array<Record<string, unknown>>)
    : []
  return items.slice(0, 8).map((item) => ({
    title: String(item.title || '外部更新'),
    source: String(item.source_name || item.source || '外部来源'),
    url: typeof item.url === 'string' ? item.url : undefined,
  }))
}

onMounted(loadBriefingHistory)
</script>

<template>
  <main class="workbench external-monitor">
    <section class="hero-panel external-monitor__hero">
      <div>
        <p class="eyebrow">Yaoyao External Risk</p>
        <h1>外部舆情监听</h1>
        <p>天气、官方安全更新和白名单媒体统一进入风险简报流程。</p>
      </div>
      <button class="primary-soft-button" :disabled="isRunning" @click="runMonitor">
        {{ isRunning ? '监听中' : '生成简报' }}
      </button>
    </section>

    <section class="external-monitor__layout">
      <section class="panel external-monitor__config">
        <div class="panel__header">
          <div>
            <h2>监听配置</h2>
            <p>运行时参数</p>
          </div>
        </div>

        <label class="external-monitor__field">
          <span>项目范围</span>
          <input v-model="area" type="text" />
        </label>

        <label class="external-monitor__field">
          <span>关注主题</span>
          <textarea v-model="focus" rows="3" />
        </label>

        <div class="external-monitor__field">
          <span>来源</span>
          <div class="external-monitor__source-list">
            <button
              v-for="source in sourceOptions"
              :key="source.id"
              type="button"
              class="external-monitor__source"
              :class="{ 'external-monitor__source--active': selectedSources.includes(source.id) }"
              @click="toggleSource(source.id)"
            >
              {{ source.label }}
            </button>
          </div>
        </div>

        <div class="external-monitor__field">
          <span>输出</span>
          <div class="external-monitor__segmented">
            <button
              type="button"
              :class="{ 'external-monitor__segment--active': deliveryMode === 'draft' }"
              @click="deliveryMode = 'draft'"
            >
              草稿
            </button>
            <button
              type="button"
              :class="{ 'external-monitor__segment--active': deliveryMode === 'feishu' }"
              @click="deliveryMode = 'feishu'"
            >
              飞书
            </button>
          </div>
        </div>

        <label v-if="deliveryMode === 'feishu'" class="external-monitor__field">
          <span>联系人或群</span>
          <input v-model="recipient" type="text" />
        </label>
      </section>

      <section class="panel external-monitor__process">
        <div class="panel__header">
          <div>
            <h2>执行过程</h2>
            <p>{{ isRunning ? '中台正在调用工具链' : '最近一次运行' }}</p>
          </div>
        </div>

        <ol class="external-monitor__steps">
          <li
            v-for="step in steps"
            :key="step.id"
            class="external-monitor__step"
            :class="`external-monitor__step--${step.status}`"
          >
            <span class="external-monitor__step-dot" />
            <div>
              <strong>{{ step.label }}</strong>
              <p>{{ step.detail }}</p>
            </div>
          </li>
        </ol>

        <p v-if="error" class="external-monitor__error">{{ error }}</p>
      </section>
    </section>

    <section class="external-monitor__layout external-monitor__layout--results">
      <section class="panel external-monitor__history">
        <div class="panel__header">
          <div>
            <h2>历史简报</h2>
            <p>{{ briefingHistory.length }} 份已存储</p>
          </div>
        </div>
        <div class="external-monitor__history-list">
          <button
            v-for="report in briefingHistory"
            :key="report.report_id"
            type="button"
            class="external-monitor__history-item"
            :class="{ 'external-monitor__history-item--active': selectedReportId === report.report_id }"
            @click="applyBriefingRecord(report)"
          >
            <strong>{{ report.title }}</strong>
            <span>{{ formatDate(report.created_at) }}</span>
          </button>
          <p v-if="!briefingHistory.length && !historyError" class="smart-form-empty">暂无历史简报。</p>
          <p v-if="historyError" class="external-monitor__error">{{ historyError }}</p>
        </div>
      </section>
      <section class="panel external-monitor__briefing">
        <div class="panel__header">
          <div>
            <h2>简报结果</h2>
            <p>{{ responseSummary || '尚未运行' }}</p>
          </div>
        </div>
        <pre v-if="briefingText" class="external-monitor__briefing-text">{{ briefingText }}</pre>
        <div v-if="reportImages.length" class="external-monitor__image-grid">
          <figure v-for="image in reportImages" :key="image.url" class="external-monitor__image">
            <img :src="image.url" :alt="image.title" />
            <figcaption>{{ image.caption || image.title }}</figcaption>
          </figure>
        </div>
        <div v-if="reportLinks.length" class="external-monitor__source-links">
          <a
            v-for="item in reportLinks"
            :key="`${item.source}-${item.title}`"
            :href="item.url || '#'"
            target="_blank"
            rel="noreferrer"
          >
            <strong>{{ item.title }}</strong>
            <span>{{ item.source }}</span>
          </a>
        </div>
        <p v-if="!briefingText && !reportImages.length && !reportLinks.length" class="smart-form-empty">
          {{ hasResult ? '中台已返回结果，暂无完整简报文本。' : '运行后显示每日外部风险简报。' }}
        </p>
      </section>
    </section>
  </main>
</template>

<style scoped>
.external-monitor__hero {
  border-color: rgba(20, 184, 166, 0.28);
}

.external-monitor__layout {
  display: grid;
  gap: 16px;
  grid-template-columns: minmax(280px, 0.86fr) minmax(360px, 1.14fr);
  margin-bottom: 16px;
}

.external-monitor__layout--results {
  grid-template-columns: minmax(260px, 0.34fr) minmax(420px, 1fr);
}

.external-monitor__config,
.external-monitor__process,
.external-monitor__history,
.external-monitor__briefing {
  border-radius: 8px;
}

.external-monitor__history-list {
  display: grid;
  gap: 8px;
}

.external-monitor__history-item {
  background: #ffffff;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  cursor: pointer;
  display: grid;
  gap: 4px;
  padding: 10px;
  text-align: left;
}

.external-monitor__history-item strong {
  color: var(--text-main);
  font-size: 14px;
}

.external-monitor__history-item span {
  color: var(--text-secondary);
  font-size: 12px;
}

.external-monitor__history-item--active {
  border-color: rgba(20, 184, 166, 0.55);
  box-shadow: inset 3px 0 0 #14b8a6;
}

.external-monitor__field {
  display: grid;
  gap: 8px;
  margin-top: 14px;
}

.external-monitor__field > span {
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 700;
}

.external-monitor__field input,
.external-monitor__field textarea {
  background: #ffffff;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  color: var(--text-main);
  font: inherit;
  padding: 10px 12px;
  resize: vertical;
}

.external-monitor__source-list,
.external-monitor__segmented {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.external-monitor__source,
.external-monitor__segmented button {
  background: var(--bg-subtle);
  border: 1px solid var(--border-light);
  border-radius: 8px;
  color: var(--text-secondary);
  cursor: pointer;
  font: inherit;
  padding: 8px 10px;
}

.external-monitor__source--active,
.external-monitor__segment--active {
  background: rgba(20, 184, 166, 0.13) !important;
  border-color: rgba(20, 184, 166, 0.55) !important;
  color: #0f766e !important;
}

.external-monitor__steps {
  display: grid;
  gap: 10px;
  list-style: none;
  margin: 0;
  padding: 0;
}

.external-monitor__step {
  align-items: center;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  display: grid;
  gap: 10px;
  grid-template-columns: 12px 1fr;
  padding: 10px;
}

.external-monitor__step strong {
  color: var(--text-main);
  display: block;
  margin-bottom: 2px;
}

.external-monitor__step p {
  color: var(--text-secondary);
  margin: 0;
}

.external-monitor__step-dot {
  background: var(--text-muted);
  border-radius: 999px;
  height: 10px;
  width: 10px;
}

.external-monitor__step--active .external-monitor__step-dot {
  background: #f59e0b;
}

.external-monitor__step--done .external-monitor__step-dot {
  background: #14b8a6;
}

.external-monitor__step--failed .external-monitor__step-dot {
  background: #ef4444;
}

.external-monitor__error {
  color: var(--color-error);
  margin-top: 12px;
}

.external-monitor__briefing-text {
  background: #0f172a;
  border-radius: 8px;
  color: #dbeafe;
  line-height: 1.7;
  margin: 0;
  max-height: 440px;
  overflow: auto;
  padding: 14px;
  white-space: pre-wrap;
}

.external-monitor__image-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  margin-top: 14px;
}

.external-monitor__image {
  border: 1px solid var(--border-light);
  border-radius: 8px;
  margin: 0;
  overflow: hidden;
}

.external-monitor__image img {
  aspect-ratio: 16 / 9;
  background: var(--bg-subtle);
  display: block;
  object-fit: cover;
  width: 100%;
}

.external-monitor__image figcaption {
  color: var(--text-secondary);
  font-size: 13px;
  padding: 8px 10px;
}

.external-monitor__source-links {
  display: grid;
  gap: 8px;
  margin-top: 14px;
}

.external-monitor__source-links a {
  border: 1px solid var(--border-light);
  border-radius: 8px;
  display: flex;
  gap: 10px;
  justify-content: space-between;
  padding: 10px;
  text-decoration: none;
}

.external-monitor__source-links span {
  color: var(--text-secondary);
  font-size: 12px;
}

@media (max-width: 1180px) {
  .external-monitor__layout,
  .external-monitor__layout--results {
    grid-template-columns: 1fr;
  }
}
</style>
