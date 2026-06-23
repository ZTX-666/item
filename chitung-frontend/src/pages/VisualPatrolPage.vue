<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import CctvLivePanel from '../components/cctv/CctvLivePanel.vue'
import {
  confirmVisualPatrolCandidate,
  draftVisualPatrol,
  getAppConfig,
  getVisualPatrolRun,
  listVisualPatrolRuns,
  parseCctvPlaybackInfo,
  runVisualPatrolBatch,
  saveAppConfig,
  visualPatrolAssetUrl,
} from '../services/chitungApi'
import type { AppConfig, CameraConfig, PatrolRunReport, PatrolRunSummary, VisualPatrolDraft } from '../types/domain'

const CENTER_BASE_URL =
  import.meta.env.VITE_CHITUNG_CENTER_URL?.replace(/\/$/, '') || 'http://127.0.0.1:8999'

const appConfig = ref<AppConfig | null>(null)
const patrolDraft = ref<VisualPatrolDraft | null>(null)
const patrolHistory = ref<PatrolRunSummary[]>([])
const selectedReport = ref<PatrolRunReport | null>(null)
const isPatrolling = ref(false)
const isBatchRunning = ref(false)
const isSavingCameraSources = ref(false)
const isParsingPlaybackInfo = ref(false)
const testingCameraSourceId = ref<string | null>(null)
const note = ref('等待巡检')
const cameraConfigNote = ref('')
const playbackInfoText = ref('')

const vlmEnabled = ref(true)
const yoloConfThreshold = ref(0.45)
const analysisMode = computed(() => (vlmEnabled.value ? 'hybrid' : 'yolo_only'))
const cameraSourceTypes = [
  { value: 'rtmp', label: 'RTMP / H264' },
  { value: 'csmart', label: 'C-SMART' },
  { value: 'csmart_player', label: '播放页截图' },
  { value: 'snapshot', label: '截图 URL' },
] as const

const hasCameras = computed(() => (appConfig.value?.cameras?.length ?? 0) > 0)
const primaryCandidate = computed(() => patrolDraft.value?.candidates[0] || null)
const detectionDetails = computed(() => primaryCandidate.value?.detection_details || [])
const selectedCameraResult = computed(() => {
  const cameraId = patrolDraft.value?.camera_id
  if (!cameraId) return null
  return selectedReport.value?.cameras?.find((camera) => camera.camera_id === cameraId) || null
})
const captureAttempts = computed(() => selectedCameraResult.value?.capture_attempts || [])

const annotatedImageUrl = computed(() => {
  const url = patrolDraft.value?.annotated_url
  if (url) return `${CENTER_BASE_URL}${url}`
  return undefined
})

const snapshotImageUrl = computed(() => {
  const url = patrolDraft.value?.snapshot_url
  if (url) return `${CENTER_BASE_URL}${url}`
  return visualPatrolAssetUrl(patrolDraft.value?.source)
})

const evidencePath = computed(() => patrolDraft.value?.source || patrolDraft.value?.confirm_payload?.image_path)

onMounted(async () => {
  appConfig.value = normalizeAppConfig(await getAppConfig())
  await refreshHistory()
})

function normalizeAppConfig(config: AppConfig): AppConfig {
  config.cameras = (config.cameras || []).map((camera) => ({
    ...camera,
    source_type: camera.source_type || 'rtmp',
    rtmp_url: camera.rtmp_url ?? '',
    snapshot_url: camera.snapshot_url ?? '',
    csmart_channel_number: camera.csmart_channel_number ?? '',
    csmart_channel_id: camera.csmart_channel_id ?? '',
    player_screenshot_url: camera.player_screenshot_url ?? '',
    playback_info: camera.playback_info ?? {},
    playback_info_raw: camera.playback_info_raw ?? '',
    inspection_interval_minutes: camera.inspection_interval_minutes ?? null,
    remark: camera.remark ?? '',
    enabled: camera.enabled ?? true,
  }))
  return config
}

function textOrNull(value: unknown): string | null {
  if (value == null) return null
  const text = String(value).trim()
  return text || null
}

