<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import TitleBar from './components/TitleBar.vue'
import SidebarPanel from './components/SidebarPanel.vue'
import EditorPanel from './components/EditorPanel.vue'
import AiPanel from './components/AiPanel.vue'
import type { RevisionResult } from '@/types'
import { useFileSystem } from '@/composables/useFileSystem'

const {
  tree,
  activeFileId,
  activeFile,
  expandedFolders,
  sidebarCollapsed,
  loading,
  toggleFolder,
  selectFile,
  updateFileContent,
  createFile,
  createFromTemplate,
  deleteFile,
  renameFile,
  exportFile,
  importExternalFile,
  loadTree,
} = useFileSystem()

const chatCollapsed = ref(false)
const editorRef = ref<InstanceType<typeof EditorPanel> | null>(null)
const aiPanelRef = ref<InstanceType<typeof AiPanel> | null>(null)

const SIDEBAR_MODE_KEY = 'docmate-layout-sidebarMode'
const AGENT_MODE_KEY = 'docmate-layout-agentMode'

function loadLayoutMode(key: string): 'sidebar' | 'float' {
  try {
    const v = localStorage.getItem(key)
    if (v === 'sidebar' || v === 'float') return v
  } catch { /* ignore */ }
  return 'sidebar'
}

const sidebarMode = ref<'sidebar' | 'float'>(loadLayoutMode(SIDEBAR_MODE_KEY))
const agentMode = ref<'sidebar' | 'float'>(loadLayoutMode(AGENT_MODE_KEY))

watch(sidebarMode, (v) => {
  try { localStorage.setItem(SIDEBAR_MODE_KEY, v) } catch { /* ignore */ }
})
watch(agentMode, (v) => {
  try { localStorage.setItem(AGENT_MODE_KEY, v) } catch { /* ignore */ }
})

const toast = ref({ show: false, message: '', type: 'info' as 'success' | 'info' | 'error' })
const appLogoUrl = new URL('./闪闪文档.png', window.location.href).href
const shanshanBusy = ref(false)

const fileContent = computed(() => activeFile.value?.content ?? '')
const fileName = computed(() => activeFile.value?.name ?? '未命名文稿')
const isReviewing = ref(false)

function showToast(message: string, type: 'success' | 'info' | 'error' = 'info') {
  toast.value = { show: true, message, type }
  setTimeout(() => { toast.value.show = false }, 2200)
}

function handleContentUpdate(html: string) {
  updateFileContent(html)
}

function handleFileSelect(id: string, path?: string) {
  selectFile(id, path)
  aiPanelRef.value?.clearConversation?.()
}

function getDocumentText() {
  return editorRef.value?.getFullText() ?? ''
}

function getLockedText() {
  return editorRef.value?.getLockedText() ?? ''
}

function handleApplyRevision(result: RevisionResult, command: string) {
  return editorRef.value?.applyRevisionResult(result, command) ?? false
}

function handleShowReview(result: RevisionResult, command: string) {
  return editorRef.value?.showReviewFromResult(result, command) ?? false
}

function handleLocate(text: string) {
  const ok = editorRef.value?.locateText(text)
  if (!ok) showToast('未在文档中找到对应文字', 'info')
}

function handleGetHistory() {
  return editorRef.value?.getRevisionHistory() ?? []
}

function handleAcceptReview() {
  return editorRef.value?.acceptReview() ?? false
}

function handleRejectReview() {
  editorRef.value?.rejectReview()
}

function onReviewChange(v: boolean) {
  isReviewing.value = v
}

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

async function handleImportFile() {
  try {
    const result = await importExternalFile()
    if (result?.ok) {
      showToast('文件导入成功', 'success')
      await loadTree()
      if (result.path) {
        const node = findNodeByPath(tree.value, result.path)
        if (node) await selectFile(node.id, result.path)
      }
    }
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : String(error)
    showToast(`导入失败: ${msg}`, 'error')
  }
}

async function handleNewScratch() {
  await createFile('文稿', '未命名文稿.md')
  sidebarCollapsed.value = true
}

async function handleCreateFromTemplate(path: string) {
  try {
    await createFromTemplate(path)
    showToast('已从模板创建文稿', 'success')
  } catch (err) {
    showToast(err instanceof Error ? err.message : String(err), 'error')
  }
}

async function handleDeleteFile(path: string) {
  try {
    await deleteFile(path)
    showToast('文件已删除', 'success')
  } catch (err) {
    showToast(err instanceof Error ? err.message : String(err), 'error')
  }
}

async function handleRenameFile(path: string, name: string) {
  try {
    await renameFile(path, name)
    showToast('文件已重命名', 'success')
  } catch (err) {
    showToast(err instanceof Error ? err.message : String(err), 'error')
  }
}

async function handleExportFile(format: 'docx' | 'pdf') {
  try {
    const result = await exportFile(format)
    if (result.ok) showToast(`已导出 ${format.toUpperCase()}`, 'success')
  } catch (err) {
    showToast(err instanceof Error ? err.message : String(err), 'error')
  }
}

