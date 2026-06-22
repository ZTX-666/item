<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import ActiveHazards from '../components/cards/ActiveHazards.vue'
import ActivityFeed from '../components/cards/ActivityFeed.vue'
import ActionReviewCards from '../components/cards/ActionReviewCards.vue'
import StatusStrip from '../components/cards/StatusStrip.vue'
import CctvLivePanel from '../components/cctv/CctvLivePanel.vue'
import CommandBar from '../components/layout/CommandBar.vue'
import ProgressChain from '../components/workflow/ProgressChain.vue'
import { useAppNavigation } from '../composables/useAppNavigation'
import {
  draftVisualPatrol,
  getAppConfig,
  getWorkbenchSummary,
  refineWorkbenchVideoDetectionPrompt,
  runCaseWorkflow,
  runWorkbenchVideoDetection,
  sendCaseNotification,
  sendCardAction,
  sendChatMessage,
  updateHazardStatus,
} from '../services/chitungApi'
import type {
  ActivityItem,
  AppConfig,
  HazardCase,
  NotificationDraft,
  StatusMetric,
  WorkbenchVideoDetectionReport,
  WorkbenchStatus,
  WorkflowStep,
} from '../types/domain'

type ReviewCard = {
  card_type?: string
  title: string
  summary: string
  actions?: Array<{ id: string; label: string }>
  data?: Record<string, unknown>
}

type VideoDetectionPhase = 'idle' | 'prompting' | 'ready' | 'detecting' | 'done' | 'error'

const { goTo, goToPendingConfirmations } = useAppNavigation()

const metrics = ref<StatusMetric[]>([])
const hazards = ref<HazardCase[]>([])
const workbenchStatus = ref<WorkbenchStatus | null>(null)

const workflowSteps = ref<WorkflowStep[]>([
  { id: 'intent', label: '识别意图', status: 'pending' },
  { id: 'tool', label: '调用工具', status: 'pending' },
  { id: 'confirm', label: '等待确认', status: 'pending' },
])

const activities = ref<ActivityItem[]>([])
const summaryLoadError = ref('')

const notificationDraft = ref<NotificationDraft | null>(null)

const aiMessages = ref<string[]>([
  '工作台已就绪。你可以输入“检查 B2 摄像头”“生成今日简报”或“帮我填 T006”。',
])
const reviewCards = ref<ReviewCard[]>([])
const isCardActionBusy = ref(false)
const isSending = ref(false)
const isPatrolling = ref(false)
const isVideoDetecting = ref(false)
const isPromptRefining = ref(false)
const appConfig = ref<AppConfig | null>(null)
const selectedVideoCameraIds = ref<string[]>([])
const videoDetectionDirection = ref('检查人员PPE合规、机械作业半径和隔离围挡：识别未戴安全帽、未穿反光衣、人员靠近挖掘机/机械作业区、隔离不足')
const refinedVideoPrompt = ref('')
const videoPromptSource = ref('')
const videoPromptPolicyContext = ref<string[]>([])
const videoDetectionError = ref('')
const videoDetectionPhase = ref<VideoDetectionPhase>('idle')
const currentVideoDetectionReport = ref<WorkbenchVideoDetectionReport | null>(null)

const centerStatusText = computed(() => {
  if (!workbenchStatus.value?.center_ok) {
    return '中台未连接 · 工具层待启动'
  }

  const llmText = workbenchStatus.value.llm_configured ? 'LLM 已接入' : 'LLM 未配置'
  return `中台已连接 · ${llmText}`
})

const enabledCameras = computed(() => appConfig.value?.cameras.filter((camera) => camera.enabled) ?? [])

const selectedVideoCameras = computed(() => {
  const selectedIds = new Set(selectedVideoCameraIds.value)
  return enabledCameras.value.filter((camera) => selectedIds.has(camera.id))
})

const selectedVideoCameraLabel = computed(() => {
  if (!selectedVideoCameras.value.length) return '未选择摄像头'
  const names = selectedVideoCameras.value.map((camera) => camera.name)
  if (names.length <= 3) return names.join('、')
  return `${names.slice(0, 3).join('、')} 等 ${names.length} 路`
})