function normalizeInterval(value: unknown): number | null {
  if (value == null || value === '') return null
  const numeric = Number(value)
  if (!Number.isFinite(numeric) || numeric <= 0) return null
  return Math.round(numeric)
}

function cameraForSave(camera: CameraConfig): CameraConfig {
  const fallbackId = `camera-${Date.now().toString(36)}`
  return {
    id: textOrNull(camera.id) || fallbackId,
    name: textOrNull(camera.name) || '未命名监控',
    area: textOrNull(camera.area) || appConfig.value?.project.default_area || '施工区域',
    source_type: camera.source_type || 'rtmp',
    rtmp_url: textOrNull(camera.rtmp_url),
    snapshot_url: textOrNull(camera.snapshot_url),
    csmart_channel_number: textOrNull(camera.csmart_channel_number),
    csmart_channel_id: textOrNull(camera.csmart_channel_id),
    player_screenshot_url: textOrNull(camera.player_screenshot_url),
    playback_info: camera.playback_info ?? {},
    playback_info_raw: textOrNull(camera.playback_info_raw),
    inspection_interval_minutes: normalizeInterval(camera.inspection_interval_minutes),
    remark: textOrNull(camera.remark),
    enabled: Boolean(camera.enabled),
  }
}

function addCameraSource() {
  if (!appConfig.value) return
  appConfig.value.cameras.push({
    id: `camera-${Date.now().toString(36)}`,
    name: '新监控',
    area: appConfig.value.project.default_area || '施工区域',
    source_type: 'rtmp',
    rtmp_url: '',
    snapshot_url: '',
    csmart_channel_number: '',
    csmart_channel_id: '',
    player_screenshot_url: '',
    playback_info: {},
    playback_info_raw: '',
    inspection_interval_minutes: null,
    remark: '',
    enabled: true,
  })
  cameraConfigNote.value = '已新增一行，保存后生效。'
}

async function importPlaybackInfo() {
  if (!appConfig.value) return
  const text = playbackInfoText.value.trim()
  if (!text) {
    cameraConfigNote.value = '请先粘贴 CCTV 播放信息。'
    return
  }
  isParsingPlaybackInfo.value = true
  cameraConfigNote.value = '正在解析 CCTV 播放信息...'
  try {
    const result = await parseCctvPlaybackInfo(text)
    const parsed = (result.cameras || []).map((camera) => normalizeAppConfig({
      ...appConfig.value!,
      cameras: [camera],
    }).cameras[0])
    if (!parsed.length) {
      cameraConfigNote.value = '未解析到 Cam 播放信息。'
      return
    }
    const byId = new Map(appConfig.value.cameras.map((camera, index) => [camera.id, index]))
    for (const camera of parsed) {
      const existingIndex = byId.get(camera.id)
      if (existingIndex == null) {
        appConfig.value.cameras.push(camera)
        byId.set(camera.id, appConfig.value.cameras.length - 1)
      } else {
        appConfig.value.cameras.splice(existingIndex, 1, {
          ...appConfig.value.cameras[existingIndex],
          ...camera,
        })
      }
    }
    cameraConfigNote.value = `已导入 ${parsed.length} 路播放信息，保存后生效。`
  } catch (error) {
    cameraConfigNote.value = `播放信息解析失败：${error instanceof Error ? error.message : String(error)}`
  } finally {
    isParsingPlaybackInfo.value = false
  }
}

function removeCameraSource(index: number) {
  if (!appConfig.value) return
  appConfig.value.cameras.splice(index, 1)
  cameraConfigNote.value = '已删除该行，保存后生效。'
}

async function saveCameraSources() {
  if (!appConfig.value) return
  isSavingCameraSources.value = true
  cameraConfigNote.value = '正在保存摄像头源配置...'
  try {
    const payload: AppConfig = {
      ...appConfig.value,
      cameras: appConfig.value.cameras.map(cameraForSave),
    }
    const result = await saveAppConfig(payload)
    appConfig.value = normalizeAppConfig(result.config)
    cameraConfigNote.value = '摄像头源配置已保存。'
  } catch (error) {
    cameraConfigNote.value = `保存失败：${error instanceof Error ? error.message : String(error)}`
  } finally {
    isSavingCameraSources.value = false
  }
}

