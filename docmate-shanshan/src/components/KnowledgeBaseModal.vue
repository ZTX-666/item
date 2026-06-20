<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useDraggable } from '@/composables/useDraggable'
import type { KbDocumentMeta } from '@/types'

const emit = defineEmits<{
  close: []
  saved: []
  toast: [message: string, type?: 'success' | 'info' | 'error']
}>()

const docs = ref<KbDocumentMeta[]>([])
const loading = ref(false)
const importing = ref(false)
const importStatus = ref('')
const importProgress = ref<{ current: number; total: number; message: string } | null>(null)
const showPaste = ref(false)
const pasteName = ref('')
const pasteContent = ref('')
const modalRef = ref<HTMLElement | null>(null)
const dragHandleRef = ref<HTMLElement | null>(null)

useDraggable(modalRef, dragHandleRef)

async function refreshDocs() {
  if (!window.electronAPI) return
  docs.value = await window.electronAPI.listKbDocs()
}

let unsubscribeProgress: (() => void) | undefined

onMounted(() => {
  refreshDocs()
  unsubscribeProgress = window.electronAPI?.onKbImportProgress?.((progress) => {
    importProgress.value = progress
    importStatus.value = progress.message
  })
})

onBeforeUnmount(() => unsubscribeProgress?.())

async function handleImportFile() {
  if (!window.electronAPI) return
  importing.value = true
  importStatus.value = '正在分析文档结构…'
  try {
    const result = await window.electronAPI.importKbDoc()
    if (result.ok) {
      importStatus.value = `切分完成 ✓ ${result.chunk_count} 块`
      importProgress.value = null
      emit('toast', `已导入「${result.doc_name}」${result.chunk_count} 块`, 'success')
      await refreshDocs()
      emit('saved')
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err)
    emit('toast', msg || '导入失败', 'error')
  } finally {
    importing.value = false
    importProgress.value = null
    setTimeout(() => { importStatus.value = '' }, 2000)
  }
}

async function handlePasteSave() {
  if (!window.electronAPI || !pasteContent.value.trim()) return
  importing.value = true
  importStatus.value = '正在分析文档结构…'
  try {
    const result = await window.electronAPI.importKbText({
      name: pasteName.value.trim() || '粘贴文档',
      content: pasteContent.value,
    })
    if (result.ok) {
      showPaste.value = false
      pasteName.value = ''
      pasteContent.value = ''
      emit('toast', `已导入 ${result.chunk_count} 块`, 'success')
      importProgress.value = null
      await refreshDocs()
      emit('saved')
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err)
    emit('toast', msg || '导入失败', 'error')
  } finally {
    importing.value = false
    importProgress.value = null
    importStatus.value = ''
  }
}

async function handleDelete(docId: string, docName: string) {
  if (!window.electronAPI) return
  if (!confirm(`确定删除「${docName}」及其全部知识块？`)) return
  loading.value = true
  try {
    await window.electronAPI.deleteKbDoc(docId)
    await refreshDocs()
    emit('toast', '已删除', 'success')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <Transition name="modal">
    <div class="modal-overlay" @click.self="emit('close')">
      <div ref="modalRef" class="modal">
      <div ref="dragHandleRef" class="modal-header drag-handle">
        <h2>知识库</h2>
        <button class="icon-btn" type="button" @click="emit('close')">✕</button>
      </div>

      <div class="modal-body">
        <p v-if="importStatus" class="status-line">{{ importStatus }}</p>
        <div v-if="importProgress" class="progress-bar">
          <span :style="{ width: `${Math.round((importProgress.current / Math.max(1, importProgress.total)) * 100)}%` }" />
        </div>
        <p v-else class="hint">上传参考资料后，修改时只注入相关片段（非全文）。</p>

        <div v-if="docs.length === 0" class="empty">暂无文档，请添加</div>
        <div v-for="doc in docs" :key="doc.doc_id" class="doc-row">
          <span class="doc-icon">📄</span>
          <span class="doc-name">{{ doc.doc_name }}</span>
          <span class="doc-meta">{{ doc.chunk_count }} 块</span>
          <button class="link-btn" type="button" :disabled="loading" @click="handleDelete(doc.doc_id, doc.doc_name)">
            删
          </button>
        </div>

        <div v-if="showPaste" class="paste-box">
          <input v-model="pasteName" class="paste-name" placeholder="文档名称" />
          <textarea v-model="pasteContent" class="paste-text" placeholder="粘贴文本内容…" rows="6" />
          <div class="paste-actions">
            <button class="btn secondary" type="button" @click="showPaste = false">取消</button>
            <button class="btn primary" type="button" :disabled="importing || !pasteContent.trim()" @click="handlePasteSave">
              保存
            </button>
          </div>
        </div>
      </div>

      <div class="modal-footer">
        <button class="btn secondary" type="button" :disabled="importing" @click="handleImportFile">
          + 添加文档
        </button>
        <button class="btn secondary" type="button" :disabled="importing" @click="showPaste = !showPaste">
          📋 粘贴文本
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
  width: 460px;
  max-width: 92vw;
  background: var(--bg-panel);
  border: 1px solid var(--border-light);
  border-radius: 12px;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.5);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
}

.modal-header h2 {
  font-size: 15px;
  margin: 0;
}

.modal-body {
  padding: 14px 16px;
  max-height: 360px;
  overflow: auto;
}

.hint, .status-line {
  font-size: 12px;
  color: var(--text-muted);
  margin: 0 0 12px;
}

.status-line {
  color: var(--accent);
}

.progress-bar {
  height: 5px;
  overflow: hidden;
  margin: -4px 0 10px;
  border-radius: 999px;
  background: var(--bg-hover);
}

.progress-bar span {
  display: block;
  height: 100%;
  background: var(--accent);
  transition: width 0.2s ease;
}

.empty {
  font-size: 13px;
  color: var(--text-muted);
  padding: 20px 0;
  text-align: center;
}

.doc-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
}

.doc-name {
  flex: 1;
  font-size: 13px;
}

.doc-meta {
  font-size: 11px;
  color: var(--text-muted);
}

.link-btn {
  font-size: 11px;
  color: var(--red);
}

.paste-box {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.paste-name, .paste-text {
  width: 100%;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--border-light);
  background: var(--bg-input);
  color: var(--text-primary);
  font-size: 13px;
}

.paste-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.modal-footer {
  display: flex;
  gap: 8px;
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
  color: var(--text-primary);
}

.btn.primary {
  background: var(--accent);
  color: #fff;
}
</style>
