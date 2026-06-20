<script setup lang="ts">
type NavItem = {
  icon: string
  label: string
  page: string
  badge?: string
  badgeTone?: 'blue'
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
      { icon: '📊', label: '工作台总览', page: 'workbench' },
      { icon: '💬', label: 'AI 对话助手', page: 'assistant' },
      { icon: '📱', label: 'WhatsApp 消息', page: 'whatsapp' },
    ],
  },
  {
    title: '工具',
    items: [
      { icon: '📝', label: '智能填表', page: 'workbench' },
      { icon: '📊', label: '每日简报', page: 'workbench' },
      { icon: '⚠️', label: '风险雷达', page: 'workbench' },
      { icon: '🚧', label: '机械 & LALG', page: 'workbench' },
      { icon: '🤖', label: '混合编排', page: 'workbench' },
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
        <span
          v-if="item.badge"
          class="sidebar__badge"
          :class="{ 'sidebar__badge--blue': item.badgeTone === 'blue' }"
        >
          {{ item.badge }}
        </span>
      </button>
    </section>
  </aside>
</template>
