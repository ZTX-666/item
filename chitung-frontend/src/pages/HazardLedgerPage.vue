<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import HazardLedgerPanel from '../components/hazards/HazardLedgerPanel.vue'
import {
  getHazards,
  listWorkbenchVideoDetections,
  runCaseWorkflow,
  visualPatrolAssetUrl,
} from '../services/chitungApi'
import type { SafetyCaseRecord, WorkbenchVideoDetectionReport } from '../types/domain'

const records = ref<SafetyCaseRecord[]>([])
const videoDetectionReports = ref<WorkbenchVideoDetectionReport[]>([])
const isLoading = ref(false)
const keyword = ref('')
const statusFilter = ref('all')

const filteredRecords = computed(() => {
  const byStatus = statusFilter.value === 'all'
    ? records.value
    : records.value.filter((item) => String(item.status || '').toLowerCase() === statusFilter.value.toLowerCase())
  if (!keyword.value.trim()) return byStatus
  const q = keyword.value.trim().toLowerCase()
  return byStatus.filter((item) => {
    const text = `${item.id} ${item.description || ''} ${item.area || ''} ${item.contractor || ''} ${item.scene || ''}`.toLowerCase()
    return text.includes(q)
  })
})

function isFallbackCamera(camera: { fallback_used?: boolean; error?: string; snapshot_source?: string }) {
  return Boolean(camera.fallback_used || camera.snapshot_source === 'fallback' || camera.error?.includes('本地回退图'))
}

function fallbackCameraCount(report: WorkbenchVideoDetectionReport) {
  if (report.cameras?.length) {
    return report.cameras.filter((camera) => isFallbackCamera(camera)).length
  }
  return isFallbackCamera(report) ? 1 : 0
}

function cameraFrameSourceText(camera: { fallback_reason?: string; fallback_image?: string; error?: string }) {
  if (!isFallbackCamera(camera)) return '实时帧'
  const reason = camera.fallback_reason || '视频流不可用'
  const image = camera.fallback_image || camera.error?.split('本地回退图: ')[1] || ''
  return image ? `回退图 · ${image}` : `回退图 · ${reason}`
}

async function refresh() {
  isLoading.value = true
  try {
    const [hazards, reports] = await Promise.all([
      getHazards(statusFilter.value === 'all' ? undefined : statusFilter.value),
      listWorkbenchVideoDetections(20),
    ])
    records.value = hazards
    videoDetectionReports.value = reports
  } finally {
    isLoading.value = false
  }
}

async function handleWorkflow(action: 'rectification-notice' | 'contractor-confirm' | 'close-review', caseId: string) {
  await runCaseWorkflow(action, {
    caseId,
    notes: 'Triggered from Hazard Ledger page',
    contractor: '待确认分包商',
  })
  await refresh()
}

onMounted(refresh)
</script>