async function testCameraSource(camera: CameraConfig) {
  testingCameraSourceId.value = camera.id
  cameraConfigNote.value = `正在巡检 ${camera.name || camera.id}...`
  try {
    await handlePatrol(camera.id)
  } finally {
    testingCameraSourceId.value = null
  }
}

async function refreshHistory() {
  try {
    patrolHistory.value = await listVisualPatrolRuns(12)
  } catch {
    patrolHistory.value = []
  }
}

async function handlePatrol(cameraId?: string) {
  if (!hasCameras.value) {
    note.value = '请先在系统设置中配置摄像头 RTMP 地址。'
    return
  }
  isPatrolling.value = true
  note.value = `正在巡检 ${cameraId || '默认摄像头'}（赤瞳守护者流水线）...`
  try {
    const camera = appConfig.value?.cameras.find((item) => item.id === cameraId)
    patrolDraft.value = await draftVisualPatrol({
      cameraId,
      cameraUrl: camera?.rtmp_url || undefined,
      area: camera?.area || appConfig.value?.project.default_area || '施工區域',
      count: 1,
      analysisMode: analysisMode.value,
      vlmEnabled: vlmEnabled.value,
      yoloConfThreshold: yoloConfThreshold.value,
      useGuardianPipeline: true,
    })
    note.value = patrolDraft.value.message
    if (patrolDraft.value.patrol_id) {
      selectedReport.value = patrolDraft.value.report ?? (await getVisualPatrolRun(patrolDraft.value.patrol_id))
    }
    await refreshHistory()
  } catch (error) {
    note.value = `巡检失败：${error instanceof Error ? error.message : String(error)}`
  } finally {
    isPatrolling.value = false
  }
}

async function handleBatchPatrol() {
  if (!hasCameras.value) {
    note.value = '请先在系统设置中配置摄像头。'
    return
  }
  isBatchRunning.value = true
  note.value = `正在全量巡检 ${appConfig.value?.cameras.length ?? 0} 路摄像头...`
  try {
    const result = await runVisualPatrolBatch({
      vlmEnabled: vlmEnabled.value,
      yoloOnly: !vlmEnabled.value,
    })
    if (!result.ok || !result.report) {
      note.value = result.error || '全量巡检失败'
      return
    }
    selectedReport.value = result.report
    const firstCamera = result.report.cameras?.find((item) => item.success) || result.report.cameras?.[0]
    if (firstCamera && result.report.patrol_id) {
      patrolDraft.value = {
        ok: true,
        message: `全量巡检完成：${result.report.success_count}/${result.report.camera_count} 成功，共 ${result.report.total_detections} 个目标`,
        requires_confirmation: true,
        patrol_id: result.report.patrol_id,
        camera_id: firstCamera.camera_id,
        camera_name: firstCamera.camera_name,
        snapshot_url: firstCamera.snapshot_url,
        annotated_url: firstCamera.annotated_url,
        analysis_mode: firstCamera.source_mix === 'hybrid' ? 'hybrid' : 'yolo_only',
        candidates: [],
        confirm_payload: {
          image_path: firstCamera.snapshot_path,
          area: firstCamera.area,
          description: `${firstCamera.camera_name} 全量巡检候选`,
        },
      }
    }
    note.value = `全量巡检完成：检测 ${result.report.total_detections} 个目标，高风险 ${result.report.high_risk_count ?? 0} 个`
    await refreshHistory()
  } catch (error) {
    note.value = `全量巡检失败：${error instanceof Error ? error.message : String(error)}`
  } finally {
    isBatchRunning.value = false
  }
}

async function loadPatrolRun(patrolId: string) {
  selectedReport.value = await getVisualPatrolRun(patrolId)
  const first = selectedReport.value.cameras?.[0]
  if (first) {
    patrolDraft.value = {
      ok: true,
      message: `历史巡检 ${patrolId}`,
      requires_confirmation: false,
      patrol_id: patrolId,
      camera_id: first.camera_id,
      camera_name: first.camera_name,
      snapshot_url: first.snapshot_url,
      annotated_url: first.annotated_url,
      analysis_mode: first.source_mix === 'hybrid' ? 'hybrid' : 'yolo_only',
      candidates: [],
    }
  }
}

