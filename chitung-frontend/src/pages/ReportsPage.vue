<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { generateReport } from '../services/chitungApi'
import type { GeneratedOutputItem } from '../types/domain'

/**
 * ReportsPage — 报告生成页
 * P1-7: 报告持久化到 localStorage（最多50条）
 * P2-5: 三种报告类型改为卡片选择
 * P1-6: 骨架屏
 */

const STORAGE_KEY = 'docmate-reports'
const MAX_REPORTS = 50

const isGenerating = ref(false)
const outputs = ref<GeneratedOutputItem[]>([])
const note = ref('选择一种报告类型开始生成。')

// P2-5: 报告类型卡片配置
const reportTypes = [
  {
    type: 'daily_safety' as const,
    title: '安全日报',
    icon: '\u{1F4CA}',
    description: '汇总当日安全巡检结果、隐患发现和处理情况',
    useCase: '适用于每日安全例会汇报、项目日志归档',
  },
  {
    type: 'rectification' as const,
    title: '整改报告',
    icon: '\u{1F527}',
    description: '针对具体隐患的整改措施、完成情况和验收记录',
    useCase: '适用于隐患闭环管理、整改通知回复',
  },
  {
    type: 'community' as const,
    title: '社区报告',
    icon: '\u{1F3D7}',
    description: '社区建设相关的安全报告，DOCX 格式输出',
    useCase: '适用于社区安全宣传、月度总结',
  },
]

// P1-7: localStorage 持久化
function loadFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as GeneratedOutputItem[]
      if (Array.isArray(parsed)) {
        outputs.value = parsed.slice(0, MAX_REPORTS)
      }
    }
  } catch {
    // 静默忽略解析失败
  }
}

function saveToStorage() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(outputs.value.slice(0, MAX_REPORTS)))
  } catch {
    // 静默忽略存储失败
  }
}