const videoDetectionSteps = computed<WorkflowStep[]>(() => {
  const hasSelection = selectedVideoCameraIds.value.length > 0
  const hasPrompt = refinedVideoPrompt.value.trim().length > 0
  const hasReport = currentVideoDetectionReport.value !== null
  const isPreparingPrompt = isPromptRefining.value || videoDetectionPhase.value === 'prompting'
  const isRunningDetection = isVideoDetecting.value || videoDetectionPhase.value === 'detecting'

  return [
    { id: 'select-camera', label: '选择通道', status: hasSelection ? 'done' : 'active' },
    {
      id: 'confirm-prompt',
      label: '确认 prompt',
      status: hasPrompt ? 'done' : isPreparingPrompt ? 'active' : hasSelection ? 'active' : 'pending',
    },
    { id: 'capture-frame', label: '截取当前帧', status: hasReport ? 'done' : isRunningDetection ? 'active' : 'pending' },
    { id: 'model-review', label: 'YOLO/GLM 分析', status: hasReport ? 'done' : isRunningDetection ? 'active' : 'pending' },
    { id: 'final-report', label: '生成结果', status: hasReport ? 'done' : 'pending' },
  ]
})

async function refreshWorkbenchSummary() {
  summaryLoadError.value = ''
  try {
    const summary = await getWorkbenchSummary()
    workbenchStatus.value = summary.status
    metrics.value = summary.metrics
    hazards.value = summary.hazards
    activities.value = summary.activities
    workflowSteps.value = summary.workflow_steps
  } catch (error) {
    summaryLoadError.value = error instanceof Error ? error.message : String(error)
    workbenchStatus.value = null
    metrics.value = []
    hazards.value = []
    activities.value = []
  }
}

onMounted(async () => {
  try {
    appConfig.value = await getAppConfig()
    selectedVideoCameraIds.value = enabledCameras.value[0]?.id ? [enabledCameras.value[0].id] : []
    await refreshWorkbenchSummary()
  } catch (error) {
    aiMessages.value.unshift(`赤瞳：后端连接失败：${error instanceof Error ? error.message : String(error)}`)
  }
})

async function handleCommand(payload: { message: string; area: string }) {
  aiMessages.value.unshift(`你：${payload.message}`)
  isSending.value = true
  workflowSteps.value = [
    { id: 'intent', label: '识别意图', status: 'active' },
    { id: 'tool', label: '调用工具', status: 'pending' },
    { id: 'confirm', label: '等待确认', status: 'pending' },
  ]

  try {
    const response = await sendChatMessage({
      message: payload.message,
      context: {
        current_area: payload.area,
        entry: 'workbench_command_bar',
      },
    })
    aiMessages.value.unshift(`赤瞳：${response.message}`)
    reviewCards.value = ((response.payload?.cards as ReviewCard[] | undefined) ?? []).map((card) => ({
      card_type: card.card_type,
      title: card.title,
      summary: card.summary,
      actions: card.actions,
      data: card.data,
    }))
    await refreshWorkbenchSummary()
    workflowSteps.value = [
      { id: 'intent', label: '识别意图', status: 'done' },
      { id: 'tool', label: '调用工具', status: 'done' },
      { id: 'confirm', label: '等待确认', status: response.type === 'review_card' ? 'active' : 'pending' },
    ]
  } catch (error) {
    aiMessages.value.unshift(`赤瞳：暂时无法连接中台：${error instanceof Error ? error.message : String(error)}`)
    workflowSteps.value = [
      { id: 'intent', label: '识别意图', status: 'done' },
      { id: 'tool', label: '调用工具', status: 'active' },
      { id: 'confirm', label: '等待确认', status: 'pending' },
    ]
  } finally {
    isSending.value = false
  }
}

async function handleReviewCardAction(actionId: string, card: ReviewCard) {
  isCardActionBusy.value = true
  try {
    const result = await sendCardAction({
      actionId,
      cardData: card.data ?? {},
    })
    const message = typeof result.message === 'string' ? result.message : '卡片动作已提交。'
    aiMessages.value.unshift(`赤瞳：${message}`)
    const navigateTo = typeof result.navigate_to === 'string' ? result.navigate_to : ''
    if (navigateTo === 'pending-confirmations' || result.confirmation) {
      goToPendingConfirmations()
    } else if (navigateTo === 'visual-patrol') {
      goTo('visual-patrol')
    } else if (navigateTo === 'shanshan-doc' || actionId === 'open_shanshan_doc') {
      goTo('shanshan-doc')
    } else if (navigateTo === 'smart-form') {
      goTo('smart-form')
    }
    await refreshWorkbenchSummary()
  } catch (error) {
    aiMessages.value.unshift(`赤瞳：卡片动作失败：${error instanceof Error ? error.message : String(error)}`)
  } finally {
    isCardActionBusy.value = false
  }
}

