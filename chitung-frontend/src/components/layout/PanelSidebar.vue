<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const props = defineProps<{
  activePanel: string
}>()

interface MenuItem {
  icon: string
  label: string
  path: string
  note?: string
}

interface PanelDef {
  id: string
  icon: string
  label: string
  tagline: string
  items: MenuItem[]
}

const panels: Record<string, PanelDef> = {
  guardian: {
    id: 'guardian',
    icon: '🛡️',
    label: '望风险',
    tagline: '赤瞳守护者',
    items: [
      { icon: '📊', label: '工作台总览', path: '/guardian/dashboard' },
      { icon: '✅', label: '待确认事项', path: '/guardian/confirmations' },
      { icon: '📋', label: '隐患台账', path: '/guardian/hazards' },
      { icon: '📷', label: '视觉巡检', path: '/guardian/patrol' },
    ],
  },
  docmate: {
    id: 'docmate',
    icon: '📄',
    label: '书文稿',
    tagline: '闪闪文档',
    items: [
      { icon: '✨', label: '文档审阅', path: '/docmate/documents', note: 'DOCX' },
      { icon: '📝', label: '智能填表', path: '/docmate/forms' },
      { icon: '🧾', label: '表格映射', path: '/docmate/table-mapping', note: 'C-SMART' },
      { icon: '📈', label: '报告生成', path: '/docmate/reports', note: '简报' },
    ],
  },
  lingxun: {
    id: 'lingxun',
    icon: '💬',
    label: '闻动态',
    tagline: '赤瞳灵讯',
    items: [
      { icon: '📱', label: 'WhatsApp 运维', path: '/lingxun/whatsapp' },
    ],
  },
  center: {
    id: 'center',
    icon: '🧩',
    label: '统全局',
    tagline: '赤瞳中台',
    items: [
      { icon: '⚙️', label: '系统设置', path: '/center/settings' },
      { icon: '🤖', label: 'AI 助手', path: '/center/assistant' },
      { icon: '🧠', label: 'Skill 技能', path: '/center/skills', note: '兼容' },
      { icon: '🔀', label: 'Workflow 工作流', path: '/center/workflows', note: '兼容' },
    ],
  },
  yaoyao: {
    id: 'yaoyao',
    icon: '📚',
    label: '问制度',
    tagline: '耀耀慧读',
    items: [
      { icon: '📸', label: 'OCR 结构化', path: '/yaoyao/structured' },
      { icon: '🔎', label: 'RAG 检索', path: '/yaoyao/rag', note: '预留' },
      { icon: '🌐', label: '舆情规范', path: '/yaoyao/feed', note: '预留' },
    ],
  },
}

const route = useRoute()
const router = useRouter()
const currentPanel = computed(() => panels[props.activePanel] || panels.guardian)

function isActive(path: string): boolean {
  return route.path === path
}
</script>

<template>
  <aside class="panel-sidebar">
    <div class="panel-sidebar__header">
      <span class="panel-sidebar__header-icon">{{ currentPanel.icon }}</span>
      <div class="panel-sidebar__header-text">
        <span class="panel-sidebar__header-label">{{ currentPanel.label }}</span>
        <span class="panel-sidebar__header-tagline">{{ currentPanel.tagline }}</span>
      </div>
    </div>

    <nav class="panel-sidebar__nav">
      <button
        v-for="item in currentPanel.items"
        :key="item.path"
        class="panel-sidebar__item"
        :class="{ 'panel-sidebar__item--active': isActive(item.path) }"
        @click="router.push(item.path)"
      >
        <span class="panel-sidebar__item-icon">{{ item.icon }}</span>
        <span class="panel-sidebar__item-label">{{ item.label }}</span>
        <span v-if="item.note" class="panel-sidebar__badge">{{ item.note }}</span>
      </button>
    </nav>

    <div class="panel-sidebar__footer">
      <span>v2.0 · 五大板块</span>
    </div>
  </aside>
</template>

<style scoped>
.panel-sidebar {
  background: var(--rail-bg);
  border-right: 1px solid var(--rail-border);
  color: var(--rail-text);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  height: 100%;
  overflow-y: auto;
  user-select: none;
  width: 232px;
}

.panel-sidebar__header {
  align-items: center;
  border-bottom: 1px solid var(--rail-border);
  display: flex;
  gap: 11px;
  padding: 18px 16px 14px;
}

.panel-sidebar__header-icon {
  align-items: center;
  background: linear-gradient(135deg, rgb(255 255 255 / 10%), rgb(255 255 255 / 4%));
  border: 1px solid var(--rail-border);
  border-radius: var(--radius-lg);
  display: flex;
  font-size: 20px;
  height: 38px;
  justify-content: center;
  width: 38px;
}

.panel-sidebar__header-text {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
}

.panel-sidebar__header-label {
  color: #eef1f6;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.2px;
}

.panel-sidebar__header-tagline,
.panel-sidebar__footer {
  color: var(--rail-text-muted);
  font-size: 12px;
}

.panel-sidebar__nav {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 3px;
  padding: 10px 8px;
}

.panel-sidebar__item {
  align-items: center;
  background: transparent;
  border: 0;
  border-radius: var(--radius-md);
  color: var(--rail-text-muted);
  display: flex;
  gap: 11px;
  padding: 9px 12px;
  position: relative;
  text-align: left;
  transition: background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease);
  width: 100%;
}

.panel-sidebar__item:hover {
  background: var(--rail-hover);
  color: var(--rail-text);
}

.panel-sidebar__item--active {
  background: var(--rail-active-bg);
  color: var(--rail-active-text);
  font-weight: 600;
}

.panel-sidebar__item--active::before {
  background: var(--rail-accent);
  border-radius: 0 3px 3px 0;
  bottom: 8px;
  content: '';
  left: -8px;
  position: absolute;
  top: 8px;
  width: 3px;
}

.panel-sidebar__item-icon {
  font-size: 15px;
  text-align: center;
  width: 18px;
}

.panel-sidebar__item-label {
  flex: 1;
}

.panel-sidebar__badge {
  background: rgb(255 255 255 / 6%);
  border: 1px solid var(--rail-border);
  border-radius: var(--radius-round);
  color: var(--rail-text-muted);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.3px;
  padding: 1px 7px;
}

.panel-sidebar__item--active .panel-sidebar__badge {
  border-color: rgb(255 112 124 / 40%);
  color: var(--rail-active-text);
}

.panel-sidebar__footer {
  border-top: 1px solid var(--rail-border);
  padding: 12px 16px;
}
</style>
