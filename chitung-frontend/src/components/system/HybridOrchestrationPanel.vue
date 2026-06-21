<script setup lang="ts">
import { reactive, ref } from 'vue'
import type { HybridPlan } from '../../types/domain'

const emit = defineEmits<{
  saveLlm: [payload: { baseUrl: string; apiKey: string; model: string }]
  createPlan: [payload: { sessionId: string; userInput: string; preferCodex: boolean; dryRun: boolean; metadata: Record<string, unknown> }]
  confirmPlan: [payload: { sessionId: string; planId: string; actionIds: string[]; notes?: string }]
  executePlan: [payload: { sessionId: string; planId: string; idempotencyKey: string; dryRun: boolean }]
}>()

const providers = [
  {
    id: 'codex',
    label: 'Codex / OpenAI Compatible',
    baseUrl: 'https://api.openai.com/v1/chat/completions',
    model: 'gpt-5-codex',
  },
  {
    id: 'deepseek',
    label: 'DeepSeek',
    baseUrl: 'https://api.deepseek.com/v1/chat/completions',
    model: 'deepseek-chat',
  },
  {
    id: 'qwen',
    label: 'Qwen (DashScope Compatible)',
    baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
    model: 'qwen-plus',
  },
  {
    id: 'zhipu',
    label: 'Zhipu GLM',
    baseUrl: 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
    model: 'glm-4-plus',
  },
  {
    id: 'moonshot',
    label: 'Moonshot / Kimi',
    baseUrl: 'https://api.moonshot.cn/v1/chat/completions',
    model: 'moonshot-v1-8k',
  },
]

const modelForm = reactive({
  provider: 'codex',
  baseUrl: providers[0].baseUrl,
  apiKey: '',
  model: providers[0].model,
})

const orchestrationForm = reactive({
  sessionId: `session_${Math.random().toString(16).slice(2, 10)}`,
  userInput: '请生成今天的外部风险简报并给出建议动作',
  preferCodex: true,
  dryRun: true,
})

const latestPlan = ref<HybridPlan | null>(null)
const running = ref(false)
const logs = ref<string[]>([])

function useProvider(id: string) {
  const provider = providers.find((item) => item.id === id)
  if (!provider) return
  modelForm.provider = provider.id
  modelForm.baseUrl = provider.baseUrl
  modelForm.model = provider.model
}

function saveModelConfig() {
  emit('saveLlm', {
    baseUrl: modelForm.baseUrl.trim(),
    apiKey: modelForm.apiKey.trim(),
    model: modelForm.model.trim(),
  })
}

function pushLog(text: string) {
  logs.value = [text, ...logs.value].slice(0, 10)
}

async function runHybridE2E() {
  running.value = true
  try {
    emit('createPlan', {
      sessionId: orchestrationForm.sessionId,
      userInput: orchestrationForm.userInput,
      preferCodex: orchestrationForm.preferCodex,
      dryRun: orchestrationForm.dryRun,
      metadata: { source: 'frontend_hybrid_panel' },
    })
  } finally {
    running.value = false
  }
}

function confirmCurrentPlan() {
  if (!latestPlan.value) return
  const actionIds = latestPlan.value.actions.map((item) => item.action_id)
  emit('confirmPlan', {
    sessionId: orchestrationForm.sessionId,
    planId: latestPlan.value.plan_id,
    actionIds,
    notes: 'frontend manual confirm',
  })
}

function executeCurrentPlan() {
  if (!latestPlan.value) return
  emit('executePlan', {
    sessionId: orchestrationForm.sessionId,
    planId: latestPlan.value.plan_id,
    idempotencyKey: `ui_${orchestrationForm.sessionId}_${Date.now()}`,
    dryRun: orchestrationForm.dryRun,
  })
}

function syncPlan(plan: HybridPlan) {
  latestPlan.value = plan
}

defineExpose({ syncPlan, pushLog })
</script>