function selectCameraFromReport(cam: NonNullable<PatrolRunReport['cameras']>[number]) {
  if (!selectedReport.value) return
  patrolDraft.value = {
    ok: cam.success,
    message: cam.error || `${cam.camera_name} 巡检结果`,
    requires_confirmation: true,
    patrol_id: selectedReport.value.patrol_id,
    camera_id: cam.camera_id,
    camera_name: cam.camera_name,
    snapshot_url: cam.snapshot_url,
    annotated_url: cam.annotated_url,
    source: cam.snapshot_path || undefined,
    analysis_mode: cam.source_mix === 'hybrid' ? 'hybrid' : 'yolo_only',
    candidates: cam.success ? [
      {
        id: `visual-${cam.camera_id}`,
        title: `${cam.camera_name} 巡检候选`,
        risk_level: 'medium',
        area: cam.area,
        description: `检测 ${cam.detection_count ?? cam.detections?.length ?? 0} 个目标`,
        labels: (cam.detections || []).map((d) => String(d.label || '')),
        source_mix: cam.source_mix,
        detection_details: (cam.detections || []).map((d) => ({
          bbox: (d.bbox as number[]) || [],
          label: String(d.label || ''),
          confidence: Number(d.confidence || 0),
          source: String(d.source || 'yolo'),
          description: String(d.description || ''),
          severity: String(d.severity || 'low'),
          suggested_action: String(d.suggested_action || ''),
        })),
      },
    ] : [],
    confirm_payload: {
      image_path: cam.snapshot_path,
      area: cam.area,
      description: `${cam.camera_name} 视觉巡检候选`,
      detections: { items: cam.detections, camera_id: cam.camera_id, patrol_id: selectedReport.value.patrol_id },
    },
  }
}

async function handleConfirmCandidate() {
  if (!patrolDraft.value?.confirm_payload) return
  await confirmVisualPatrolCandidate(patrolDraft.value)
  note.value = '视觉隐患已确认入库。'
}

async function openEvidence(path?: string) {
  if (!path) return
  if (!window.chitungDesktop) return
  await window.chitungDesktop.openPath(path)
}

function severityClass(severity: string | undefined): string {
  switch (severity) {
    case 'critical': return 'sev-critical'
    case 'high': return 'sev-high'
    case 'medium': return 'sev-medium'
    case 'low': return 'sev-low'
    default: return 'sev-low'
  }
}

function severityText(severity: string | undefined): string {
  switch (severity) {
    case 'critical': return '严重'
    case 'high': return '高'
    case 'medium': return '中'
    case 'low': return '低'
    default: return '未知'
  }
}

function sourceText(source: string | undefined): string {
  switch (source) {
    case 'yolo': return 'YOLO'
    case 'vlm': return 'VLM'
    case 'hybrid': return '混合'
    default: return source || '未知'
  }
}
</script>

