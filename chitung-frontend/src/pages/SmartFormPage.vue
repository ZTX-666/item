<script setup lang="ts">
import { computed, ref } from 'vue'
import DocumentDiffPanel from '../components/documents/DocumentDiffPanel.vue'
import FormTemplateBrowserPanel from '../components/forms/FormTemplateBrowserPanel.vue'
import SkeletonLoader from '../components/common/SkeletonLoader.vue'
import { acceptSmartFormDraft, draftSmartForm, searchFormTemplates } from '../services/chitungApi'
import type { DocumentRevisionPreview, SmartFormDraft, SmartFormTemplate } from '../types/domain'

/**
 * SmartFormPage — 智能填表页
 * P0-2: 删除硬编码假数据，新增用户输入区
 * P1-4: 空状态 + CTA
 * P1-6: 骨架屏
 * P2-5: 模板选择卡片
 */

const templates = ref<SmartFormTemplate[]>([])
const isSearching = ref(false)
const smartFormDraft = ref<SmartFormDraft | null>(null)
const isGenerating = ref(false)

// 用户输入 (P0-2)
const userInput = ref({
  query: '',
  sourceText: '',
  instruction: '',
})

const selectedTemplateId = ref<string | undefined>(undefined)

// 空的 revision 初始值 (P0-2: lines 改为空数组)
const revision = ref<DocumentRevisionPreview>({
  id: 'smart-form-initial',
  title: '智能填表草稿',
  source: 'smart-form',
  instruction: '将输入内容整理为正式安全表格字段，保留人工确认。',
  additions: 0,
  deletions: 0,
  status: 'draft',
  lines: [],
})

// canGenerate computed (P0-2)
const canGenerate = computed(() =>
  Boolean(userInput.value.query.trim() && userInput.value.sourceText.trim()),
)

async function handleSearchTemplates(query: string) {
  isSearching.value = true
  try {
    templates.value = await searchFormTemplates(query)
  } finally {
    isSearching.value = false
  }
}

async function openSmartFormRevision(templateId?: string) {
  if (!canGenerate.value) return
  selectedTemplateId.value = templateId
  isGenerating.value = true
  try {
    const draft = await draftSmartForm({
      query: userInput.value.query.trim(),
      sourceText: userInput.value.sourceText.trim(),
      templateId,
      instruction: userInput.value.instruction.trim() || '将输入内容整理为正式安全表格字段，保留人工确认。',
    })
    smartFormDraft.value = draft
    if (draft.revision_preview) {
      revision.value = draft.revision_preview
    }
  } catch (error) {
    revision.value = {
      ...revision.value,
      status: 'rejected',
      lines: [{
        id: 'error',
        type: 'context',
        text: `生成失败：${error instanceof Error ? error.message : String(error)}`,
      }],
    }
  } finally {
    isGenerating.value = false
  }
}

async function handleAccept() {
  if (!smartFormDraft.value?.accept_payload) return
  await acceptSmartFormDraft(smartFormDraft.value)
  revision.value = { ...revision.value, status: 'accepted' }
}

function handleReject() {
  revision.value = { ...revision.value, status: 'rejected' }
}

function handleRegenerate() {
  revision.value = {
    ...revision.value,
    status: 'draft',
    lines: [],
  }
}

function fillExample() {
  userInput.value.query = '临边 高处 整改 T006'
  userInput.value.sourceText = [
    '关于 B2 区临边防护隐患的整改通知',
    '现场有些护栏没弄好，需要尽快处理。',
    '后面安全员再看一下。',
  ].join('\n')
}
</script>

