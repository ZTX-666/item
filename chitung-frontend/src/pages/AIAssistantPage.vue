<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useAiAssistant } from '../composables/useAiAssistant'
import ChatRichBlocks from '../components/chat/ChatRichBlocks.vue'
import { getSkills, getWorkflowTemplates } from '../services/chitungApi'
import type { SkillInfo, WorkflowTemplateInfo } from '../types/domain'

interface ParamField {
  key: string
  label: string
  placeholder: string
  textarea?: boolean
}

interface AssistantEntry {
  id: string
  kind: 'skill' | 'workflow'
  name: string
  title: string
  description: string
  status?: string
  enabled?: boolean
  tools?: string[]
  intent?: string
  workflowName?: string
  promptTemplate: string
  paramFields: ParamField[]
  defaultParams: Record<string, string>
}

const skillParamPresets: Record<string, { title: string; prompt: string; fields: ParamField[]; params: Record<string, string> }> = {
  'daily-risk-briefing': {
    title: '每日风险简报',
    prompt: '生成每日安全风险简报',
    fields: [
      { key: 'project_scope', label: '项目范围', placeholder: '例如：香港项目' },
      { key: 'topics', label: '关注主题', placeholder: '例如：施工安全、天气预警、工伤意外', textarea: true },
      { key: 'sources', label: '数据源', placeholder: '例如：天文台、政府新闻公报、劳工处' },
      { key: 'output', label: '输出形式', placeholder: '例如：图文简报草稿' },
    ],
    params: {
      project_scope: '香港项目',
      topics: '施工安全、天气预警、工伤意外',
      sources: '天文台、政府新闻公报、劳工处',
      output: '图文简报草稿',
    },
  },
  'hazard-intake': {
    title: '隐患线索入库',
    prompt: '把以下现场信息作为安全隐患线索处理',
    fields: [
      { key: 'hazard_text', label: '隐患描述', placeholder: '例如：B2 区临边护栏缺失', textarea: true },
      { key: 'area', label: '区域', placeholder: '例如：B2 区' },
      { key: 'contractor', label: '责任单位', placeholder: '例如：分判商 A' },
      { key: 'due_date', label: '整改期限', placeholder: '例如：今天 18:00 前' },
    ],
    params: {
      hazard_text: '现场存在待核实安全隐患，请归档并生成后续动作卡片',
      area: '',
      contractor: '',
      due_date: '',
    },
  },
  'knowledge-query': {
    title: '知识库问答',
    prompt: '查询知识库并结合制度文档回答以下问题',
    fields: [
      { key: 'question', label: '问题', placeholder: '例如：临边作业护栏高度和整改闭环要求是什么？', textarea: true },
      { key: 'top_k', label: '引用数量', placeholder: '例如：5' },
    ],
    params: {
      question: '临边作业安全管理要求是什么？',
      top_k: '5',
    },
  },
  'shanshan-doc': {
    title: '文档/表格处理',
    prompt: '按以下要求查找或处理安全文档表格',
    fields: [
      { key: 'document_task', label: '任务', placeholder: '例如：查找高处作业检查表模板', textarea: true },
      { key: 'template_keyword', label: '模板关键词', placeholder: '例如：高处作业 检查表' },
    ],
    params: {
      document_task: '查找高处作业相关检查表模板',
      template_keyword: '高处作业',
    },
  },
  'visual-patrol': {
    title: '视频巡检',
    prompt: '按以下要求执行视频巡检',
    fields: [
      { key: 'detection_direction', label: '检测方向', placeholder: '例如：检查人员 PPE 与机械作业半径风险', textarea: true },
      { key: 'camera_ids', label: '摄像头编号', placeholder: '例如：cam-3 或 cam-1,cam-3' },
      { key: 'frame_source', label: '抽帧方式', placeholder: '例如：实时流截取当前帧' },
    ],
    params: {
      detection_direction: '检查人员 PPE 合规、机械作业半径和临边风险',
      camera_ids: '',
      frame_source: '实时流截取当前帧',
    },
  },
  'whatsapp-sql-query': {
    title: 'WhatsApp 本地库查询',
    prompt: '读取 WhatsApp 本地 SQLite 数据',
    fields: [
      { key: 'question', label: '查询问题', placeholder: '例如：查看 WhatsApp 本地数据库有哪些表', textarea: true },
      { key: 'sql', label: 'SELECT', placeholder: '可选，例如：SELECT * FROM messages ORDER BY ts DESC' },
      { key: 'limit', label: '返回行数', placeholder: '例如：20' },
    ],
    params: {
      question: '查看 WhatsApp 本地数据库有哪些表',
      sql: '',
      limit: '20',
    },
  },
  'whatsapp-wacli-ops': {
    title: 'WhatsApp 命令诊断',
    prompt: '执行 WhatsApp wacli 只读诊断',
    fields: [
      { key: 'task', label: '任务', placeholder: '例如：查看 WhatsApp 登录状态，或搜索整改消息', textarea: true },
      { key: 'args', label: 'wacli 参数', placeholder: '可选，例如：auth status' },
    ],
    params: {
      task: '查看 WhatsApp 登录状态',
      args: '',
    },
  },
}