<template>
  <section class="panel hybrid-orchestration-panel">
    <div class="panel__header">
      <div>
        <h2>Codex + Chitong 混合编排</h2>
        <p>模型连接页 + /plan /confirm /execute 测试入口（支持国产模型）</p>
      </div>
    </div>

    <div class="hybrid-grid">
      <div class="hybrid-card">
        <h3>模型连接</h3>
        <label>
          <span>预设提供方</span>
          <select v-model="modelForm.provider" @change="useProvider(modelForm.provider)">
            <option v-for="item in providers" :key="item.id" :value="item.id">{{ item.label }}</option>
          </select>
        </label>
        <label>
          <span>Base URL</span>
          <input v-model="modelForm.baseUrl" placeholder="https://.../chat/completions" />
        </label>
        <label>
          <span>API Key</span>
          <input v-model="modelForm.apiKey" type="password" placeholder="sk-..." />
        </label>
        <label>
          <span>Model</span>
          <input v-model="modelForm.model" placeholder="gpt-5-codex / deepseek-chat / qwen-plus" />
        </label>
        <button class="primary-soft-button" type="button" @click="saveModelConfig">保存模型连接</button>
      </div>

      <div class="hybrid-card">
        <h3>混合编排 E2E</h3>
        <label>
          <span>session_id</span>
          <input v-model="orchestrationForm.sessionId" />
        </label>
        <label>
          <span>用户输入</span>
          <textarea v-model="orchestrationForm.userInput" rows="3" />
        </label>
        <label class="inline-check">
          <input v-model="orchestrationForm.preferCodex" type="checkbox" />
          <span>优先使用 Codex 规划（失败自动降级规则流）</span>
        </label>
        <label class="inline-check">
          <input v-model="orchestrationForm.dryRun" type="checkbox" />
          <span>Dry Run（只演练状态流，不真实调用工具）</span>
        </label>
        <button class="primary-soft-button" type="button" :disabled="running" @click="runHybridE2E">
          {{ running ? '执行中...' : '创建计划（/plan）' }}
        </button>
        <div class="hybrid-actions">
          <button class="mini-button" type="button" :disabled="!latestPlan || latestPlan.status !== 'PENDING_CONFIRMATION'" @click="confirmCurrentPlan">
            确认计划（/confirm）
          </button>
          <button class="mini-button" type="button" :disabled="!latestPlan || latestPlan.status !== 'CONFIRMED'" @click="executeCurrentPlan">
            执行计划（/execute）
          </button>
        </div>
      </div>
    </div>

    <div class="hybrid-grid">
      <div class="hybrid-card">
        <h3>最近计划</h3>
        <p v-if="!latestPlan" class="muted">尚未创建计划。</p>
        <div v-else class="plan-summary">
          <p><strong>plan_id:</strong> {{ latestPlan.plan_id }}</p>
          <p><strong>workflow:</strong> {{ latestPlan.workflow }}</p>
          <p><strong>planner_mode:</strong> {{ latestPlan.planner_mode }}</p>
          <p><strong>status:</strong> {{ latestPlan.status }}</p>
          <p><strong>actions:</strong> {{ latestPlan.actions.length }}</p>
        </div>
      </div>
      <div class="hybrid-card">
        <h3>日志</h3>
        <p v-if="!logs.length" class="muted">暂无日志。</p>
        <ul v-else class="log-list">
          <li v-for="line in logs" :key="line">{{ line }}</li>
        </ul>
      </div>
    </div>
  </section>
</template>

<style scoped>
.hybrid-orchestration-panel {
  margin-bottom: 16px;
}

.hybrid-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 10px;
}

@media (max-width: 960px) {
  .hybrid-grid {
    grid-template-columns: 1fr;
  }
}

.hybrid-card {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  padding: 14px;
  background: var(--bg-subtle);
}

.hybrid-card h3 {
  margin: 0 0 10px;
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}

label {
  display: block;
  margin-bottom: 10px;
}

label span {
  display: block;
  margin-bottom: 5px;
  color: var(--text-secondary);
  font-size: 12px;
}

input,
select,
textarea {
  width: 100%;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-normal);
  background: var(--bg-white);
  color: var(--text-primary);
  padding: 8px 11px;
}

input:focus,
select:focus,
textarea:focus {
  border-color: var(--brand-cyan);
  box-shadow: var(--ring);
  outline: none;
}

.inline-check {
  display: flex;
  align-items: center;
  gap: 8px;
}

.inline-check span {
  margin: 0;
  color: var(--text-primary);
}

.inline-check input {
  width: auto;
}

.muted {
  color: var(--text-muted);
}

.plan-summary p {
  margin: 4px 0;
  font-size: 13px;
  color: var(--text-primary);
}

.log-list {
  margin: 0;
  padding-left: 18px;
  color: var(--text-secondary);
  font-size: 12px;
}

.hybrid-actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
}
</style>