async function handleConfirmHazard(caseId: string) {
  if (!/^\d+$/.test(caseId)) {
    aiMessages.value.unshift('赤瞳：当前为演示隐患，启动中台和工具层后可执行确认。')
    return
  }

  try {
    await updateHazardStatus(caseId, 'confirmed')
    aiMessages.value.unshift(`赤瞳：已确认隐患 #${caseId}，台账已刷新。`)
    await refreshWorkbenchSummary()
  } catch (error) {
    aiMessages.value.unshift(`赤瞳：隐患确认失败：${error instanceof Error ? error.message : String(error)}`)
  }
}

async function handleVisualPatrol(cameraId?: string) {
  isPatrolling.value = true
  workflowSteps.value = [
    { id: 'snapshot', label: 'RTMP 截图', status: 'active' },
    { id: 'vlm', label: 'VLM 检测', status: 'pending' },
    { id: 'confirm', label: '人工确认', status: 'pending' },
  ]

  try {
    const camera =
      appConfig.value?.cameras.find((item) => item.id === cameraId) ??
      appConfig.value?.cameras.find((item) => item.enabled) ??
      appConfig.value?.cameras[0]
    const draft = await draftVisualPatrol({
      area: camera?.area ?? appConfig.value?.project.default_area ?? 'B2',
      cameraUrl: camera?.rtmp_url ?? undefined,
      count: 1,
    })
    workflowSteps.value = [
      { id: 'snapshot', label: 'RTMP 截图', status: 'done' },
      { id: 'vlm', label: 'VLM 检测', status: 'done' },
      { id: 'confirm', label: '人工确认', status: 'active' },
    ]
    aiMessages.value.unshift(draft.message || '赤瞳：视觉巡检已生成隐患候选，请进入视觉巡检页确认。')
  } catch (error) {
    aiMessages.value.unshift(`赤瞳：视觉巡检失败：${error instanceof Error ? error.message : String(error)}`)
    workflowSteps.value = [
      { id: 'snapshot', label: 'RTMP 截图', status: 'active' },
      { id: 'vlm', label: 'VLM 检测', status: 'pending' },
      { id: 'confirm', label: '人工确认', status: 'pending' },
    ]
  } finally {
    isPatrolling.value = false
  }
}

function toggleVideoCamera(cameraId: string) {
  if (selectedVideoCameraIds.value.includes(cameraId)) {
    selectedVideoCameraIds.value = selectedVideoCameraIds.value.filter((id) => id !== cameraId)
  } else {
    selectedVideoCameraIds.value = [...selectedVideoCameraIds.value, cameraId]
  }
}

function selectAllVideoCameras() {
  selectedVideoCameraIds.value = enabledCameras.value.map((camera) => camera.id)
}

function clearVideoCameras() {
  selectedVideoCameraIds.value = []
}

async function handleRefineVideoPrompt() {
  const direction = videoDetectionDirection.value.trim()
  if (!direction) {
    videoDetectionError.value = '请先输入检测方向。'
    videoDetectionPhase.value = 'error'
    return false
  }
  if (!selectedVideoCameraIds.value.length) {
    videoDetectionError.value = '请至少选择一路摄像头。'
    videoDetectionPhase.value = 'error'
    return false
  }

  isPromptRefining.value = true
  videoDetectionError.value = ''
  videoDetectionPhase.value = 'prompting'
  workflowSteps.value = [
    { id: 'prompt', label: '润色检测提示词', status: 'active' },
    { id: 'detect', label: 'YOLO+GLM 检测', status: 'pending' },
    { id: 'report', label: '生成简报', status: 'pending' },
  ]

  try {
    const prompt = await refineWorkbenchVideoDetectionPrompt({
      detectionDirection: direction,
      cameraIds: selectedVideoCameraIds.value,
    })
    if (!prompt.ok || !prompt.refined_prompt) {
      throw new Error(prompt.message || prompt.error || '提示词润色失败')
    }
    refinedVideoPrompt.value = prompt.refined_prompt
    videoPromptSource.value = prompt.prompt_source || ''
    videoPromptPolicyContext.value = prompt.policy_context ?? []
    workflowSteps.value = [
      { id: 'prompt', label: '润色检测提示词', status: 'done' },
      { id: 'detect', label: 'YOLO+GLM 检测', status: 'pending' },
      { id: 'report', label: '生成简报', status: 'pending' },
    ]
    videoDetectionPhase.value = 'ready'
    aiMessages.value.unshift(`赤瞳：已生成可编辑检测提示词，覆盖 ${selectedVideoCameraIds.value.length} 路摄像头。`)
    return true
  } catch (error) {
    videoDetectionError.value = error instanceof Error ? error.message : String(error)
    videoDetectionPhase.value = 'error'
    aiMessages.value.unshift(`赤瞳：提示词润色失败：${videoDetectionError.value}`)
    return false
  } finally {
    isPromptRefining.value = false
  }
}