const workflowParamPresets: Record<string, { prompt: string; fields: ParamField[]; params: Record<string, string> }> = {
  workflow_weather_query: {
    prompt: '查询香港天气并给出现场安全提示',
    fields: [{ key: 'question', label: '查询内容', placeholder: '例如：香港天气如何' }],
    params: { question: '香港天气如何' },
  },
}

const {
  messages,
  inputText,
  isTyping,
  messagesEl,
  loadLatestHistory,
  sendMessage,
  setDraft,
  handleKeydown,
  toolName,
  toolOk,
  toolSummary,
  cardTitle,
  cardActions,
  cardActionLabel,
  actionKey,
  actionRunning,
  handleCardAction,
  appliedSkillName,
  skillHighlights,
  skillNextActions,
  resultImages,
  resultReports,
} = useAiAssistant()

const backendSkills = ref<SkillInfo[]>([])
const workflowTemplates = ref<WorkflowTemplateInfo[]>([])
const selectedEntry = ref<AssistantEntry | null>(null)
const entryParams = ref<Record<string, string>>({})
const catalogLoading = ref(false)
const catalogError = ref('')

const skillEntries = computed<AssistantEntry[]>(() =>
  backendSkills.value.map((skill) => {
    const preset = skillParamPresets[skill.name] ?? {
      title: skill.name,
      prompt: `调用 ${skill.name} 技能处理以下任务`,
      fields: [{ key: 'task', label: '任务参数', placeholder: '请输入任务要求', textarea: true }],
      params: { task: skill.summary || skill.name },
    }
    return {
      id: `skill:${skill.name}`,
      kind: 'skill',
      name: skill.name,
      title: preset.title,
      description: skill.summary,
      status: skill.status,
      enabled: skill.enabled,
      tools: skill.tools ?? [],
      workflowName: skill.workflow || '',
      promptTemplate: preset.prompt,
      paramFields: preset.fields,
      defaultParams: preset.params,
    }
  }),
)

const workflowEntries = computed<AssistantEntry[]>(() =>
  workflowTemplates.value.map((workflow) => {
    const preset = workflowParamPresets[workflow.workflow_name] ?? {
      prompt: `运行工作流：${workflow.title}`,
      fields: [{ key: 'message', label: '任务参数', placeholder: workflow.description, textarea: true }],
      params: { message: workflow.description },
    }
    return {
      id: `workflow:${workflow.workflow_name}`,
      kind: 'workflow',
      name: workflow.workflow_name,
      title: workflow.title,
      description: workflow.description,
      intent: workflow.intent,
      workflowName: workflow.workflow_name,
      promptTemplate: preset.prompt,
      paramFields: preset.fields,
      defaultParams: preset.params,
    }
  }),
)

const paramFields = computed(() => selectedEntry.value?.paramFields ?? [])

function bindMessagesEl(el: unknown) {
  messagesEl.value = el instanceof HTMLElement ? el : null
}

onMounted(() => {
  loadLatestHistory()
  loadCatalog()
})