<template>
  <main class="workbench">
    <section class="hero-panel">
      <div>
        <p class="eyebrow">Chitung Guardian</p>
        <h1>赤瞳守护者 · 视觉巡检</h1>
        <p>RTMP 截帧 → YOLO 双模型 → VLM 语义精分 → 标注图 → 人工确认入库</p>
      </div>
      <div class="hero-panel__status">
        <span class="status-dot" :class="(isPatrolling || isBatchRunning) ? 'status-dot--orange' : 'status-dot--green'" />
        {{ note }}
      </div>
    </section>

    <section class="panel vlm-controls-panel">
      <div class="vlm-controls">
        <label class="vlm-toggle">
          <input type="checkbox" v-model="vlmEnabled" />
          <span class="vlm-toggle__label">VLM 大模型精分 (GLM-4v)</span>
          <span class="vlm-toggle__hint">{{ vlmEnabled ? 'YOLO→VLM 串行' : '纯 YOLO' }}</span>
        </label>
        <div class="vlm-threshold">
          <span class="vlm-threshold__label">YOLO 置信度阈值</span>
          <span class="vlm-threshold__value">{{ yoloConfThreshold.toFixed(2) }}</span>
        </div>
        <button
          class="primary-soft-button"
          :disabled="isBatchRunning || !hasCameras"
          @click="handleBatchPatrol"
        >
          {{ isBatchRunning ? '全量巡检中...' : `全量巡检 ${appConfig?.cameras.length ?? 0} 路` }}
        </button>
      </div>
    </section>

    <section class="panel camera-source-panel">
      <div class="panel__header camera-source-panel__header">
        <div>
          <h2>摄像头源配置</h2>
          <p>监控名、RTMP/H264 地址、截图源和巡检参数</p>
        </div>
        <div class="camera-source-actions">
          <button class="mini-button" type="button" @click="addCameraSource">新增</button>
          <button
            class="primary-soft-button"
            type="button"
            :disabled="isSavingCameraSources || !appConfig"
            @click="saveCameraSources"
          >
            {{ isSavingCameraSources ? '保存中...' : '保存配置' }}
          </button>
        </div>
      </div>

      <div class="playback-import">
        <textarea
          v-model="playbackInfoText"
          rows="8"
          placeholder="Cam12&#10;播放信息&#10;EZOPEN(標清)&#10;ezopen://...&#10;FLV(標清)&#10;https://..."
        />
        <div class="playback-import__actions">
          <button
            class="primary-soft-button"
            type="button"
            :disabled="isParsingPlaybackInfo || !appConfig"
            @click="importPlaybackInfo"
          >
            {{ isParsingPlaybackInfo ? '解析中...' : '导入播放信息' }}
          </button>
          <button class="mini-button" type="button" @click="playbackInfoText = ''">清空</button>
        </div>
      </div>

      <div v-if="appConfig" class="camera-source-table-wrap">
        <table class="camera-source-table">
          <thead>
            <tr>
              <th>启用</th>
              <th>监控名</th>
              <th>区域</th>
              <th>源类型</th>
              <th>视频流地址</th>
              <th>截图 URL</th>
              <th>C-SMART</th>
              <th>播放截图</th>
              <th>间隔</th>
              <th>备注</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(camera, index) in appConfig.cameras" :key="camera.id || index">
              <td class="camera-source-table__enabled">
                <input type="checkbox" v-model="camera.enabled" />
              </td>
              <td>
                <input v-model.trim="camera.name" type="text" />
              </td>
              <td>
                <input v-model.trim="camera.area" type="text" />
              </td>
              <td>
                <select v-model="camera.source_type">
                  <option v-for="type in cameraSourceTypes" :key="type.value" :value="type.value">
                    {{ type.label }}
                  </option>
                </select>
              </td>
              <td>
                <textarea v-model.trim="camera.rtmp_url" rows="2" placeholder="rtmp://..." />
              </td>
              <td>
                <input v-model.trim="camera.snapshot_url" type="text" placeholder="https://..." />
              </td>
              <td>
                <input v-model.trim="camera.csmart_channel_number" type="text" placeholder="通道号" />
              </td>
              <td>
                <input v-model.trim="camera.player_screenshot_url" type="text" placeholder="自动生成" />
              </td>
              <td>
                <input v-model.number="camera.inspection_interval_minutes" type="number" min="1" placeholder="分钟" />
              </td>
              <td>
                <input v-model.trim="camera.remark" type="text" />
              </td>
              <td class="camera-source-table__ops">
                <button
                  class="mini-button"
                  type="button"
                  :disabled="isPatrolling || testingCameraSourceId === camera.id"
                  @click="testCameraSource(camera)"
                >
                  {{ testingCameraSourceId === camera.id ? '测试中' : '测试' }}
                </button>
                <button class="mini-button" type="button" @click="removeCameraSource(index)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="!appConfig.cameras.length" class="camera-source-empty">
          暂无摄像头源配置。
        </div>
      </div>
      <p v-else class="camera-source-empty">正在加载摄像头源配置...</p>
      <p v-if="cameraConfigNote" class="camera-source-note">{{ cameraConfigNote }}</p>
    </section>

    <div class="visual-layout">
      <div class="visual-main">
        <CctvLivePanel
          title="CCTV 实时画面"
          subtitle="C-SMART 直播 + 视觉巡检入口"
          :busy="isPatrolling"
          action-label="巡检当前画面"
          busy-label="巡检中"
          @patrol="handlePatrol"
        />

        <section v-if="annotatedImageUrl || snapshotImageUrl" class="panel image-panel">
          <div class="panel__header">
            <div>
              <h2>巡检标注图</h2>
              <p>{{ patrolDraft?.camera_name || patrolDraft?.camera_id || '最新结果' }}</p>
            </div>
          </div>
          <img
            v-if="annotatedImageUrl"
            :src="annotatedImageUrl"
            alt="annotated patrol"
            class="patrol-image"
          />
          <img
            v-else-if="snapshotImageUrl"
            :src="snapshotImageUrl"
            alt="patrol snapshot"
            class="patrol-image"
          />
        </section>

        <section v-if="patrolDraft && !patrolDraft.ok && !primaryCandidate" class="panel capture-error-panel">
          <div class="panel__header">
            <div>
              <h2>巡检失败</h2>
              <p>{{ patrolDraft.camera_name || patrolDraft.camera_id || '当前摄像头' }}</p>
            </div>
          </div>
          <p class="capture-error-panel__message">{{ patrolDraft.message }}</p>
          <div v-if="captureAttempts.length" class="capture-attempts">
            <div
              v-for="(attempt, index) in captureAttempts"
              :key="`${attempt.method || 'capture'}-${index}`"
              class="capture-attempt"
              :class="{ 'capture-attempt--ok': attempt.ok }"
            >
              <div class="capture-attempt__row">
                <strong>{{ attempt.method || 'stream' }}</strong>
                <span>{{ attempt.ok ? '成功' : '失败' }}</span>
                <span v-if="attempt.attempt">第 {{ attempt.attempt }} 次</span>
              </div>
              <p v-if="attempt.error">{{ attempt.error }}</p>
              <code v-if="attempt.url">{{ attempt.url }}</code>
            </div>
          </div>
        </section>

        <section v-if="primaryCandidate" class="panel candidate-panel">
          <div class="candidate-header">
            <h2>{{ primaryCandidate.title }}</h2>
            <span class="sev-tag" :class="severityClass(primaryCandidate.severity)">
              {{ severityText(primaryCandidate.severity) }}
            </span>
            <span class="source-tag" v-if="primaryCandidate.source_mix">
              {{ sourceText(primaryCandidate.source_mix) }}
            </span>
          </div>
          <p class="candidate-desc">{{ primaryCandidate.description }}</p>
          <div class="candidate-action" v-if="primaryCandidate.suggested_action">
            <strong>建议处置：</strong>
            <span>{{ primaryCandidate.suggested_action }}</span>
          </div>
          <div class="detection-details" v-if="detectionDetails.length">
            <h3>检测详情（{{ detectionDetails.length }} 项）</h3>
            <div class="detection-item" v-for="(detail, idx) in detectionDetails" :key="idx">
              <div class="detection-item__row">
                <span class="det-source" :class="`src-${detail.source}`">{{ sourceText(detail.source) }}</span>
                <span class="det-label">{{ detail.label }}</span>
                <span class="det-conf">{{ (detail.confidence * 100).toFixed(1) }}%</span>
                <span class="sev-tag sev-tag-sm" :class="severityClass(detail.severity)">
                  {{ severityText(detail.severity) }}
                </span>
              </div>
              <p class="det-desc" v-if="detail.description">{{ detail.description }}</p>
              <p class="det-action" v-if="detail.suggested_action">
                <strong>建议：</strong>{{ detail.suggested_action }}
              </p>
            </div>
          </div>
          <div class="candidate-actions">
            <button class="mini-button" @click="openEvidence(String(evidencePath || ''))">打开证据</button>
            <button class="primary-soft-button" @click="handleConfirmCandidate">确认入库</button>
          </div>
        </section>
      </div>

      <aside class="panel patrol-history">
        <div class="panel__header">
          <div>
            <h2>巡检历史</h2>
            <p>来自 patrol-output 的 JSON 报告</p>
          </div>
          <button class="mini-button" @click="refreshHistory">刷新</button>
        </div>
        <div v-if="!patrolHistory.length" class="history-empty">暂无历史巡检记录</div>
        <button
          v-for="run in patrolHistory"
          :key="run.patrol_id"
          class="history-item"
          @click="loadPatrolRun(run.patrol_id)"
        >
          <strong>{{ run.patrol_id }}</strong>
          <span>{{ run.success_count }}/{{ run.camera_count }} 成功 · {{ run.total_detections }} 目标</span>
          <span v-if="run.high_risk_count">高风险 {{ run.high_risk_count }}</span>
        </button>

        <div v-if="selectedReport?.cameras?.length" class="history-cameras">
          <h3>本轮摄像头</h3>
          <button
            v-for="cam in selectedReport.cameras"
            :key="cam.camera_id"
            class="history-camera"
            @click="selectCameraFromReport(cam)"
          >
          <span>{{ cam.camera_name }}</span>
            <span v-if="cam.success">{{ cam.detection_count ?? cam.detections?.length ?? 0 }} 目标 · {{ cam.source_mix }}</span>
            <span v-else class="history-camera__error">失败 · {{ cam.error || '抽帧失败' }}</span>
          </button>
        </div>
      </aside>
    </div>
  </main>