async function handleWorkbenchVideoDetection() {
  const direction = videoDetectionDirection.value.trim()
  if (!direction) {
    videoDetectionError.value = '请先输入检测方向。'
    videoDetectionPhase.value = 'error'
    return
  }
  if (!selectedVideoCameraIds.value.length) {
    videoDetectionError.value = '请至少选择一路摄像头。'
    videoDetectionPhase.value = 'error'
    return
  }
  if (!refinedVideoPrompt.value.trim()) {
    const refined = await handleRefineVideoPrompt()
    if (!refined) return
  }

  isVideoDetecting.value = true
  videoDetectionError.value = ''
  videoDetectionPhase.value = 'detecting'
  currentVideoDetectionReport.value = null
  workflowSteps.value = [
    { id: 'prompt', label: '确认检测提示词', status: 'done' },
    { id: 'detect', label: 'YOLO+GLM 检测', status: 'active' },
    { id: 'report', label: '生成简报', status: 'pending' },
  ]

  try {
    const report = await runWorkbenchVideoDetection({
      detectionDirection: direction,
      cameraIds: selectedVideoCameraIds.value,
      refinedPrompt: refinedVideoPrompt.value.trim(),
      vlmEnabled: true,
    })
    if (!report.ok) {
      throw new Error(report.message || report.error || '视频检测失败')
    }
    currentVideoDetectionReport.value = report
    videoDetectionPhase.value = 'done'
    aiMessages.value.unshift(`赤瞳：${report.summary.text}`)
    workflowSteps.value = [
      { id: 'prompt', label: '确认检测提示词', status: 'done' },
      { id: 'detect', label: 'YOLO+GLM 检测', status: 'done' },
      { id: 'report', label: '生成简报', status: 'done' },
    ]
    await refreshWorkbenchSummary()
  } catch (error) {
    videoDetectionError.value = error instanceof Error ? error.message : String(error)
    videoDetectionPhase.value = 'error'
    aiMessages.value.unshift(`赤瞳：视频检测失败：${videoDetectionError.value}`)
    workflowSteps.value = [
      { id: 'prompt', label: '润色检测提示词', status: 'done' },
      { id: 'detect', label: 'YOLO+GLM 检测', status: 'active' },
      { id: 'report', label: '生成简报', status: 'pending' },
    ]
  } finally {
    isVideoDetecting.value = false
  }
}

async function handleCaseWorkflow(action: 'rectification-notice' | 'contractor-confirm' | 'close-review', caseId: string) {
  if (!/^\d+$/.test(caseId)) {
    aiMessages.value.unshift('赤瞳：当前为演示隐患，真实台账记录才可执行闭环动作。')
    return
  }

  try {
    const result = await runCaseWorkflow(action, {
      caseId,
      contractor: appConfig.value?.contractors[0]?.name ?? '待确认分包商',
      dueDate: new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10),
      notes: 'Confirmed from Chitung desktop workbench.',
      reviewer: '安全主任',
    })
    if (action === 'rectification-notice') {
      const contractor = appConfig.value?.contractors[0]
      notificationDraft.value = {
        caseId,
        contractor: contractor?.name ?? '待确认分包商',
        contact: contractor?.contact,
        channel: contractor?.channel,
        draftText: String((result.notice as Record<string, unknown> | undefined)?.draft_text || result.message || '整改通知草稿已生成。'),
        status: 'draft',
      }
    }
    aiMessages.value.unshift(`赤瞳：${String(result.message || '隐患闭环动作已完成')}`)
    await refreshWorkbenchSummary()
  } catch (error) {
    aiMessages.value.unshift(`赤瞳：隐患闭环动作失败：${error instanceof Error ? error.message : String(error)}`)
  }
}