watch(
  entryParams,
  () => {
    if (!selectedEntry.value) return
    setDraft(buildEntryPrompt(selectedEntry.value), buildEntryMetadata(selectedEntry.value))
  },
  { deep: true },
)

async function loadCatalog() {
  catalogLoading.value = true
  catalogError.value = ''
  try {
    const [skills, workflows] = await Promise.all([getSkills(), getWorkflowTemplates()])
    backendSkills.value = skills
    workflowTemplates.value = workflows
    if (!selectedEntry.value && skillEntries.value.length) selectEntry(skillEntries.value[0])
  } catch (error) {
    catalogError.value = error instanceof Error ? error.message : String(error)
  } finally {
    catalogLoading.value = false
  }
}

function selectEntry(entry: AssistantEntry) {
  selectedEntry.value = entry
  entryParams.value = { ...entry.defaultParams }
  setDraft(buildEntryPrompt(entry), buildEntryMetadata(entry))
}

function runSelectedEntry() {
  if (!selectedEntry.value) return
  inputText.value = buildEntryPrompt(selectedEntry.value)
  sendMessage(buildEntryMetadata(selectedEntry.value))
}

function buildEntryPrompt(entry: AssistantEntry) {
  const lines = [entry.promptTemplate]
  for (const field of entry.paramFields) {
    const value = entryParams.value[field.key]?.trim()
    if (value) lines.push(`${field.label}：${value}`)
  }
  return lines.join('\n')
}

function buildEntryMetadata(entry: AssistantEntry): Record<string, unknown> {
  const params = { ...entryParams.value }
  const metadata: Record<string, unknown> = {
    assistant_entry_kind: entry.kind,
    assistant_entry_name: entry.name,
    assistant_entry_params: params,
  }
  if (entry.kind === 'skill') metadata.skill_name = entry.name
  if (entry.kind === 'workflow') metadata.workflow_name = entry.workflowName
  if (entry.intent) metadata.intent = entry.intent
  if (params.camera_ids) {
    metadata.camera_ids = params.camera_ids
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)
  }
  if (params.detection_direction) metadata.detection_direction = params.detection_direction
  return metadata
}
</script>