<template>
  <main class="workbench">
    <section class="hero-panel">
      <div>
        <p class="eyebrow">Hazard Ledger</p>
        <h1>隐患台账</h1>
        <p>对齐原型 02 页面：筛选、检索、案例动作闭环。</p>
      </div>
      <div class="hero-panel__status">
        <span class="status-dot status-dot--green" />
        当前记录 {{ filteredRecords.length }} 条
      </div>
    </section>

    <section class="panel" style="margin-bottom: 12px;">
      <div class="template-search-bar">
        <input v-model="keyword" placeholder="搜索案例/区域/分包商" />
        <select v-model="statusFilter">
          <option value="all">全部状态</option>
          <option value="open">open</option>
          <option value="in_progress">in_progress</option>
          <option value="rectification_notice_drafted">rectification_notice_drafted</option>
          <option value="closed">closed</option>
        </select>
        <button class="primary-soft-button" :disabled="isLoading" @click="refresh">{{ isLoading ? '刷新中' : '刷新' }}</button>
      </div>
    </section>

    <section class="panel visual-detection-history">
      <div class="panel__header">
        <div>
          <h2>视觉检测历史</h2>
          <p>来自工作台总览的视频检测，保留原始方向、润色提示词、标注图和详细结果。</p>
        </div>
        <span class="camera-status camera-status--green">{{ videoDetectionReports.length }} 条</span>
      </div>
      <div v-if="!videoDetectionReports.length" class="visual-detection-history__empty">
        暂无视觉检测报告。可先在工作台总览输入检测方向并开始检测。
      </div>
      <article
        v-for="report in videoDetectionReports"
        :key="report.report_id"
        class="visual-detection-report-row"
      >
        <img
          v-if="report.annotated_url"
          :src="visualPatrolAssetUrl(report.annotated_url)"
          alt="视觉检测标注图"
        />
        <div class="visual-detection-report-row__body">
          <div class="visual-detection-report-row__head">
            <strong>{{ report.camera_name }} · {{ report.direction }}</strong>
            <div class="visual-detection-report-row__badges">
              <span
                v-if="fallbackCameraCount(report)"
                class="diff-status diff-status--draft visual-detection-fallback-badge"
              >
                {{ fallbackCameraCount(report) }} 路回退图
              </span>
              <span class="diff-status" :class="`diff-status--${report.summary.severity === 'low' ? 'accepted' : 'draft'}`">
                {{ report.summary.severity }}
              </span>
            </div>
          </div>
          <p>{{ report.summary.text }}</p>
          <small>润色提示词：{{ report.refined_prompt }}</small>
          <small v-if="report.policy_context?.length">制度依据：{{ report.policy_context.slice(0, 2).join('；') }}</small>
          <div v-if="report.cameras?.length" class="visual-detection-camera-strip">
            <figure v-for="camera in report.cameras" :key="camera.camera_id">
              <img
                v-if="camera.annotated_url"
                :src="visualPatrolAssetUrl(camera.annotated_url)"
                alt="单路视觉检测标注图"
              />
              <figcaption>
                <strong>{{ camera.camera_name }} · {{ camera.summary?.detection_count ?? camera.detections?.length ?? 0 }} 个目标</strong>
                <span :class="{ 'visual-detection-frame-source--fallback': isFallbackCamera(camera) }">
                  {{ cameraFrameSourceText(camera) }}
                </span>
              </figcaption>
            </figure>
          </div>
        </div>
      </article>
    </section>

    <HazardLedgerPanel
      :records="filteredRecords"
      :is-loading="isLoading"
      @refresh="refresh"
      @workflow="handleWorkflow"
    />
  </main>
</template>

<style scoped>
.visual-detection-history {
  margin-bottom: 12px;
}

.visual-detection-history__empty {
  border: 1px dashed var(--border-normal);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 13px;
  padding: 14px;
}

.visual-detection-report-row {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  display: grid;
  gap: 12px;
  grid-template-columns: 180px minmax(0, 1fr);
  margin-top: 10px;
  padding: 10px;
}

.visual-detection-report-row img {
  aspect-ratio: 16 / 9;
  background: #111827;
  border-radius: var(--radius-sm);
  object-fit: cover;
  width: 100%;
}

.visual-detection-report-row__body {
  min-width: 0;
}

.visual-detection-report-row__head {
  align-items: center;
  display: flex;
  gap: 8px;
  justify-content: space-between;
}

.visual-detection-report-row__badges {
  align-items: center;
  display: flex;
  flex-shrink: 0;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
}

.visual-detection-fallback-badge {
  background: rgba(255, 138, 0, 0.1);
  color: #a14d00;
}

.visual-detection-report-row p {
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.5;
  margin: 6px 0;
}

.visual-detection-report-row small {
  color: var(--text-secondary);
  display: block;
  font-size: 12px;
  margin-top: 4px;
  overflow-wrap: anywhere;
}

.visual-detection-camera-strip {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  margin-top: 10px;
}

.visual-detection-camera-strip figure {
  margin: 0;
}

.visual-detection-camera-strip img {
  aspect-ratio: 16 / 9;
  background: #111827;
  border-radius: var(--radius-sm);
  object-fit: cover;
  width: 100%;
}

.visual-detection-camera-strip figcaption {
  color: var(--text-secondary);
  display: grid;
  font-size: 11px;
  gap: 2px;
  margin-top: 4px;
}

.visual-detection-camera-strip figcaption strong {
  color: var(--text-primary);
  font-size: 12px;
}

.visual-detection-frame-source--fallback {
  color: #a14d00;
  font-weight: 700;
}

@media (max-width: 760px) {
  .visual-detection-report-row {
    grid-template-columns: 1fr;
  }
}
</style>