async function confirmNotificationDraft() {
  if (!notificationDraft.value) return
  try {
    const channel = notificationDraft.value.channel?.toLowerCase().includes('whatsapp') ? 'whatsapp' : 'feishu'
    const sendResult = await sendCaseNotification({
      caseId: notificationDraft.value.caseId,
      text: notificationDraft.value.draftText,
      contractor: notificationDraft.value.contractor,
      channel,
    })
    await runCaseWorkflow('contractor-confirm', {
      caseId: notificationDraft.value.caseId,
      contractor: notificationDraft.value.contractor,
      dueDate: new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10),
      notes: `Notification draft confirmed for ${notificationDraft.value.contractor}.`,
    })
    notificationDraft.value = { ...notificationDraft.value, status: 'confirmed' }
    aiMessages.value.unshift(`赤瞳：整改通知已确认：${String(sendResult.message || '发送结果已回写。')}`)
    await refreshWorkbenchSummary()
  } catch (error) {
    aiMessages.value.unshift(`赤瞳：整改通知确认失败：${error instanceof Error ? error.message : String(error)}`)
  }
}

</script>

<template>
  <main class="workbench">
    <section class="hero-panel">
      <div>
        <p class="eyebrow">Chitung Workbench</p>
        <h1>赤瞳安全智能平台</h1>
        <p>用一个工作台连接隐患、视频、聊天、表格、外部风险和 AI 确认闭环。</p>
      </div>
      <div class="hero-panel__status">
        <span
          class="status-dot"
          :class="workbenchStatus?.center_ok ? 'status-dot--green' : 'status-dot--orange'"
        />
        {{ centerStatusText }}
      </div>
    </section>

    <CommandBar @submit="handleCommand" />

    <ActionReviewCards
      :cards="reviewCards"
      :busy="isCardActionBusy"
      @action="handleReviewCardAction"
    />

    <section class="video-detection-workflow">
      <div class="video-detection-workflow__top">
        <section class="panel video-detection-panel">
          <div class="panel__header">
            <div>
              <h2>视频检测</h2>
              <p>输入检测方向，选择摄像头，后台会结合制度知识库润色 prompt 并调用 YOLO + GLM。</p>
            </div>
          </div>
          <div class="video-detection-controls">
            <input
              v-model="videoDetectionDirection"
              class="video-detection-input"
              placeholder="检测方向，例如：检查未戴安全帽、机械靠近人员、临边防护缺失"
            />
            <button
              class="mini-button"
              :disabled="isPromptRefining || isVideoDetecting || !enabledCameras.length"
              @click="handleRefineVideoPrompt"
            >
              {{ isPromptRefining ? '润色中' : '公司制度润色' }}
            </button>
            <button
              class="primary-soft-button video-detection-run"
              :disabled="isVideoDetecting || isPromptRefining || !enabledCameras.length"
              @click="handleWorkbenchVideoDetection"
            >
              {{ isVideoDetecting ? '检测中' : '开始检测' }}
            </button>
          </div>

          <div class="video-camera-picker">
            <div class="video-camera-picker__toolbar">
              <span>已选 {{ selectedVideoCameraIds.length }} / {{ enabledCameras.length }} 路</span>
              <button class="mini-button" type="button" @click="selectAllVideoCameras">全选</button>
              <button class="mini-button" type="button" @click="clearVideoCameras">清空</button>
            </div>
            <label
              v-for="camera in enabledCameras"
              :key="camera.id"
              class="video-camera-option"
              :class="{ 'video-camera-option--selected': selectedVideoCameraIds.includes(camera.id) }"
            >
              <input
                type="checkbox"
                :checked="selectedVideoCameraIds.includes(camera.id)"
                @change="toggleVideoCamera(camera.id)"
              />
              <span>{{ camera.name }}</span>
              <small>{{ camera.area }}</small>
            </label>
          </div>

          <details class="video-prompt-settings">
            <summary>编辑 prompt</summary>
            <div class="video-prompt-block">
              <div class="video-prompt-block__head">
                <span>润色后的 prompt</span>
                <small v-if="videoPromptSource">来源：{{ videoPromptSource }}</small>
              </div>
              <textarea
                v-model="refinedVideoPrompt"
                class="video-prompt-editor"
                rows="5"
                placeholder="点击“公司制度润色”生成，也可以在这里直接输入或修改给 YOLO + GLM 的检测提示词。"
              />
              <small v-if="videoPromptPolicyContext.length" class="video-prompt-context">
                制度依据：{{ videoPromptPolicyContext.slice(0, 2).join('；') }}
              </small>
            </div>
          </details>
        </section>

        <CctvLivePanel
          compact
          title="CCTV 实时画面"
          subtitle="左侧勾选摄像头后，点击开始检测截取当前画面"
          :busy="isPatrolling"
          :show-action="false"
          action-label="巡检当前画面"
          busy-label="巡检中"
          @patrol="handleVisualPatrol"
        />
      </div>

      <div class="video-detection-workflow__bottom">
        <section class="panel video-detection-process">
          <div class="panel__header">
            <div>
              <h2>中间过程</h2>
              <p>展示这次视频检测从选路到生成结果的状态。</p>
            </div>
          </div>
          <div class="video-frame-mode">
            <strong>帧选择方式</strong>
            <p>点击开始检测时，从所选摄像头实时流截取当前帧；实时流不可用时优先使用 C-SMART 截图，最后才使用本地预设回退帧。</p>
          </div>
          <ProgressChain :steps="videoDetectionSteps" />
          <div class="video-process-list">
            <article
              class="video-process-card"
              :class="selectedVideoCameraIds.length ? 'video-process-card--done' : 'video-process-card--active'"
            >
              <span>1</span>
              <div>
                <strong>选择摄像头</strong>
                <p>{{ selectedVideoCameraIds.length }} 路 · {{ selectedVideoCameraLabel }}</p>
              </div>
            </article>
            <article
              class="video-process-card"
              :class="refinedVideoPrompt ? 'video-process-card--done' : isPromptRefining ? 'video-process-card--active' : ''"
            >
              <span>2</span>
              <div>
                <strong>润色并确认 prompt</strong>
                <p>{{ refinedVideoPrompt ? '已生成，可在上方展开修改' : '等待润色或手动输入' }}</p>
              </div>
            </article>
            <article
              class="video-process-card"
              :class="currentVideoDetectionReport ? 'video-process-card--done' : isVideoDetecting ? 'video-process-card--active' : ''"
            >
              <span>3</span>
              <div>
                <strong>截取视频帧并检测</strong>
                <p>{{ isVideoDetecting ? '正在截取当前帧并调用 YOLO/GLM' : currentVideoDetectionReport ? '已完成当前帧检测' : '等待开始检测' }}</p>
              </div>
            </article>
            <article
              class="video-process-card"
              :class="currentVideoDetectionReport ? 'video-process-card--done' : ''"
            >
              <span>4</span>
              <div>
                <strong>生成证据和简报</strong>
                <p>{{ currentVideoDetectionReport ? '证据图片和详细历史已写入隐患台账' : '结果会在右侧最终结果区展示' }}</p>
              </div>
            </article>
          </div>
        </section>

        <section class="panel video-detection-final">
          <div class="panel__header">
            <div>
              <h2>最终结果</h2>
              <p>只显示当前检测结论，详细图片和历史报告进入隐患台账。</p>
            </div>
            <span v-if="currentVideoDetectionReport" class="diff-status diff-status--accepted">
              {{ currentVideoDetectionReport.summary.severity }}
            </span>
          </div>
          <div v-if="currentVideoDetectionReport" class="video-result-card">
            <span class="video-detection-report__meta">
              检测结论 · {{ currentVideoDetectionReport.camera_count || 1 }} 路 · {{ currentVideoDetectionReport.summary.detection_count }} 个目标
            </span>
            <h3>{{ currentVideoDetectionReport.summary.title }}</h3>
            <div class="video-result-stats">
              <span>
                <small>检测路数</small>
                <strong>{{ currentVideoDetectionReport.camera_count || selectedVideoCameraIds.length || 1 }}</strong>
              </span>
              <span>
                <small>目标数量</small>
                <strong>{{ currentVideoDetectionReport.summary.detection_count }}</strong>
              </span>
              <span>
                <small>风险等级</small>
                <strong>{{ currentVideoDetectionReport.summary.severity }}</strong>
              </span>
            </div>
            <p class="video-result-text">{{ currentVideoDetectionReport.summary.text }}</p>
            <div v-if="currentVideoDetectionReport.summary.labels.length" class="video-label-list">
              <span v-for="label in currentVideoDetectionReport.summary.labels" :key="label">{{ label }}</span>
            </div>
            <p v-if="currentVideoDetectionReport.summary.suggested_action" class="video-result-action">
              {{ currentVideoDetectionReport.summary.suggested_action }}
            </p>
            <div class="video-detection-report__actions">
              <button class="primary-soft-button" type="button" @click="goTo('hazard-ledger')">查看证据</button>
            </div>
          </div>
          <div v-else-if="videoDetectionError" class="video-result-empty video-result-empty--error">
            <strong>检测失败</strong>
            <p>{{ videoDetectionError }}</p>
          </div>
          <div v-else class="video-result-empty">
            <strong>等待开始检测</strong>
            <p>选择摄像头并确认 prompt 后，最终结论、目标数和证据入口会显示在这里。</p>
          </div>
        </section>
      </div>
    </section>

    <StatusStrip :metrics="metrics" />

    <section class="workbench-grid">
      <ActiveHazards
        :hazards="hazards"
        @confirm="handleConfirmHazard"
        @workflow="handleCaseWorkflow"
        @view-all="goTo('hazard-ledger')"
      />
      <section class="panel">
        <div class="panel__header">
          <div>
            <h2>AI 执行进度</h2>
            <p>{{ isSending ? '正在等待中台响应' : '展示最近一次工具链状态' }}</p>
          </div>
        </div>
        <ProgressChain :steps="workflowSteps" />
        <div class="ai-message-list">
          <p v-for="msg in aiMessages.slice(0, 3)" :key="msg">{{ msg }}</p>
        </div>
      </section>
      <section v-if="notificationDraft" class="panel notification-draft-panel">
        <div class="panel__header">
          <div>
            <h2>整改通知确认卡</h2>
            <p>{{ notificationDraft.contractor }} · {{ notificationDraft.channel || notificationDraft.contact || '待补充联系方式' }}</p>
          </div>
          <span class="diff-status" :class="`diff-status--${notificationDraft.status === 'confirmed' ? 'accepted' : 'draft'}`">
            {{ notificationDraft.status === 'confirmed' ? '已确认' : '待人工确认' }}
          </span>
        </div>
        <pre class="notification-draft-text">{{ notificationDraft.draftText }}</pre>
        <div class="file-actions-bar">
          <button class="mini-button" @click="notificationDraft = null">取消</button>
          <button class="primary-soft-button" @click="confirmNotificationDraft">确认通知</button>
        </div>
      </section>
    </section>

    <ActivityFeed :items="activities" @open-confirmations="goToPendingConfirmations" />
  </main>
