<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useDraggable } from '@/composables/useDraggable'
import type { UserPreferences } from '@/types'

const emit = defineEmits<{
  close: []
  saved: []
  toast: [message: string, type?: 'success' | 'info' | 'error']
}>()

const profile = ref<UserPreferences | null>(null)
const saving = ref(false)
const modalRef = ref<HTMLElement | null>(null)
const dragHandleRef = ref<HTMLElement | null>(null)
const newPreferred = ref('')
const newAvoided = ref('')
const newTerm = ref('')

useDraggable(modalRef, dragHandleRef)

function normalizeProfile(p: UserPreferences): UserPreferences {
  const learning = {
    enabled: p.learning?.enabled ?? p.auto_learn ?? true,
    apply_mode: p.learning?.apply_mode ?? 'suggest',
    learn_from: {
      accepted: p.learning?.learn_from?.accepted ?? true,
      rejected: p.learning?.learn_from?.rejected ?? true,
      manual_terms: p.learning?.learn_from?.manual_terms ?? true,
      commands: p.learning?.learn_from?.commands ?? true,
    },
    digest_threshold: p.learning?.digest_threshold ?? p.digest?.next_digest_at ?? 10,
    retention_limit: p.learning?.retention_limit ?? 200,
    privacy: {
      store_examples: p.learning?.privacy?.store_examples ?? true,
      store_rejected_text: p.learning?.privacy?.store_rejected_text ?? false,
    },
  }
  return {
    ...p,
    auto_learn: learning.enabled,
    learning,
    style: {
      ...p.style,
      conciseness: p.style.conciseness ?? 'concise',
      tone: p.style.tone ?? '公文风格',
      document_style: p.style.document_style ?? 'general',
      risk_sensitivity: p.style.risk_sensitivity ?? 'strict',
    },
  }
}

onMounted(async () => {
  if (window.electronAPI) {
    profile.value = normalizeProfile(await window.electronAPI.getPreferences())
  }
})

async function saveProfile() {
  if (!window.electronAPI || !profile.value) return
  saving.value = true
  try {
    profile.value.auto_learn = profile.value.learning?.enabled ?? true
    profile.value = normalizeProfile(await window.electronAPI.updatePreferences(profile.value))
    emit('saved')
    emit('toast', '偏好已保存', 'success')
  } finally {
    saving.value = false
  }
}

async function resetProfile() {
  if (!window.electronAPI) return
  if (!confirm('确定重置偏好并清空学习记录？')) return
  profile.value = normalizeProfile(await window.electronAPI.resetPreferences())
  emit('toast', '已重置偏好', 'info')
}

function addTag(field: 'preferred_phrases' | 'avoided_phrases', value: string) {
  if (!profile.value || !value.trim()) return
  const list = profile.value.style[field]
  if (!list.includes(value.trim())) list.push(value.trim())
}

function removeTag(field: 'preferred_phrases' | 'avoided_phrases', idx: number) {
  profile.value?.style[field].splice(idx, 1)
}

function addTerm() {
  if (!profile.value || !newTerm.value.trim()) return
  if (!profile.value.domain.terms.includes(newTerm.value.trim())) {
    profile.value.domain.terms.push(newTerm.value.trim())
  }
  newTerm.value = ''
}
</script>