<template>
  <main class="assistant-page">
    <section class="assistant-page__hero panel">
      <div>
        <p class="eyebrow">CHITUNG AI ORCHESTRATOR</p>
        <h2>赤瞳 AI 助手</h2>
        <p>这里和左下角机器人使用同一个会话、同一套 Skill 入口、同一个中台编排接口。</p>
      </div>
      <div class="assistant-page__status">
        <span :class="{ 'assistant-page__dot--active': !isTyping }" class="assistant-page__dot"></span>
        <strong>{{ isTyping ? '执行中' : '待命' }}</strong>
      </div>
    </section>

    <section class="assistant-workspace">
      <aside class="assistant-skills panel">
        <div>
          <h3>后台能力入口</h3>
          <p>来自 `/api/skills` 和 `/api/workflows/templates`，选中后可改参数再执行。</p>
        </div>
        <p v-if="catalogLoading" class="assistant-catalog-note">正在加载后台技能...</p>
        <p v-if="catalogError" class="assistant-catalog-error">{{ catalogError }}</p>

        <div class="assistant-entry-section">
          <h4>Skills</h4>
          <div class="assistant-skill-grid">
            <button
              v-for="entry in skillEntries"
              :key="entry.id"
              class="assistant-skill"
              :class="{ 'assistant-skill--active': selectedEntry?.id === entry.id }"
              :disabled="isTyping || entry.enabled === false"
              @click="selectEntry(entry)"
            >
              <span class="assistant-skill__kind">{{ entry.name }}</span>
              <strong>{{ entry.title }}</strong>
              <small>{{ entry.description }}</small>
              <em>{{ entry.status || 'ready' }}</em>
            </button>
          </div>
        </div>

        <div class="assistant-entry-section">
          <h4>Workflows</h4>
          <div class="assistant-skill-grid">
            <button
              v-for="entry in workflowEntries"
              :key="entry.id"
              class="assistant-skill"
              :class="{ 'assistant-skill--active': selectedEntry?.id === entry.id }"
              :disabled="isTyping"
              @click="selectEntry(entry)"
            >
              <span class="assistant-skill__kind">{{ entry.name }}</span>
              <strong>{{ entry.title }}</strong>
              <small>{{ entry.description }}</small>
              <em>{{ entry.intent }}</em>
            </button>
          </div>
        </div>

        <div v-if="selectedEntry" class="assistant-params">
          <div>
            <h4>参数</h4>
            <p>{{ selectedEntry.kind === 'skill' ? 'Skill' : 'Workflow' }}: {{ selectedEntry.name }}</p>
          </div>
          <label v-for="field in paramFields" :key="field.key" class="assistant-param">
            <span>{{ field.label }}</span>
            <textarea
              v-if="field.textarea"
              v-model="entryParams[field.key]"
              rows="3"
              :placeholder="field.placeholder"
            />
            <input v-else v-model="entryParams[field.key]" :placeholder="field.placeholder" />
          </label>
          <div v-if="selectedEntry.tools?.length" class="assistant-tools">
            <span v-for="tool in selectedEntry.tools" :key="tool">{{ tool }}</span>
          </div>
          <button class="primary-soft-button" :disabled="isTyping" @click="runSelectedEntry">
            {{ isTyping ? '执行中...' : '按参数执行' }}
          </button>
        </div>
      </aside>

      <section class="assistant-chat panel">
        <div class="assistant-chat__header">
          <div>
            <h3>对话执行</h3>
            <p>选中真实 Skill / Workflow 后，参数会合成 prompt 并随 metadata 一起提交给同一个 AI 助手。</p>
          </div>
        </div>

        <div :ref="bindMessagesEl" class="assistant-chat__messages">
          <article
            v-for="message in messages"
            :key="message.id"
            class="assistant-message"
            :class="`assistant-message--${message.role}`"
          >
            <div class="assistant-message__body">
              <ChatRichBlocks
                v-if="message.role === 'assistant'"
                :content="message.content"
                :cards="message.cards"
                :tool-results="message.toolResults"
                :rich-blocks="message.richBlocks"
              />
              <p v-else>{{ message.content }}</p>
              <div class="assistant-message__meta">
                <span v-if="message.status">{{ message.status }}</span>
                <span v-if="message.intent">意图 {{ message.intent }}</span>
                <span v-if="appliedSkillName(message)">Skill {{ appliedSkillName(message) }}</span>
                <span v-if="message.workflowName">Workflow {{ message.workflowName }}</span>
              </div>
            </div>

            <div
              v-if="skillHighlights(message).length || skillNextActions(message).length"
              class="assistant-message__skill-detail"
            >
              <p v-if="skillHighlights(message).length">{{ skillHighlights(message).join('；') }}</p>
              <div v-if="skillNextActions(message).length" class="assistant-card__actions">
                <span v-for="action in skillNextActions(message)" :key="action">{{ action }}</span>
              </div>
            </div>

            <div v-if="message.toolResults?.length" class="assistant-message__tools">
              <article
                v-for="(result, index) in message.toolResults"
                :key="`${message.id}-tool-${index}`"
                class="assistant-tool-result"
                :class="{ 'assistant-tool-result--failed': !toolOk(result) }"
              >
                <strong>{{ toolName(result) }}</strong>
                <span>{{ toolOk(result) ? '完成' : '失败' }}</span>
                <p>{{ toolSummary(result) }}</p>
              </article>
            </div>

            <div v-if="message.cards?.length" class="assistant-message__cards">
              <article v-for="(card, index) in message.cards" :key="`${message.id}-card-${index}`" class="assistant-card">
                <strong>{{ cardTitle(card) }}</strong>
                <div v-if="cardActions(card).length" class="assistant-card__actions">
                  <button
                    v-for="action in cardActions(card)"
                    :key="String(action.id || action.action_id || action.label)"
                    :disabled="actionRunning(actionKey(message, card, action))"
                    @click="handleCardAction(message, card, action)"
                  >
                    {{ actionRunning(actionKey(message, card, action)) ? '执行中' : cardActionLabel(action) }}
                  </button>
                </div>
              </article>
            </div>

            <div v-if="resultReports(message).length" class="assistant-message__reports">
              <article
                v-for="report in resultReports(message)"
                :key="`${report.title}-${report.reportId || report.text}`"
                class="assistant-report"
              >
                <div class="assistant-report__header">
                  <strong>{{ report.title }}</strong>
                  <span v-if="report.reportId">#{{ report.reportId }}</span>
                </div>
                <p v-if="report.text">{{ report.text }}</p>
                <div v-if="report.links.length" class="assistant-report__links">
                  <a v-for="link in report.links" :key="link.url" :href="link.url" target="_blank" rel="noreferrer">
                    {{ link.label }}
                  </a>
                </div>
              </article>
            </div>

            <div v-if="resultImages(message).length" class="assistant-message__images">
              <figure v-for="image in resultImages(message)" :key="image.url" class="assistant-result-image">
                <img :src="image.url" :alt="image.title" />
                <figcaption>{{ image.caption || image.title }}</figcaption>
              </figure>
            </div>
          </article>
        </div>

        <div class="assistant-chat__input">
          <textarea
            v-model="inputText"
            rows="3"
            placeholder="输入消息，Enter 发送，Shift+Enter 换行"
            @keydown="handleKeydown"
          />
          <button class="primary-soft-button" :disabled="!inputText.trim() || isTyping" @click="() => sendMessage()">
            {{ isTyping ? '发送中...' : '发送' }}
          </button>
        </div>
      </section>
    </section>
  </main>