</template>

<style scoped>
.video-detection-workflow {
  display: grid;
  gap: 16px;
  margin-bottom: 16px;
}

.video-detection-workflow__top,
.video-detection-workflow__bottom {
  align-items: stretch;
  display: grid;
  gap: 16px;
}

.video-detection-workflow__top {
  grid-template-columns: minmax(380px, 0.88fr) minmax(560px, 1.12fr);
}

.video-detection-workflow__bottom {
  grid-template-columns: minmax(420px, 1fr) minmax(420px, 1fr);
}

.video-detection-panel,
.video-detection-process,
.video-detection-final {
  min-width: 0;
}

.video-detection-panel {
  display: flex;
  flex-direction: column;
}

.video-detection-workflow :deep(.cctv-live-panel) {
  height: 100%;
  min-width: 0;
}

.video-detection-workflow :deep(.cctv-live-panel__metrics) {
  display: none;
}

.video-detection-controls {
  display: grid;
  gap: 10px;
  grid-template-columns: minmax(0, 1fr) auto auto;
}

.video-detection-input {
  background: var(--bg-white);
  border: 1px solid var(--border-normal);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 14px;
  min-width: 0;
  padding: 9px 11px;
}

.video-detection-run {
  min-width: 92px;
}

.video-camera-picker {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
  max-height: 178px;
  overflow-y: auto;
  padding: 10px;
}

