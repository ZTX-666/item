<script setup lang="ts">
import type { FileNode } from '@/types'

defineOptions({ name: 'FileTreeItem' })

defineProps<{
  node: FileNode
  depth: number
  activeFileId: string
  expandedFolders: Set<string>
}>()

const emit = defineEmits<{
  select: [id: string, path?: string]
  toggle: [id: string]
  createFile: [parentId: string]
  createFromTemplate: [path: string]
  renameFile: [path: string, name: string]
  deleteFile: [path: string]
}>()

function getFileColor(node: FileNode): string {
  if (node.type === 'folder') return 'var(--text-secondary)'
  const ext = node.extension || node.name.split('.').pop()?.toLowerCase() || ''
  const colors: Record<string, string> = {
    md: '#519aba',
    txt: '#8bc34a',
    html: '#e44d26',
    htm: '#e44d26',
    doc: '#2b579a',
    docx: '#2b579a',
    rtf: '#9c27b0',
  }
  return colors[ext] || 'var(--text-secondary)'
}

function requestRename(node: FileNode) {
  if (!node.path) return
  const name = window.prompt('请输入新文件名', node.name)
  if (name) emit('renameFile', node.path, name)
}

function requestDelete(node: FileNode) {
  if (!node.path) return
  if (window.confirm(`确定删除「${node.name}」？`)) emit('deleteFile', node.path)
}
</script>

<template>
  <div class="tree-item">
    <div
      class="tree-row"
      :class="{ active: node.type === 'file' && node.id === activeFileId }"
      :style="{ paddingLeft: `${depth * 12 + 8}px` }"
      @click="node.type === 'file' ? emit('select', node.id, node.path) : emit('toggle', node.id)"
    >
      <span
        class="tree-chevron"
        :class="{
          expanded: expandedFolders.has(node.id),
          hidden: node.type !== 'folder',
        }"
      >
        <svg viewBox="0 0 16 16" fill="currentColor" width="10" height="10">
          <path d="M6 4l4 4-4 4V4z" />
        </svg>
      </span>
      <span class="tree-icon" :style="{ color: getFileColor(node) }">
        <svg v-if="node.type === 'folder'" viewBox="0 0 16 16" fill="currentColor" width="16" height="16">
          <path d="M14.5 3H7.71l-.85-.85L6.51 2h-5l-.5.5v11l.5.5h13l.5-.5v-10L14.5 3zm-.51 10.5V4H7.5l-1-1H2v10h12z" />
        </svg>
        <svg v-else viewBox="0 0 16 16" fill="currentColor" width="16" height="16">
          <path d="M13.5 2H6.5L5 3.5V2H2.5L2 2.5v11l.5.5h11l.5-.5v-10L13.5 2zM3 13V3h1v2.5L5.5 7H13v6H3z" />
        </svg>
      </span>
      <span class="tree-name">{{ node.name }}</span>
      <span v-if="node.type === 'file'" class="tree-actions" @click.stop>
        <button
          v-if="node.path?.startsWith('模板/')"
          class="tree-action"
          title="从模板创建"
          @click="node.path && emit('createFromTemplate', node.path)"
        >用</button>
        <button
          class="tree-action"
          title="重命名"
          @click="requestRename(node)"
        >改</button>
        <button
          class="tree-action danger"
          title="删除"
          @click="requestDelete(node)"
        >删</button>
      </span>
    </div>
    <div
      v-if="node.type === 'folder' && node.children && expandedFolders.has(node.id)"
      class="tree-children"
    >
      <FileTreeItem
        v-for="child in node.children"
        :key="child.id"
        :node="child"
        :depth="depth + 1"
        :active-file-id="activeFileId"
        :expanded-folders="expandedFolders"
        @select="emit('select', $event)"
        @toggle="emit('toggle', $event)"
        @create-file="emit('createFile', $event)"
        @create-from-template="emit('createFromTemplate', $event)"
        @rename-file="(path, name) => emit('renameFile', path, name)"
        @delete-file="emit('deleteFile', $event)"
      />
    </div>
  </div>
</template>

<style scoped>
.tree-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tree-actions {
  display: none;
  gap: 3px;
  margin-left: 4px;
}

.tree-row:hover .tree-actions {
  display: inline-flex;
}

.tree-action {
  font-size: 10px;
  color: var(--text-muted);
  padding: 1px 3px;
  border-radius: 4px;
}

.tree-action:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.tree-action.danger:hover {
  color: var(--red);
}
</style>