</template>

<style scoped>
.assistant-page {
  display: grid;
  gap: 16px;
}

.assistant-page__hero {
  align-items: center;
  display: flex;
  justify-content: space-between;
}

.assistant-page__hero h2,
.assistant-page__hero p,
.assistant-skills h3,
.assistant-skills p,
.assistant-chat h3,
.assistant-chat p {
  margin: 0;
}

.assistant-page__hero h2 {
  font-size: 28px;
}

.assistant-page__status {
  align-items: center;
  background: #f6f8fb;
  border: 1px solid #e3e8f0;
  border-radius: 999px;
  display: flex;
  gap: 8px;
  padding: 8px 12px;
}

.assistant-page__dot {
  background: #f59e0b;
  border-radius: 999px;
  height: 10px;
  width: 10px;
}

.assistant-page__dot--active {
  background: #22c55e;
}

.assistant-workspace {
  display: grid;
  gap: 16px;
  grid-template-columns: minmax(260px, 340px) minmax(0, 1fr);
  min-height: calc(100vh - 270px);
}

.assistant-skills,
.assistant-chat {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.assistant-skills {
  gap: 14px;
  max-height: calc(100vh - 270px);
  overflow-y: auto;
}

.assistant-entry-section {
  display: grid;
  gap: 8px;
}

.assistant-entry-section h4,
.assistant-params h4 {
  color: #344054;
  font-size: 13px;
  margin: 0;
}

.assistant-catalog-note {
  color: #667085;
}

.assistant-catalog-error {
  color: #dc2626;
}

.assistant-skill-grid {
  display: grid;
  gap: 10px;
}

.assistant-skill {
  background: #f8fafc;
  border: 1px solid #dfe5ee;
  border-radius: 8px;
  cursor: pointer;
  display: grid;
  gap: 5px;
  padding: 12px;
  text-align: left;
}

.assistant-skill:hover {
  border-color: #94c5ff;
  box-shadow: 0 8px 20px rgba(14, 40, 65, 0.08);
}

.assistant-skill--active {
  background: #eef6ff;
  border-color: #60a5fa;
}

.assistant-skill:disabled {
  cursor: wait;
  opacity: 0.6;
}

.assistant-skill strong {
  color: #182230;
}

.assistant-skill small {
  color: #667085;
  line-height: 1.45;
}

.assistant-skill em,
.assistant-skill__kind,
.assistant-page__hero p,
.assistant-skills p,
.assistant-chat__header p {
  color: #687383;
  line-height: 1.5;
}

.assistant-skill em,
.assistant-skill__kind {
  font-size: 11px;
  font-style: normal;
}

.assistant-params {
  border-top: 1px solid #e4e7ec;
  display: grid;
  gap: 10px;
  padding-top: 12px;
}

.assistant-param {
  display: grid;
  gap: 5px;
}

.assistant-param span {
  color: #344054;
  font-size: 12px;
  font-weight: 700;
}

.assistant-param input,
.assistant-param textarea {
  border: 1px solid #d9dee7;
  border-radius: 8px;
  color: #182230;
  padding: 8px 10px;
}

.assistant-param textarea {
  resize: vertical;
}

.assistant-tools {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.assistant-tools span {
  background: #f7fbff;
  border: 1px solid #b7d8ff;
  border-radius: 999px;
  color: #2563eb;
  font-size: 11px;
  padding: 2px 7px;
}

.assistant-chat {
  gap: 12px;
}

.assistant-chat__header {
  align-items: center;
  display: flex;
  justify-content: space-between;
}

.assistant-chat__messages {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 12px;
  min-height: 360px;
  overflow-y: auto;
  padding-right: 4px;
}

.assistant-message {
  border-radius: 10px;
  display: grid;
  font-size: 14px;
  gap: 8px;
  line-height: 1.6;
  max-width: min(860px, 92%);
  padding: 12px 14px;
}

.assistant-message--assistant {
  background: #f5f8fc;
  border: 1px solid #e2e8f0;
}

.assistant-message--user {
  align-self: flex-end;
  background: #0e2841;
  color: #fff;
}

.assistant-message__body {
  display: grid;
  gap: 6px;
}

.assistant-message__body p {
  margin: 0;
  white-space: pre-wrap;
}

.assistant-message__meta,
.assistant-card__actions,
.assistant-report__links {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.assistant-message__meta span {
  border: 1px solid #d7e0ec;
  border-radius: 999px;
  color: #64748b;
  font-size: 12px;
  padding: 2px 8px;
}

.assistant-message__skill-detail,
.assistant-tool-result,
.assistant-card,
.assistant-report {
  background: #fff;
  border: 1px solid #e1e7ef;
  border-radius: 8px;
  display: grid;
  gap: 5px;
  padding: 10px;
}

.assistant-message__tools,
.assistant-message__cards,
.assistant-message__reports,
.assistant-message__images {
  display: grid;
  gap: 8px;
}

.assistant-tool-result strong,
.assistant-card strong,
.assistant-report strong {
  color: #182230;
}

.assistant-tool-result span {
  color: #059669;
  font-size: 12px;
}

.assistant-tool-result--failed span {
  color: #dc2626;
}

.assistant-tool-result p,
.assistant-card p,
.assistant-report p,
.assistant-message__skill-detail p {
  color: #667085;
  margin: 0;
  white-space: pre-wrap;
}

.assistant-card__actions span,
.assistant-card__actions button,
.assistant-report__links a {
  background: #f7fbff;
  border: 1px solid #b7d8ff;
  border-radius: 999px;
  color: #2563eb;
  font-size: 12px;
  padding: 4px 9px;
  text-decoration: none;
}

.assistant-card__actions button:disabled {
  cursor: wait;
  opacity: 0.55;
}

.assistant-report__header {
  align-items: center;
  display: flex;
  justify-content: space-between;
}

.assistant-report__header span {
  color: #94a3b8;
  font-size: 12px;
}

.assistant-result-image {
  border: 1px solid #e1e7ef;
  border-radius: 8px;
  margin: 0;
  overflow: hidden;
}

.assistant-result-image img {
  aspect-ratio: 16 / 9;
  background: #111827;
  display: block;
  object-fit: cover;
  width: 100%;
}

.assistant-result-image figcaption {
  color: #667085;
  font-size: 12px;
  padding: 8px 10px;
}

.assistant-chat__input {
  align-items: flex-end;
  display: flex;
  gap: 10px;
}

.assistant-chat__input textarea {
  border: 1px solid #d9dee7;
  border-radius: 8px;
  flex: 1;
  min-height: 74px;
  padding: 10px;
  resize: vertical;
}

@media (max-width: 980px) {
  .assistant-workspace {
    grid-template-columns: 1fr;
  }

  .assistant-page__hero,
  .assistant-chat__input {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