.video-camera-picker__toolbar {
  align-items: center;
  color: var(--text-secondary);
  display: flex;
  flex-basis: 100%;
  gap: 8px;
  font-size: 12px;
}

.video-camera-option {
  align-items: center;
  background: var(--bg-white);
  border: 1px solid var(--border-normal);
  border-radius: var(--radius-sm);
  cursor: pointer;
  display: inline-flex;
  gap: 6px;
  min-height: 31px;
  padding: 5px 8px;
}

.video-camera-option input {
  margin: 0;
}

.video-camera-option span {
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 700;
}

.video-camera-option small {
  color: var(--text-secondary);
  font-size: 12px;
}

.video-camera-option--selected {
  border-color: var(--brand-blue);
  box-shadow: inset 0 0 0 1px var(--brand-blue);
}

.video-prompt-block {
  display: grid;
  gap: 6px;
  margin-top: 10px;
}

.video-prompt-block__head {
  align-items: center;
  display: flex;
  justify-content: space-between;
}

.video-prompt-block__head span {
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 800;
}

.video-prompt-block__head small,
.video-prompt-context {
  color: var(--text-secondary);
  font-size: 12px;
}

.video-prompt-editor {
  background: var(--bg-white);
  border: 1px solid var(--border-normal);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.55;
  min-height: 118px;
  padding: 10px 11px;
  resize: vertical;
  width: 100%;
}

