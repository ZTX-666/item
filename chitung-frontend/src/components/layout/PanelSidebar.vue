<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useLocale } from '../../composables/useLocale'
import guardianLogo from '../../assets/logos/guardian.png'
import docmateLogo from '../../assets/logos/docmate.png'
import lingxunLogo from '../../assets/logos/lingxun.png'
import centerLogo from '../../assets/logos/center.png'
import yaoyaoLogo from '../../assets/logos/yaoyao.png'

const { display } = useLocale()

const props = defineProps<{
  activePanel: string
}>()

interface MenuItem {
  icon: string
  label: string
  path: string
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
    icon: guardianLogo,
    label: '赤瞳守护者',
    tagline: '望风险',
    items: [
      { icon: '📊', label: '视觉巡检总览', path: '/guardian/dashboard' },
      { icon: '✅', label: '待确认事项', path: '/guardian/confirmations' },
      { icon: '📋', label: '隐患台账', path: '/guardian/hazards' },
      { icon: '📷', label: '视觉巡检', path: '/guardian/patrol' },
    ],
  },
  docmate: {
    id: 'docmate',
    icon: docmateLogo,
    label: '闪闪文档',
    tagline: '书文档',
    items: [
      { icon: '✨', label: '文档审阅', path: '/docmate/documents' },
      { icon: '📝', label: '智能填表', path: '/docmate/forms' },
      { icon: '🧾', label: '表格映射', path: '/docmate/table-mapping' },
      { icon: '📈', label: '报告生成', path: '/docmate/reports' },
    ],
  },
  lingxun: {
    id: 'lingxun',
    icon: lingxunLogo,
    label: '赤瞳聆讯',
    tagline: '闻动态',
    items: [
      { icon: '📱', label: 'WhatsApp 运维', path: '/lingxun/whatsapp' },
      { icon: '🔍', label: '数据浏览', path: '/lingxun/browse' },
      { icon: '🗄️', label: 'SQL 查询', path: '/lingxun/sql' },
      { icon: '⚙️', label: '命令工具', path: '/lingxun/commands' },
    ],
  },
  center: {
    id: 'center',
    icon: centerLogo,
    label: '赤瞳中台',
    tagline: '统全局',
    items: [
      { icon: '⚙️', label: '系统设置', path: '/center/settings' },
      { icon: '🤖', label: 'AI助手', path: '/center/assistant' },
      { icon: '⏱️', label: '自动化', path: '/center/automation' },
      { icon: '🧠', label: '技能', path: '/center/skills' },
      { icon: '🔀', label: '工作流', path: '/center/workflows' },
    ],
  },
  yaoyao: {
    id: 'yaoyao',
    icon: yaoyaoLogo,
    label: '耀耀慧读',
    tagline: '问制度',
    items: [
      { icon: '📸', label: '结构化输入', path: '/yaoyao/structured' },
      { icon: '🔎', label: '耀耀知识', path: '/yaoyao/rag' },
      { icon: '🌐', label: '外部风险', path: '/yaoyao/feed' },
    ],
  },
}

const route = useRoute()
const router = useRouter()
const currentPanel = computed(() => panels[props.activePanel] || panels.guardian)

function isActive(path: string): boolean {
  if (path === '/center/automation' && route.path.startsWith('/automation')) return true
  return route.path === path
}
</script>

<template>
  <aside class="panel-sidebar">
    <div class="panel-sidebar__header">
      <img class="panel-sidebar__header-icon" :src="currentPanel.icon" :alt="display(currentPanel.label)" />
      <div class="panel-sidebar__header-text">
        <span class="panel-sidebar__header-label">{{ display(currentPanel.label) }}</span>
        <span class="panel-sidebar__header-tagline">{{ display(currentPanel.tagline) }}</span>
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
        <span class="panel-sidebar__item-label">{{ display(item.label) }}</span>
      </button>
    </nav>

    <div class="panel-sidebar__footer">
      <span>v2.0 · {{ display('五大板块') }}</span>
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
  background: linear-gradient(135deg, #fff, #f5f8ff);
  border: 1px solid var(--rail-border);
  border-radius: var(--radius-lg);
  flex-shrink: 0;
  height: 40px;
  object-fit: contain;
  padding: 4px;
  width: 40px;
}

.panel-sidebar__header-text {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
}

.panel-sidebar__header-label {
  color: var(--rail-text);
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

.panel-sidebar__footer {
  border-top: 1px solid var(--rail-border);
  padding: 12px 16px;
}
</style>