function findNodeByPath(nodes: { path?: string; id: string; children?: unknown[] }[], path: string): { id: string } | null {
  for (const node of nodes) {
    if (node.path === path) return node
    if (node.children) {
      const found = findNodeByPath(node.children as typeof nodes, path)
      if (found) return found
    }
  }
  return null
}

function toggleChat() {
  chatCollapsed.value = !chatCollapsed.value
  if (!chatCollapsed.value) nextTick(() => aiPanelRef.value?.focusInput())
}

function toggleSidebarMode() {
  sidebarMode.value = sidebarMode.value === 'sidebar' ? 'float' : 'sidebar'
}

function toggleAgentMode() {
  agentMode.value = agentMode.value === 'sidebar' ? 'float' : 'sidebar'
}

function handleAgentCommand(command: string) {
  chatCollapsed.value = false
  nextTick(() => {
    aiPanelRef.value?.submitExternalCommand?.(command)
  })
}

function onKeydown(e: KeyboardEvent) {
  if (e.ctrlKey && (e.key === 'k' || e.key === 'm')) {
    e.preventDefault()
    chatCollapsed.value = !chatCollapsed.value
    if (!chatCollapsed.value) nextTick(() => aiPanelRef.value?.focusInput())
  }
  if (e.ctrlKey && e.key === 'b') {
    e.preventDefault()
    sidebarCollapsed.value = !sidebarCollapsed.value
  }
}

onMounted(() => {
  document.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div class="app-shell">
    <TitleBar
      :sidebar-open="!sidebarCollapsed"
      :chat-open="!chatCollapsed"
      @toggle-sidebar="toggleSidebar"
      @toggle-chat="toggleChat"
    />

    <div class="app-body">
      <SidebarPanel
        v-if="!loading"
        :tree="tree"
        :active-file-id="activeFileId"
        :expanded-folders="expandedFolders"
        :collapsed="sidebarCollapsed"
        :panel-mode="sidebarMode"
        @select="handleFileSelect"
        @toggle-folder="toggleFolder"
        @create-file="createFile"
        @create-from-template="handleCreateFromTemplate"
        @rename-file="handleRenameFile"
        @delete-file="handleDeleteFile"
        @import-file="handleImportFile"
        @export-file="handleExportFile"
        @toggle-collapse="toggleSidebar"
        @toggle-mode="toggleSidebarMode"
      />

      <EditorPanel
        v-if="activeFile"
        ref="editorRef"
        :key="activeFileId"
        :content="fileContent"
        :file-name="fileName"
        :agent-busy="shanshanBusy"
        @update="handleContentUpdate"
        @review-change="onReviewChange"
        @history-change="() => aiPanelRef?.refreshHistory?.()"
        @regenerate-start="() => aiPanelRef?.onRegenerateStart?.()"
        @regenerate-end="(p) => aiPanelRef?.onRegenerateEnd?.(p)"
        @thinking-log-change="(log) => aiPanelRef?.onRegenerateThinking?.(log)"
        @ai-state-change="(s) => aiPanelRef?.onEditorAiState?.(s)"
        @agent-command="handleAgentCommand"
        @toast="showToast"
      />
      <div v-else-if="!loading" class="editor-area empty-editor">
        <img :src="appLogoUrl" alt="DocMate" class="empty-logo" />
        <p>欢迎使用 DocMate 闪闪文档</p>
        <p class="empty-hint">闪闪可直接改稿（无需选中）· 选中文字后也可用上方操作条</p>
        <button class="empty-btn" @click="handleNewScratch">开始写作</button>
      </div>
      <div v-else class="editor-area empty-editor">
        <p>加载中...</p>
      </div>

      <AiPanel
        ref="aiPanelRef"
        :collapsed="chatCollapsed"
        :panel-mode="agentMode"
        :get-document-text="getDocumentText"
        :get-locked-text="getLockedText"
        :on-show-review="handleShowReview"
        :on-apply-revision="handleApplyRevision"
        :on-locate="handleLocate"
        :on-get-history="handleGetHistory"
        :on-capture-selection="() => editorRef?.captureSelectionAnchor?.()"
        :is-reviewing="isReviewing"
        :on-accept-review="handleAcceptReview"
        :on-reject-review="handleRejectReview"
        @toggle-collapse="toggleChat"
        @toggle-mode="toggleAgentMode"
        @status-change="(thinking) => { shanshanBusy = thinking }"
        @toast="showToast"
      />
    </div>

    <div class="toast" :class="[toast.type, { show: toast.show }]">
      {{ toast.message }}
    </div>
  </div>
</template>

<style scoped>
.empty-logo {
  width: 80px;
  height: 80px;
  border-radius: 16px;
  margin-bottom: 8px;
}

.empty-hint {
  font-size: 12px;
  color: var(--text-muted);
}

.empty-btn {
  margin-top: 12px;
  padding: 8px 20px;
  background: var(--accent);
  color: white;
  border-radius: 8px;
  font-size: 13px;
}

.empty-btn:hover {
  background: var(--accent-hover);
}
</style>