.video-frame-mode {
  background: var(--bg-subtle);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  display: grid;
  gap: 4px;
  margin-bottom: 14px;
  padding: 10px 12px;
}

.video-frame-mode strong,
.video-process-card strong {
  color: var(--text-primary);
  font-size: 13px;
}

.video-frame-mode p,
.video-process-card p {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.45;
  margin: 0;
}

.video-process-list {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.video-process-card {
  align-items: flex-start;
  background: var(--bg-white);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  display: grid;
  gap: 10px;
  grid-template-columns: 28px minmax(0, 1fr);
  padding: 10px;
}

.video-process-card > span {
  align-items: center;
  background: var(--bg-subtle);
  border-radius: 999px;
  color: var(--text-secondary);
  display: inline-flex;
  font-size: 12px;
  font-weight: 800;
  height: 24px;
  justify-content: center;
  width: 24px;
}

.video-process-card--active {
  border-color: var(--brand-red);
  box-shadow: inset 3px 0 0 var(--brand-red);
}

.video-process-card--done {
  border-color: rgba(60, 172, 48, 0.35);
  box-shadow: inset 3px 0 0 #3cac30;
}

.video-result-card {
  display: grid;
  gap: 12px;
}

.video-result-card h3 {
  font-size: 15px;
  margin: 0;
}

.video-result-text,
.video-result-action {
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.55;
  margin: 0;
}

.video-detection-report__meta {
  color: var(--text-secondary);
  display: block;
  font-size: 12px;
  overflow-wrap: anywhere;
}

.video-result-stats {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.video-result-stats span {
  background: var(--bg-subtle);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  display: grid;
  gap: 3px;
  padding: 9px 10px;
}

.video-result-stats small {
  color: var(--text-secondary);
  font-size: 11px;
}

.video-result-stats strong {
  color: var(--text-primary);
  font-size: 18px;
}

.video-label-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.video-label-list span {
  background: rgba(237, 28, 36, 0.08);
  border: 1px solid rgba(237, 28, 36, 0.18);
  border-radius: 999px;
  color: var(--brand-red);
  font-size: 12px;
  font-weight: 700;
  padding: 4px 8px;
}

.video-detection-report__actions {
  align-items: flex-start;
  display: flex;
  flex-shrink: 0;
  gap: 8px;
}

.video-result-empty {
  align-content: center;
  background: var(--bg-subtle);
  border: 1px dashed var(--border-normal);
  border-radius: var(--radius-md);
  display: grid;
  min-height: 136px;
  padding: 18px;
  text-align: center;
}

.video-result-empty strong {
  color: var(--text-primary);
  font-size: 16px;
}

.video-result-empty p {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.5;
  margin: 8px 0 0;
}

.video-result-empty--error {
  background: rgba(237, 28, 36, 0.06);
  border-color: rgba(237, 28, 36, 0.22);
}

.video-result-empty--error strong {
  color: var(--brand-red);
}

.video-prompt-settings {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  margin-top: 10px;
  padding: 8px 10px;
}

.video-prompt-settings summary {
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
  list-style-position: inside;
}

.video-prompt-settings:not([open]) .video-prompt-block {
  display: none;
}

@media (max-width: 1100px) {
  .video-detection-workflow__top,
  .video-detection-workflow__bottom {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 820px) {
  .video-detection-controls,
  .video-result-stats {
    grid-template-columns: 1fr;
  }

}
</style>