function rememberOutput(item: Omit<GeneratedOutputItem, 'id' | 'createdAt'>) {
  outputs.value = [
    {
      ...item,
      id: `${item.kind}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      createdAt: new Date().toLocaleString('zh-CN', { hour12: false }),
    },
    ...outputs.value,
  ].slice(0, MAX_REPORTS)
  saveToStorage()
}

async function handleGenerateReport(reportType: 'community' | 'daily_safety' | 'rectification') {
  isGenerating.value = true
  note.value = '正在生成报告...'
  try {
    const config = reportTypes.find((r) => r.type === reportType)
    const title = config?.title || '报告'
    const report = await generateReport({ reportType, title })
    note.value = report.message
    if (report.output_path) {
      rememberOutput({
        title: report.message || title,
        kind: report.output_path.endsWith('.docx') ? 'docx' : 'report',
        path: report.output_path,
      })
    }
  } catch (error) {
    note.value = `报告生成失败：${error instanceof Error ? error.message : String(error)}`
  } finally {
    isGenerating.value = false
  }
}

// P1-7: 补充操作
function handleDelete(id: string) {
  outputs.value = outputs.value.filter((item) => item.id !== id)
  saveToStorage()
}

async function handleRegenerate(item: GeneratedOutputItem) {
  const reportType = item.kind === 'docx' ? 'community' : item.title.includes('整改') ? 'rectification' : 'daily_safety'
  await handleGenerateReport(reportType as 'community' | 'rectification' | 'daily_safety')
}

async function openPath(path?: string) {
  if (!path || !window.chitungDesktop) return
  await window.chitungDesktop.openPath(path)
}

async function showInFolder(path?: string) {
  if (!path || !window.chitungDesktop) return
  await window.chitungDesktop.showInFolder(path)
}

function formatKind(kind: string): string {
  const labels: Record<string, string> = {
    docx: 'Word 文档',
    report: '报告',
    payload: '数据',
    image: '图片',
    notification: '通知',
    other: '其他',
  }
  return labels[kind] || kind
}

onMounted(loadFromStorage)
</script>

<template>
  <main class="workbench">
    <section class="hero-panel">
      <div>
        <p class="eyebrow">Reports</p>
        <h1>报告生成</h1>
        <p>安全日报、整改报告和社区报告在这里生成、打开和定位。</p>
      </div>
      <div class="hero-panel__status">
        <span class="status-dot" :class="isGenerating ? 'status-dot--orange' : 'status-dot--green'" />
        {{ isGenerating ? '生成中' : '就绪' }}
      </div>
    </section>

    <!-- P2-5: 卡片选择 -->
    <section class="panel report-generator-panel">
      <div class="panel__header">
        <div>
          <h2>选择报告类型</h2>
          <p>{{ note }}</p>
        </div>
      </div>
      <div class="report-type-cards">
        <article
          v-for="rt in reportTypes"
          :key="rt.type"
          class="report-type-card"
          :class="{ 'report-type-card--disabled': isGenerating }"
          @click="!isGenerating && handleGenerateReport(rt.type)"
        >
          <div class="report-type-card__icon">{{ rt.icon }}</div>
          <div class="report-type-card__body">
            <h3>{{ rt.title }}</h3>
            <p class="report-type-card__desc">{{ rt.description }}</p>
            <p class="report-type-card__usecase">{{ rt.useCase }}</p>
          </div>
          <button class="report-type-card__btn" :disabled="isGenerating">
            {{ isGenerating ? '生成中...' : '生成' }}
          </button>
        </article>
      </div>
    </section>

    <!-- P1-7: 持久化产物列表 -->
    <section class="panel output-history-panel">
      <div class="panel__header">
        <div>
          <h2>已生成文件</h2>
          <p>最多保留 {{ MAX_REPORTS }} 条记录，页面刷新后仍然保留</p>
        </div>
        <span class="output-count">{{ outputs.length }} / {{ MAX_REPORTS }}</span>
      </div>

      <!-- 骨架屏 (P1-6) -->
      <div v-if="isGenerating && !outputs.length" class="skeleton-area">
        <div v-for="i in 2" :key="i" class="skeleton-card">
          <div class="skeleton-bar skeleton-bar--title"></div>
          <div class="skeleton-bar skeleton-bar--text"></div>
          <div class="skeleton-bar skeleton-bar--text" style="width: 70%"></div>
        </div>
      </div>

      <div v-else class="output-history-list">
        <article v-for="item in outputs" :key="item.id" class="output-history-row">
          <div class="output-history-row__info">
            <strong>{{ item.title }}</strong>
            <p>{{ item.path || item.content || '暂无路径' }}</p>
            <small>{{ formatKind(item.kind) }} · {{ item.createdAt }}</small>
          </div>
          <div class="output-history-actions">
            <button v-if="item.path" class="mini-button" @click="openPath(item.path)">打开</button>
            <button v-if="item.path" class="mini-button" @click="showInFolder(item.path)">定位</button>
            <button class="mini-button" @click="handleRegenerate(item)">重新生成</button>
            <button class="mini-button mini-button--danger" @click="handleDelete(item.id)">删除</button>
          </div>
        </article>

        <!-- 空状态 (P1-4) -->
        <div v-if="!outputs.length" class="output-empty">
          <div class="output-empty__icon">&#128203;</div>
          <p class="output-empty__title">暂无生成文件</p>
          <p class="output-empty__hint">选择上方报告类型，开始生成第一份报告</p>
        </div>
      </div>
    </section>
  </main>
</template>

<style scoped>
.workbench {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: 100%;
  overflow-y: auto;
  padding: 16px;
}

.hero-panel {
  align-items: center;
  background: var(--bg-white, #fff);
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-xl, 16px);
  box-shadow: var(--shadow-sm, 0 1px 3px rgba(0,0,0,0.06));
  display: flex;
  justify-content: space-between;
  padding: 16px 20px;
}

.hero-panel h1 {
  color: var(--text-primary, #1a1d23);
  font-size: 20px;
  margin: 4px 0;
}

.eyebrow {
  color: var(--brand-cyan, #0f9ed5);
  font-size: 11px;
  letter-spacing: 0.08em;
  margin: 0;
  text-transform: uppercase;
}

.hero-panel p {
  color: var(--text-secondary, #5b626c);
  font-size: 12px;
  margin: 0;
}

.hero-panel__status {
  align-items: center;
  display: flex;
  font-size: 12px;
  gap: 6px;
}

.status-dot {
  border-radius: 50%;
  display: inline-block;
  height: 8px;
  width: 8px;
}

.status-dot--green {
  background: var(--risk-low, #43A047);
}

.status-dot--orange {
  background: var(--risk-medium, #FB8C00);
}

/* Panel */
.panel {
  background: var(--bg-white, #fff);
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-xl, 16px);
  box-shadow: var(--shadow-sm, 0 1px 3px rgba(0,0,0,0.06));
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
}

.panel__header {
  align-items: flex-start;
  display: flex;
  justify-content: space-between;
}

.panel__header h2 {
  color: var(--text-primary, #1a1d23);
  font-size: 16px;
  margin: 0;
}

.panel__header p {
  color: var(--text-secondary, #5b626c);
  font-size: 12px;
  margin: 4px 0 0;
}

.output-count {
  background: var(--bg-subtle, #f5f7fa);
  border-radius: 999px;
  color: var(--text-secondary, #5b626c);
  font-size: 11px;
  padding: 3px 10px;
}

/* P2-5: 报告类型卡片 */
.report-type-cards {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(3, 1fr);
}

.report-type-card {
  background: var(--bg-subtle, #f5f7fa);
  border: 1.5px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-lg, 12px);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  transition: all 150ms ease;
}

.report-type-card:hover {
  border-color: var(--brand-cyan, #0f9ed5);
  box-shadow: var(--shadow-sm, 0 2px 8px rgba(15, 158, 213, 0.12));
}

.report-type-card--disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.report-type-card__icon {
  font-size: 32px;
}

.report-type-card__body h3 {
  color: var(--text-primary, #1a1d23);
  font-size: 15px;
  margin: 0 0 4px;
}

.report-type-card__desc {
  color: var(--text-secondary, #5b626c);
  font-size: 12px;
  line-height: 1.5;
  margin: 0 0 4px;
}

.report-type-card__usecase {
  color: var(--text-muted, #9ca3af);
  font-size: 11px;
  line-height: 1.5;
  margin: 0;
}

.report-type-card__btn {
  background: var(--brand-cyan, #0f9ed5);
  border: none;
  border-radius: var(--radius-md, 8px);
  color: var(--text-white, #fff);
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  margin-top: auto;
  padding: 8px 16px;
}

.report-type-card__btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

/* 产物列表 */
.output-history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.output-history-row {
  align-items: center;
  background: var(--bg-subtle, #f5f7fa);
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-md, 8px);
  display: flex;
  gap: 12px;
  justify-content: space-between;
  padding: 12px;
}

.output-history-row__info strong {
  color: var(--text-primary, #1a1d23);
  display: block;
  font-size: 13px;
}

.output-history-row__info p {
  color: var(--text-secondary, #5b626c);
  font-size: 12px;
  margin: 2px 0;
  word-break: break-all;
}

.output-history-row__info small {
  color: var(--text-muted, #9ca3af);
  font-size: 11px;
}

.output-history-actions {
  display: flex;
  flex-shrink: 0;
  flex-wrap: wrap;
  gap: 4px;
  justify-content: flex-end;
}

.mini-button {
  background: var(--bg-white, #fff);
  border: 1px solid var(--border-normal, #d0d5dd);
  border-radius: var(--radius-sm, 4px);
  color: var(--text-secondary, #5b626c);
  cursor: pointer;
  font-size: 11px;
  padding: 5px 10px;
  white-space: nowrap;
}

.mini-button:hover {
  border-color: var(--brand-cyan, #0f9ed5);
  color: var(--brand-cyan, #0f9ed5);
}

.mini-button--danger {
  border-color: rgba(229, 57, 53, 0.3);
  color: var(--risk-high, #E53935);
}

.mini-button--danger:hover {
  background: var(--diff-del-bg, #FFEBEE);
  border-color: var(--risk-high, #E53935);
}

/* 骨架屏 */
.skeleton-area {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.skeleton-card {
  background: var(--bg-subtle, #f5f7fa);
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-md, 8px);
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
}

.skeleton-bar {
  animation: skeleton-pulse 1.4s ease-in-out infinite;
  background: linear-gradient(90deg, var(--bg-subtle, #f0f2f5) 25%, var(--bg-active, #e4e8ee) 50%, var(--bg-subtle, #f0f2f5) 75%);
  background-size: 200% 100%;
  border-radius: var(--radius-sm, 4px);
  height: 12px;
}

.skeleton-bar--title {
  height: 14px;
  width: 50%;
}

.skeleton-bar--text {
  height: 11px;
  width: 100%;
}

@keyframes skeleton-pulse {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* 空状态 */
.output-empty {
  align-items: center;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 32px 16px;
  text-align: center;
}

.output-empty__icon {
  font-size: 36px;
  opacity: 0.5;
}

.output-empty__title {
  color: var(--text-primary, #1a1d23);
  font-size: 14px;
  font-weight: 600;
  margin: 0;
}

.output-empty__hint {
  color: var(--text-secondary, #5b626c);
  font-size: 12px;
  margin: 0;
}
</style>
