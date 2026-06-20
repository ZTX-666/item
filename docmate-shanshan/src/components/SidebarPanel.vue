<script setup lang="ts">
import type { FileNode } from '@/types'
import FileTreeItem from './FileTreeItem.vue'

defineProps<{
  tree: FileNode[]
  activeFileId: string
  expandedFolders: Set<string>
  collapsed: boolean
  panelMode?: 'sidebar' | 'float'
}>()

const emit = defineEmits<{
  select: [id: string, path?: string]
  toggleFolder: [id: string]
  createFile: [parentId: string]
  createFromTemplate: [path: string]
  renameFile: [path: string, name: string]
  deleteFile: [path: string]
  toggleCollapse: []
  toggleMode: []
  importFile: []
  exportFile: [format: 'docx' | 'pdf']
}>()
</script>

<template>
  <aside
    class="sidebar"
    :class="{ collapsed, 'sidebar-float': panelMode === 'float' }"
  >
    <div class="sidebar-header">
      <span>资源管理器</span>
      <div class="sidebar-actions">
        <button
          class="icon-btn"
          title="导入外部文件"
          @click="emit('importFile')"
        >
          <svg viewBox="0 0 16 16" fill="currentColor" width="14" height="14">
            <path d="M8 1v9.5L4.5 7 3 8.5 8 13.5l5-5-1.5-1.5L9 10.5V1H8zM2 14h12v1H2v-1z"/>
          </svg>
        </button>
        <button class="icon-btn" title="导出 Word" @click="emit('exportFile', 'docx')">W</button>
        <button class="icon-btn" title="导出 PDF" @click="emit('exportFile', 'pdf')">P</button>
        <button
          class="icon-btn"
          title="新建文稿"
          @click="emit('createFile', '文稿')"
        >
          <svg viewBox="0 0 16 16" fill="currentColor" width="14" height="14">
            <path d="M14.5 13.5V5.7l-4.2-4.2H2.5l-.5.5v11l.5.5h12l.5-.5zM8 2.5V7H3.5L8 2.5zM3 13V8h5V3.5l3.5 3.5V13H3z" />
          </svg>
        </button>
        <button
          class="icon-btn layout-toggle"
          :title="panelMode === 'sidebar' ? '切换为浮窗' : '切换为侧栏'"
          @click="emit('toggleMode')"
        >
          <svg v-if="panelMode === 'sidebar'" viewBox="0 0 16 16" fill="currentColor" width="14" height="14">
            <path d="M3 3h4v1H3v8h4v1H2V3h1zm10 0H9v1h4v8H9v1h5V3h-1z"/>
            <path d="M7 7.5h2v1H7z" opacity="0.4"/>
          </svg>
          <svg v-else viewBox="0 0 16 16" fill="currentColor" width="14" height="14">
            <path d="M2 2h12v12H2V2zm1 1v10h10V3H3z"/>
            <path d="M3 7.5h10v1H3z" opacity="0.4"/>
          </svg>
        </button>
        <button class="icon-btn" title="折叠侧边栏" @click="emit('toggleCollapse')">
          <svg viewBox="0 0 16 16" fill="currentColor" width="14" height="14">
            <path d="M9 4L5 8l4 4V4z" />
          </svg>
        </button>
      </div>
    </div>
    <div class="sidebar-body">
      <FileTreeItem
        v-for="node in tree"
        :key="node.id"
        :node="node"
        :depth="0"
        :active-file-id="activeFileId"
        :expanded-folders="expandedFolders"
        @select="emit('select', $event)"
        @toggle="emit('toggleFolder', $event)"
        @create-file="emit('createFile', $event)"
        @create-from-template="emit('createFromTemplate', $event)"
        @rename-file="(path, name) => emit('renameFile', path, name)"
        @delete-file="emit('deleteFile', $event)"
      />
    </div>
  </aside>
</template>