</template>

<style scoped>
.camera-source-panel {
  margin-bottom: 16px;
}

.camera-source-panel__header,
.camera-source-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.camera-source-actions {
  justify-content: flex-end;
  flex-wrap: wrap;
}

.playback-import {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  align-items: start;
  margin: 12px 0 14px;
}

.playback-import textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid #dbe3ef;
  border-radius: 6px;
  padding: 10px 12px;
  color: #111827;
  background: #fff;
  font: inherit;
  line-height: 1.45;
  resize: vertical;
}

.playback-import__actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.camera-source-table-wrap {
  overflow-x: auto;
}

.camera-source-table {
  width: 100%;
  min-width: 1360px;
  table-layout: fixed;
  border-collapse: collapse;
}

.camera-source-table th,
.camera-source-table td {
  padding: 8px;
  border-top: 1px solid rgba(148, 163, 184, 0.2);
  vertical-align: top;
}

.camera-source-table th {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  text-align: left;
  background: #f8fafc;
}

.camera-source-table th:nth-child(1) { width: 58px; }
.camera-source-table th:nth-child(2) { width: 140px; }
.camera-source-table th:nth-child(3) { width: 110px; }
.camera-source-table th:nth-child(4) { width: 130px; }
.camera-source-table th:nth-child(5) { width: 280px; }
.camera-source-table th:nth-child(6) { width: 190px; }
.camera-source-table th:nth-child(7) { width: 110px; }
.camera-source-table th:nth-child(8) { width: 190px; }
.camera-source-table th:nth-child(9) { width: 90px; }
.camera-source-table th:nth-child(10) { width: 150px; }
.camera-source-table th:nth-child(11) { width: 130px; }

