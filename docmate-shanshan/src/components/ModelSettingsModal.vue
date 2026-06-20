<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { LlmSettings } from '@/types'
import { useDraggable } from '@/composables/useDraggable'
import { serializeForIpc } from '@/utils/ipc'

const emit = defineEmits<{
  close: []
  saved: []
  toast: [message: string, type?: 'success' | 'info' | 'error']
}>()

const form = ref<LlmSettings>({
  apiUrl: 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
  apiKey: '',
  model: 'glm-5.1',
  useApi: true,
  optionCount: 1,
  speechMode: 'online-first',
  speechApiUrl: '',
  speechModel: 'whisper-1',
})

const testing = ref(false)
const saving = ref(false)
const testResult = ref<{ ok: boolean; message: string } | null>(null)
const apiKeyEdited = ref(false)
const modalRef = ref<HTMLElement | null>(null)
const dragHandleRef = ref<HTMLElement | null>(null)

useDraggable(modalRef, dragHandleRef)

onMounted(async () => {
  if (window.electronAPI) {
    const masked = await window.electronAPI.getSettings()
    form.value = { ...masked }
  }
})

async function handleSave() {
  saving.value = true
  try {
    const payload: Partial<LlmSettings> = { ...form.value }
    if (!apiKeyEdited.value) delete payload.apiKey
    await window.electronAPI!.saveSettings(serializeForIpc(payload))
    emit('saved')
    emit('toast', '设置已保存', 'success')
    emit('close')
  } finally {
    saving.value = false
  }
}

async function handleTest() {
  testing.value = true
  testResult.value = null
  try {
    if (apiKeyEdited.value && form.value.apiKey && !form.value.apiKey.includes('••••')) {
      await window.electronAPI!.saveSettings(serializeForIpc({
        apiUrl: form.value.apiUrl,
        apiKey: form.value.apiKey,
        model: form.value.model,
        useApi: form.value.useApi,
        optionCount: Math.min(3, Math.max(1, form.value.optionCount || 1)),
      }))
    }
    testResult.value = await window.electronAPI!.testConnection()
  } finally {
    testing.value = false
  }
}

function onApiKeyInput() {
  apiKeyEdited.value = true
}
</script>

<template>
  <Transition name="modal">
    <div class="modal-overlay" @click.self="emit('close')">
      <div ref="modalRef" class="modal">
      <div ref="dragHandleRef" class="modal-header drag-handle">
        <h2>大模型配置</h2>
        <button class="icon-btn" @click="emit('close')">
          <svg viewBox="0 0 16 16" fill="currentColor" width="14" height="14">
            <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="1.5" fill="none" />
          </svg>
        </button>
      </div>

      <div class="modal-body">
        <label class="field-toggle">
          <input v-model="form.useApi" type="checkbox" />
          <span>启用在线大模型（关闭则使用本地模拟）</span>
        </label>

        <div class="field">
          <label>API 地址</label>
          <input
            v-model="form.apiUrl"
            type="text"
            placeholder="https://open.bigmodel.cn/api/paas/v4/chat/completions"
            :disabled="!form.useApi"
          />
        </div>

        <div class="field">
          <label>API Key</label>
          <input
            v-model="form.apiKey"
            type="password"
            placeholder="sk-..."
            :disabled="!form.useApi"
            @input="onApiKeyInput"
          />
        </div>

        <div class="field">
          <label>模型名称</label>
          <input
            v-model="form.model"
            type="text"
            placeholder="glm-5.1"
            :disabled="!form.useApi"
          />
        </div>

        <div class="field">
          <label>修改方案数量（1–3，默认 1）</label>
          <select v-model.number="form.optionCount" :disabled="!form.useApi">
            <option :value="1">1 个方案（默认）</option>
            <option :value="2">2 个方案</option>
            <option :value="3">3 个方案</option>
          </select>
        </div>

        <p class="field-hint">对话中会展示多个修改方案，悬停预览、点击采纳。默认只生成 1 个。</p>

        <div class="section-title">语音识别</div>
        <div class="field">
          <label>识别模式</label>
          <select v-model="form.speechMode">
            <option value="online-first">在线优先，失败回退本地（推荐）</option>
            <option value="online">仅在线识别</option>
            <option value="local">仅本地识别</option>
          </select>
        </div>

        <div class="field">
          <label>在线语音接口地址</label>
          <input
            v-model="form.speechApiUrl"
            type="text"
            placeholder="留空则由聊天 API 推导 /audio/transcriptions"
            :disabled="form.speechMode === 'local'"
          />
        </div>

        <div class="field">
          <label>语音模型</label>
          <input
            v-model="form.speechModel"
            type="text"
            placeholder="whisper-1"
            :disabled="form.speechMode === 'local'"
          />
        </div>

        <p class="field-hint">
          快速联网识别建议使用 OpenAI 兼容的 audio/transcriptions 接口；不支持时会自动回退本地 Whisper tiny。
        </p>

        <div v-if="testResult" class="test-result" :class="{ ok: testResult.ok, fail: !testResult.ok }">
          {{ testResult.message }}
        </div>
      </div>

      <div class="modal-footer">
        <button class="btn secondary" :disabled="testing" @click="handleTest">
          {{ testing ? '测试中...' : '测试连接' }}
        </button>
        <div class="footer-right">
          <button class="btn secondary" @click="emit('close')">取消</button>
          <button class="btn primary" :disabled="saving" @click="handleSave">
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>
    </div>
  </Transition>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}

.modal {
  width: 480px;
  max-width: 90vw;
  background: var(--bg-panel);
  border: 1px solid var(--border-light);
  border-radius: 10px;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.5);
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
}

.modal-header h2 {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-bright);
}

.drag-handle {
  cursor: move;
  user-select: none;
}

.drag-handle .icon-btn {
  cursor: pointer;
}

.modal-body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-height: 68vh;
  overflow: auto;
}

.section-title {
  padding-top: 8px;
  border-top: 1px solid var(--border);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-bright);
}

.field label {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.field input,
.field select {
  width: 100%;
  padding: 8px 10px;
  background: var(--bg-input);
  border: 1px solid var(--border-light);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 13px;
  outline: none;
}

.field input:focus,
.field select:focus {
  border-color: var(--accent);
}

.field input:disabled,
.field select:disabled {
  opacity: 0.5;
}

.field-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-primary);
  cursor: pointer;
}

.field-toggle input {
  accent-color: var(--accent);
}

.field-hint {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
  margin: 0;
}

.test-result {
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 12px;
}

.test-result.ok {
  background: var(--green-bg);
  color: var(--green);
}

.test-result.fail {
  background: var(--red-bg);
  color: var(--red);
}

.modal-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-top: 1px solid var(--border);
}

.footer-right {
  display: flex;
  gap: 8px;
}

.btn {
  padding: 7px 14px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.15s;
}

.btn.primary {
  background: var(--accent);
  color: white;
}

.btn.primary:hover {
  background: var(--accent-hover);
}

.btn.secondary {
  background: var(--bg-hover);
  color: var(--text-primary);
  border: 1px solid var(--border-light);
}

.btn.secondary:hover {
  background: var(--bg-active);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
