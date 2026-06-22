<script setup lang="ts">
type NavItem = {
  icon: string
  label: string
  page: string
}

type NavGroup = {
  title: string
  items: NavItem[]
}

const props = defineProps<{
  currentPage: string
}>()

const emit = defineEmits<{
  navigate: [page: string]
}>()

const groups: NavGroup[] = [
  {
    title: '主菜单',
    items: [
      { icon: '📋', label: '隐患台账', page: 'hazard-ledger' },
      { icon: '📷', label: '视觉巡检', page: 'visual-patrol' },
      { icon: '📝', label: '智能填表', page: 'smart-form' },
      { icon: '✨', label: '闪闪文档', page: 'shanshan-doc' },
      { icon: '📖', label: '耀耀慧读', page: 'yaoyao-structured-input' },
    ],
  },
  {
    title: '工具',
    items: [
      { icon: '📊', label: '每日简报', page: 'workbench' },
      { icon: '⚠️', label: '风险雷达', page: 'workbench' },
      { icon: '🚧', label: '机械 & LALG', page: 'workbench' },
      { icon: '💬', label: 'AI 助手', page: 'workbench' },
      { icon: '📱', label: 'WhatsApp', page: 'workbench' },
    ],
  },
]
</script>

<template>
  <aside class="sidebar">
    <section v-for="group in groups" :key="group.title" class="sidebar__section">
      <h2 class="sidebar__section-title">{{ group.title }}</h2>
      <button
        v-for="item in group.items"
        :key="item.label"
        class="sidebar__item"
        :class="{ 'sidebar__item--active': props.currentPage === item.page }"
        @click="emit('navigate', item.page)"
      >
        <span class="sidebar__item-icon">{{ item.icon }}</span>
        <span>{{ item.label }}</span>
      </button>
    </section>
  </aside>
</template>