<template>
  <main class="workbench">
    <section class="hero-panel">
      <div>
        <p class="eyebrow">Smart Form</p>
        <h1>智能填表</h1>
        <p>搜索安全表格模板，输入事件描述，AI 自动生成填表草稿。</p>
      </div>
      <div class="hero-panel__status">
        <span class="status-dot" :class="isGenerating ? 'status-dot--orange' : 'status-dot--green'" />
        {{ isGenerating ? '生成中' : '就绪' }}
      </div>
    </section>

    <!-- 用户输入区 (P0-2) -->
    <section class="panel user-input-panel">
      <div class="panel__header">
        <div>
          <h2>事件信息</h2>
          <p>输入关键词和事件描述，AI 将自动整理为正式表格字段</p>
        </div>
        <button class="mini-button" @click="fillExample">填入示例</button>
      </div>

      <div class="user-input-grid">
        <label class="field">
          <span class="field__label">关键词 <em>*</em></span>
          <input
            v-model="userInput.query"
            class="field__input"
            type="text"
            placeholder="例如：临边 高处 整改 T006"
          />
        </label>

        <label class="field">
          <span class="field__label">修改指令（可选）</span>
          <input
            v-model="userInput.instruction"
            class="field__input"
            type="text"
            placeholder="例如：按 T006 表格格式整理，重点突出整改期限"
          />
        </label>

        <label class="field field--full">
          <span class="field__label">事件描述 <em>*</em></span>
          <textarea
            v-model="userInput.sourceText"
            class="field__textarea"
            placeholder="描述需要填表的事件内容，例如：&#10;关于 B2 区临边防护隐患的整改通知&#10;现场有些护栏没弄好，需要尽快处理。"
            rows="4"
          ></textarea>
        </label>
      </div>

      <div class="user-input-actions">
        <button
          class="primary-button"
          :disabled="!canGenerate || isGenerating"
          @click="openSmartFormRevision(selectedTemplateId)"
        >
          {{ isGenerating ? '生成中...' : '生成填表草稿' }}
        </button>
        <span v-if="!canGenerate && !isGenerating" class="input-hint">
          请填写关键词和事件描述后再生成
        </span>
      </div>
    </section>

    <FormTemplateBrowserPanel
      :templates="templates"
      :is-loading="isSearching"
      @search="handleSearchTemplates"
      @use-template="openSmartFormRevision"
    />

    <!-- 骨架屏 (P1-6) -->
    <SkeletonLoader v-if="isGenerating" type="cards" :count="3" />

    <DocumentDiffPanel
      v-else
      :revision="revision"
      :is-loading="isGenerating"
      @accept="handleAccept"
      @reject="handleReject"
      @regenerate="handleRegenerate"
    />
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

/* 用户输入区 */
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

.mini-button {
  background: var(--bg-subtle, #f5f7fa);
  border: 1px solid var(--border-light, #e8eaef);
  border-radius: var(--radius-sm, 4px);
  color: var(--text-secondary, #5b626c);
  cursor: pointer;
  font-size: 11px;
  padding: 5px 10px;
}

.mini-button:hover {
  border-color: var(--brand-cyan, #0f9ed5);
  color: var(--brand-cyan, #0f9ed5);
}

.user-input-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: 1fr 1fr;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field--full {
  grid-column: 1 / -1;
}

.field__label {
  color: var(--text-secondary, #5b626c);
  font-size: 12px;
}

.field__label em {
  color: var(--risk-high, #E53935);
  font-style: normal;
}

.field__input {
  background: var(--bg-white, #fff);
  border: 1px solid var(--border-normal, #d0d5dd);
  border-radius: var(--radius-md, 8px);
  color: var(--text-primary, #1a1d23);
  font-size: 13px;
  padding: 9px 12px;
}

.field__input:focus {
  border-color: var(--brand-cyan, #0f9ed5);
  outline: none;
}

.field__textarea {
  background: var(--bg-white, #fff);
  border: 1px solid var(--border-normal, #d0d5dd);
  border-radius: var(--radius-md, 8px);
  color: var(--text-primary, #1a1d23);
  font-family: inherit;
  font-size: 13px;
  line-height: 1.6;
  padding: 9px 12px;
  resize: vertical;
}

.field__textarea:focus {
  border-color: var(--brand-cyan, #0f9ed5);
  outline: none;
}

.user-input-actions {
  align-items: center;
  display: flex;
  gap: 12px;
}

.primary-button {
  background: var(--brand-cyan, #0f9ed5);
  border: none;
  border-radius: var(--radius-md, 8px);
  color: var(--text-white, #fff);
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  padding: 10px 24px;
}

.primary-button:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

.input-hint {
  color: var(--text-muted, #9ca3af);
  font-size: 12px;
}
</style>