<template>
  <Transition name="modal">
    <div v-if="profile" class="modal-overlay" @click.self="emit('close')">
      <div ref="modalRef" class="modal">
        <div ref="dragHandleRef" class="modal-header drag-handle">
          <div>
            <h2>写作偏好</h2>
            <p class="subtitle">控制闪闪如何学习和使用你的写作习惯</p>
          </div>
          <button class="icon-btn" type="button" @click="emit('close')">✕</button>
        </div>

        <div class="modal-body">
          <section class="section">
            <div class="section-title">自动学习习惯</div>
            <label class="switch-row">
              <input v-model="profile.learning!.enabled" type="checkbox" />
              <span>
                <strong>启用自动学习</strong>
                <small>根据采纳/拒绝记录总结你的常用措辞、禁用词和修改偏好</small>
              </span>
            </label>

            <div class="grid-2">
              <label class="field">
                <span>应用方式</span>
                <select v-model="profile.learning!.apply_mode">
                  <option value="suggest">只作为建议约束</option>
                  <option value="auto">自动用于每次生成</option>
                </select>
              </label>
              <label class="field">
                <span>学习频率</span>
                <select v-model.number="profile.learning!.digest_threshold">
                  <option :value="5">每 5 次操作总结</option>
                  <option :value="10">每 10 次操作总结</option>
                  <option :value="20">每 20 次操作总结</option>
                </select>
              </label>
            </div>

            <div class="field-label">学习来源</div>
            <div class="check-grid">
              <label><input v-model="profile.learning!.learn_from.accepted" type="checkbox" /> 采纳的修改</label>
              <label><input v-model="profile.learning!.learn_from.rejected" type="checkbox" /> 拒绝的修改</label>
              <label><input v-model="profile.learning!.learn_from.commands" type="checkbox" /> 常用指令</label>
              <label><input v-model="profile.learning!.learn_from.manual_terms" type="checkbox" /> 手动添加术语</label>
            </div>

            <div class="field-label">隐私与记录</div>
            <div class="check-grid">
              <label><input v-model="profile.learning!.privacy.store_examples" type="checkbox" /> 保存文本片段用于学习</label>
              <label><input v-model="profile.learning!.privacy.store_rejected_text" type="checkbox" /> 保存被拒绝原文</label>
            </div>
            <label class="field compact">
              <span>最多保留操作记录</span>
              <select v-model.number="profile.learning!.retention_limit">
                <option :value="50">50 条</option>
                <option :value="100">100 条</option>
                <option :value="200">200 条</option>
                <option :value="500">500 条</option>
              </select>
            </label>
          </section>

          <section class="section">
            <div class="section-title">文稿场景</div>
            <div class="grid-2">
              <label class="field">
                <span>常用部门场景</span>
                <select v-model="profile.style.document_style">
                  <option value="general">综合公文</option>
                  <option value="hr">人力部门</option>
                  <option value="party">党建部门</option>
                </select>
              </label>
              <label class="field">
                <span>风险敏感度</span>
                <select v-model="profile.style.risk_sensitivity">
                  <option value="standard">标准</option>
                  <option value="strict">严格</option>
                  <option value="highest">最高</option>
                </select>
              </label>
            </div>

            <label class="field-label">风格</label>
            <div class="radio-row">
              <label><input v-model="profile.style.formality" type="radio" value="formal" /> 正式公文</label>
              <label><input v-model="profile.style.formality" type="radio" value="balanced" /> 适度正式</label>
              <label><input v-model="profile.style.formality" type="radio" value="casual" /> 简洁口语</label>
            </div>
          </section>

          <section class="section">
            <div class="section-title">词语与术语</div>
            <label class="field-label">倾向用词</label>
            <div class="tag-row">
              <span v-for="(t, i) in profile.style.preferred_phrases" :key="`p-${t}`" class="tag">
                {{ t }} <button type="button" @click="removeTag('preferred_phrases', i)">×</button>
              </span>
              <input v-model="newPreferred" class="tag-input" placeholder="添加" @keydown.enter.prevent="addTag('preferred_phrases', newPreferred); newPreferred = ''" />
            </div>

            <label class="field-label">避免用词</label>
            <div class="tag-row">
              <span v-for="(t, i) in profile.style.avoided_phrases" :key="`a-${t}`" class="tag avoided">
                {{ t }} <button type="button" @click="removeTag('avoided_phrases', i)">×</button>
              </span>
              <input v-model="newAvoided" class="tag-input" placeholder="添加" @keydown.enter.prevent="addTag('avoided_phrases', newAvoided); newAvoided = ''" />
            </div>

            <label class="field-label">行业术语</label>
            <div class="tag-row">
              <span v-for="(t, i) in profile.domain.terms" :key="`t-${t}`" class="tag term">
                {{ t }} <button type="button" @click="profile.domain.terms.splice(i, 1)">×</button>
              </span>
              <input v-model="newTerm" class="tag-input" placeholder="添加" @keydown.enter.prevent="addTerm" />
            </div>
          </section>
        </div>

        <div class="modal-footer">
          <button class="btn secondary" type="button" @click="resetProfile">重置偏好</button>
          <button class="btn primary" type="button" :disabled="saving" @click="saveProfile">
            {{ saving ? '保存中…' : '保存' }}
          </button>
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
  width: 560px;
  max-width: 92vw;
  background: var(--bg-panel);
  border: 1px solid var(--border-light);
  border-radius: 12px;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
}

.modal-header h2 {
  margin: 0;
  font-size: 16px;
}

.subtitle {
  margin: 4px 0 0;
  color: var(--text-muted);
  font-size: 12px;
}

.modal-body {
  padding: 14px 16px;
  max-height: 560px;
  overflow: auto;
}

.section {
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.02);
  margin-bottom: 12px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-bright);
  margin-bottom: 10px;
}

.field-label {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
  margin: 10px 0 6px;
}

.radio-row, .check-row {
  display: flex;
  gap: 12px;
  font-size: 13px;
  flex-wrap: wrap;
}

.switch-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 10px;
  border-radius: 8px;
  background: var(--bg-input);
}

.switch-row small {
  display: block;
  color: var(--text-muted);
  margin-top: 3px;
  line-height: 1.4;
}

.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-top: 10px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
}

.field.compact {
  max-width: 220px;
  margin-top: 10px;
}

.field select {
  height: 32px;
  border-radius: 8px;
  border: 1px solid var(--border-light);
  background: var(--bg-input);
  color: var(--text-primary);
  padding: 0 8px;
}

.check-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  font-size: 13px;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--bg-input);
}

.tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--green-bg);
  color: var(--green);
  font-size: 12px;
}

.tag.avoided {
  background: var(--red-bg);
  color: var(--red);
}

.tag.term {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.tag button {
  font-size: 14px;
  line-height: 1;
}

.tag-input {
  min-width: 80px;
  flex: 1;
  border: none;
  background: transparent;
  font-size: 12px;
  outline: none;
}

.modal-footer {
  display: flex;
  justify-content: space-between;
  padding: 12px 16px;
  border-top: 1px solid var(--border);
}

.btn {
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 12px;
}

.btn.secondary {
  background: var(--bg-hover);
}

.btn.primary {
  background: var(--accent);
  color: #fff;
}
</style>
