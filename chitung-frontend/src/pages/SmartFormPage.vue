<script setup lang="ts">
import { ref } from 'vue'
import DocumentDiffPanel from '../components/documents/DocumentDiffPanel.vue'
import FormTemplateBrowserPanel from '../components/forms/FormTemplateBrowserPanel.vue'
import { acceptSmartFormDraft, draftSmartForm, searchFormTemplates } from '../services/chitungApi'
import type { DocumentRevisionPreview, SmartFormDraft, SmartFormTemplate } from '../types/domain'

const templates = ref<SmartFormTemplate[]>([])
const isSearching = ref(false)
const smartFormDraft = ref<SmartFormDraft | null>(null)
const revision = ref<DocumentRevisionPreview>({
  id: 'smart-form-initial',
  title: '智能填表草稿',
  source: 'smart-form',
  instruction: '将输入内容整理为正式安全表格字段，保留人工确认。',
  additions: 0,
  deletions: 0,
  status: 'draft',
  lines: [{ id: 'line-1', type: 'context', text: '请先选择模板并生成草稿。' }],
})

async function handleSearchTemplates(query: string) {
  isSearching.value = true
  try {
    templates.value = await searchFormTemplates(query)
  } finally {
    isSearching.value = false
  }
}

async function openSmartFormRevision(templateId?: string) {
  const draft = await draftSmartForm({
    query: '临边 高处 整改 T006',
    templateId,
    sourceText: [
      '关于 B2 区临边防护隐患的整改通知',
      '现场有些护栏没弄好，需要尽快处理。',
      '后面安全员再看一下。',
    ].join('\n'),
    instruction: revision.value.instruction,
  })
  smartFormDraft.value = draft
  if (draft.revision_preview) {
    revision.value = draft.revision_preview
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
  revision.value = { ...revision.value, status: 'draft' }
}
</script>

<template>
  <main class="workbench">
    <section class="hero-panel">
      <div>
        <p class="eyebrow">Smart Form</p>
        <h1>智能填表</h1>
        <p>对齐原型 04 页面：模板搜索、字段草稿、文档差异确认。</p>
      </div>
      <div class="hero-panel__status">
        <span class="status-dot status-dot--green" />
        模板 {{ templates.length }} 个 · 状态 {{ revision.status }}
      </div>
    </section>

    <FormTemplateBrowserPanel
      :templates="templates"
      :is-loading="isSearching"
      @search="handleSearchTemplates"
      @use-template="openSmartFormRevision"
    />

    <DocumentDiffPanel
      :revision="revision"
      @accept="handleAccept"
      @reject="handleReject"
      @regenerate="handleRegenerate"
    />
  </main>
</template>