.camera-source-table input,
.camera-source-table select,
.camera-source-table textarea {
  width: 100%;
  min-height: 36px;
  box-sizing: border-box;
  border: 1px solid #dbe3ef;
  border-radius: 6px;
  padding: 8px 10px;
  color: #111827;
  background: #fff;
  font: inherit;
}

.camera-source-table textarea {
  resize: vertical;
  line-height: 1.35;
  word-break: break-all;
}

.camera-source-table__enabled {
  text-align: center;
}

.camera-source-table__enabled input {
  width: 18px;
  min-height: 18px;
  margin-top: 8px;
}

.camera-source-table__ops {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.camera-source-empty,
.camera-source-note {
  margin: 10px 0 0;
  color: #64748b;
  font-size: 13px;
}

.camera-source-note {
  color: #0f766e;
}

.visual-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 16px;
}

.visual-main {
  min-width: 0;
}

.vlm-controls-panel {
  padding: 14px 20px;
  margin-bottom: 16px;
}

.vlm-controls {
  display: flex;
  align-items: center;
  gap: 28px;
  flex-wrap: wrap;
}

.vlm-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.vlm-toggle__label { font-weight: 600; font-size: 14px; }
.vlm-toggle__hint { font-size: 12px; color: #888; }
.vlm-threshold { display: flex; align-items: center; gap: 6px; }
.vlm-threshold__value { font-weight: 700; color: #2563eb; }

.image-panel { margin-top: 16px; }
.patrol-image {
  width: 100%;
  max-height: 480px;
  object-fit: contain;
  border-radius: 8px;
  background: #111;
}

.capture-error-panel {
  margin-top: 16px;
  border-color: rgba(220, 38, 38, 0.2);
}

.capture-error-panel__message {
  margin: 0;
  color: #991b1b;
  font-weight: 600;
  line-height: 1.6;
}

.capture-attempts {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.capture-attempt {
  padding: 10px 12px;
  border: 1px solid #fee2e2;
  border-radius: 6px;
  background: #fff7f7;
}

.capture-attempt--ok {
  border-color: #bbf7d0;
  background: #f0fdf4;
}

.capture-attempt__row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  color: #334155;
}

.capture-attempt p {
  margin: 6px 0 0;
  color: #b91c1c;
  font-size: 13px;
}

.capture-attempt code {
  display: block;
  margin-top: 6px;
  max-width: 100%;
  overflow-wrap: anywhere;
  color: #475569;
  font-size: 12px;
  line-height: 1.45;
}

.patrol-history {
  align-self: start;
  position: sticky;
  top: 12px;
}

.history-empty {
  color: #888;
  font-size: 13px;
  padding: 8px 0;
}

.history-item,
.history-camera {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  width: 100%;
  text-align: left;
  padding: 10px 12px;
  margin-top: 8px;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 8px;
  background: rgba(255,255,255,0.02);
  cursor: pointer;
}

.history-item span,
.history-camera span {
  font-size: 12px;
  color: #9aa4b2;
}

.history-camera .history-camera__error {
  color: #dc2626;
}

.history-cameras {
  margin-top: 16px;
  border-top: 1px solid rgba(255,255,255,0.08);
  padding-top: 12px;
}

.history-cameras h3 {
  margin: 0 0 8px;
  font-size: 13px;
  color: #9aa4b2;
}

.candidate-panel { padding: 20px; margin-top: 16px; }
.candidate-header { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.candidate-header h2 { margin: 0; font-size: 18px; }
.sev-tag { padding: 2px 10px; border-radius: 4px; font-size: 12px; font-weight: 600; }
.sev-tag-sm { padding: 1px 6px; font-size: 11px; }
.sev-critical { background: #991b1b; color: #fff; }
.sev-high { background: #dc2626; color: #fff; }
.sev-medium { background: #f97316; color: #fff; }
.sev-low { background: #facc15; color: #1f2937; }
.source-tag { padding: 2px 10px; border-radius: 4px; font-size: 12px; background: #e0e7ff; color: #4338ca; }
.candidate-desc { margin: 8px 0; line-height: 1.6; }
.detection-details { margin-top: 14px; border-top: 1px solid #e5e7eb; padding-top: 12px; }
.detection-item { padding: 8px 12px; margin-bottom: 6px; background: #f9fafb; border-radius: 6px; }
.detection-item__row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.det-source { padding: 1px 6px; border-radius: 3px; font-size: 11px; font-weight: 600; }
.src-yolo { background: #dbeafe; color: #2563eb; }
.src-vlm { background: #fce7f3; color: #db2777; }
.src-hybrid { background: #ede9fe; color: #7c3aed; }
.det-label { font-weight: 600; }
.det-conf { font-size: 12px; color: #6b7280; }
.det-desc, .det-action { margin: 4px 0 0; font-size: 13px; }
.candidate-actions { display: flex; gap: 10px; margin-top: 14px; }

@media (max-width: 1100px) {
  .visual-layout { grid-template-columns: 1fr; }
  .patrol-history { position: static; }
  .camera-source-panel__header { align-items: flex-start; flex-direction: column; }
  .playback-import { grid-template-columns: 1fr; }
  .playback-import__actions { justify-content: flex-start; }
}
</style>
