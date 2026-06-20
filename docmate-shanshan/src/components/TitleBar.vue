<script setup lang="ts">
import { ref, onMounted } from 'vue'

defineProps<{
  sidebarOpen?: boolean
  chatOpen?: boolean
}>()

const emit = defineEmits<{
  toggleSidebar: []
  toggleChat: []
}>()

const isMaximized = ref(false)
const appLogoUrl = new URL('./闪闪文档.png', window.location.href).href

function minimize() {
  window.electronAPI?.minimize()
}

async function handleMaximize() {
  if (!window.electronAPI) return
  await window.electronAPI.maximize()
  isMaximized.value = await window.electronAPI.isMaximized()
}

function closeWindow() {
  window.electronAPI?.close()
}

onMounted(async () => {
  if (window.electronAPI) {
    isMaximized.value = await window.electronAPI.isMaximized()
  }
})
</script>

<template>
  <header class="titlebar">
    <div class="titlebar-left">
      <img :src="appLogoUrl" alt="DocMate" class="app-logo" />
      <span class="titlebar-title">DocMate 闪闪文档</span>
    </div>

    <div class="titlebar-nav">
      <button
        class="nav-btn"
        :class="{ active: sidebarOpen }"
        title="文件列表 (Ctrl+B)"
        @click="emit('toggleSidebar')"
      >
        <svg viewBox="0 0 16 16" fill="currentColor" width="14" height="14">
          <path d="M2 3h12v1H2V3zm0 4h8v1H2V7zm0 4h12v1H2v-1z"/>
        </svg>
        文件
      </button>
      <button
        class="nav-btn"
        :class="{ active: chatOpen }"
        title="闪闪助手 (Ctrl+K)"
        @click="emit('toggleChat')"
      >
        <svg viewBox="0 0 16 16" fill="currentColor" width="14" height="14">
          <path d="M8 1a7 7 0 100 14A7 7 0 008 1zm0 3a1 1 0 100 2 1 1 0 000-2zm1 4H7v4h2V8z"/>
        </svg>
        闪闪
      </button>
    </div>

    <div class="titlebar-center titlebar-drag">
      <span class="titlebar-badge">写字板 · 语音改稿 · 确认替换</span>
    </div>

    <div class="titlebar-controls">
      <button class="win-btn" title="最小化" @click="minimize">
        <svg viewBox="0 0 12 12"><rect y="5" width="12" height="1.5" fill="currentColor" /></svg>
      </button>
      <button class="win-btn" title="最大化" @click="handleMaximize">
        <svg v-if="!isMaximized" viewBox="0 0 12 12">
          <rect x="1" y="1" width="10" height="10" stroke="currentColor" stroke-width="1.2" fill="none" />
        </svg>
        <svg v-else viewBox="0 0 12 12">
          <rect x="2.5" y="0.5" width="8" height="8" stroke="currentColor" stroke-width="1.2" fill="none" />
          <rect x="0.5" y="2.5" width="8" height="8" stroke="currentColor" stroke-width="1.2" fill="var(--bg-base)" />
        </svg>
      </button>
      <button class="win-btn close" title="关闭" @click="closeWindow">
        <svg viewBox="0 0 12 12">
          <path d="M1 1l10 10M11 1L1 11" stroke="currentColor" stroke-width="1.3" />
        </svg>
      </button>
    </div>
  </header>
</template>

<style scoped>
.titlebar {
  height: var(--titlebar-height);
  background: var(--bg-base);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 0 0 12px;
  flex-shrink: 0;
  user-select: none;
  -webkit-app-region: drag;
}

.titlebar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  -webkit-app-region: drag;
}

.titlebar-nav {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-left: 12px;
  flex-shrink: 0;
  -webkit-app-region: no-drag;
}

.nav-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  font-size: 11px;
  border-radius: 5px;
  color: var(--text-secondary);
  transition: all 0.15s;
}

.nav-btn:hover,
.nav-btn.active {
  background: var(--bg-hover);
  color: var(--text-bright);
}

.nav-btn.active {
  color: var(--accent);
}

.app-logo {
  width: 22px;
  height: 22px;
  border-radius: 4px;
  -webkit-app-region: no-drag;
}

.titlebar-title {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
}

.titlebar-center {
  flex: 1;
  display: flex;
  justify-content: center;
  min-width: 0;
  -webkit-app-region: drag;
}

.titlebar-badge {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.titlebar-controls {
  display: flex;
  flex-shrink: 0;
  -webkit-app-region: no-drag;
}

.win-btn {
  width: 46px;
  height: var(--titlebar-height);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  transition: background 0.1s, color 0.1s;
}

.win-btn svg {
  width: 12px;
  height: 12px;
}

.win-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.win-btn.close:hover {
  background: #e81123;
  color: white;
}
</style>
