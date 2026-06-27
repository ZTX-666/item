<script setup lang="ts">
import guardianLogo from '../../assets/logos/guardian.png'
import docmateLogo from '../../assets/logos/docmate.png'
import lingxunLogo from '../../assets/logos/lingxun.png'
import centerLogo from '../../assets/logos/center.png'
import yaoyaoLogo from '../../assets/logos/yaoyao.png'
import assistantAvatar from '../../assets/logos/assistant-avatar.png'
import { prefetchPanel } from '../../router/routePrefetch'

defineProps<{
  activePanel: string
}>()

const emit = defineEmits<{
  select: [panel: string]
}>()

const panels = [
  { id: 'guardian', logo: guardianLogo, label: '赤瞳守護者' },
  { id: 'docmate', logo: docmateLogo, label: '閃閃文檔' },
  { id: 'lingxun', logo: lingxunLogo, label: '赤瞳聆訊' },
  { id: 'yaoyao', logo: yaoyaoLogo, label: '耀耀慧讀' },
  { id: 'center', logo: centerLogo, label: '赤瞳中台' },
]

const assistantLogo = assistantAvatar
</script>

<template>
  <div class="activity-bar">
    <div class="activity-bar__top">
      <button
        v-for="panel in panels"
        :key="panel.id"
        class="activity-bar__item"
        :class="{ 'activity-bar__item--active': activePanel === panel.id }"
        :title="panel.label"
        @mouseenter="prefetchPanel(panel.id)"
        @click="emit('select', panel.id)"
      >
        <img class="activity-bar__logo" :src="panel.logo" :alt="panel.label" />
        <span class="activity-bar__label">{{ panel.label }}</span>
      </button>
    </div>
    <div class="activity-bar__bottom">
      <button class="activity-bar__item" title="AI 助手" @click="emit('select', 'chatbot')">
        <span class="activity-bar__assistant-wrap">
          <img class="activity-bar__assistant-img" :src="assistantLogo" alt="AI 助手头像" loading="eager" />
        </span>
        <span class="activity-bar__label">助手</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.activity-bar {
  align-items: center;
  background: linear-gradient(180deg, var(--rail-bg-2) 0%, var(--rail-bg) 100%);
  border-right: 1px solid var(--rail-border);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  height: 100%;
  justify-content: space-between;
  padding: 10px 0;
  width: 72px;
}

.activity-bar__top,
.activity-bar__bottom {
  align-items: center;
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
}

.activity-bar__item {
  align-items: center;
  background: transparent;
  border: 0;
  border-radius: var(--radius-md);
  color: var(--rail-text-muted);
  display: flex;
  flex-direction: column;
  gap: 4px;
  justify-content: center;
  margin: 0 8px;
  padding: 8px 0;
  position: relative;
  transition: color var(--dur-fast) var(--ease), background var(--dur-fast) var(--ease), transform var(--dur-fast) var(--ease-out);
  width: 56px;
}

.activity-bar__item:active {
  transform: scale(0.94);
}

.activity-bar__item:hover {
  background: var(--rail-hover);
  color: var(--rail-text);
}

.activity-bar__item--active {
  background: var(--rail-active-bg);
  color: var(--rail-active-text);
}

.activity-bar__item--active::before {
  background: var(--rail-accent);
  border-radius: 0 3px 3px 0;
  bottom: 10px;
  content: '';
  left: -8px;
  position: absolute;
  top: 10px;
  width: 3px;
}

.activity-bar__logo {
  width: 30px;
  height: 30px;
  object-fit: contain;
  border-radius: var(--radius-sm);
  opacity: 0.9;
  transition: opacity var(--dur-fast) var(--ease), transform var(--dur-fast) var(--ease);
}

.activity-bar__item:hover .activity-bar__logo,
.activity-bar__item--active .activity-bar__logo {
  opacity: 1;
  transform: scale(1.06);
}

.activity-bar__assistant-wrap {
  align-items: center;
  background: linear-gradient(135deg, #fff, #f3f6fb);
  border: 1px solid var(--rail-border);
  border-radius: var(--radius-round);
  display: flex;
  height: 34px;
  justify-content: center;
  padding: 2px;
  width: 34px;
}

.activity-bar__assistant-img {
  border-radius: var(--radius-round);
  box-shadow: 0 0 0 1px rgb(0 0 0 / 8%);
  display: block;
  height: 100%;
  object-fit: cover;
  width: 100%;
}

.activity-bar__item:hover .activity-bar__assistant-wrap,
.activity-bar__item--active .activity-bar__assistant-wrap {
  border-color: rgb(51 112 255 / 45%);
  box-shadow: 0 0 0 2px rgb(51 112 255 / 18%);
  transform: scale(1.1);
}

.activity-bar__label {
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.2px;
  line-height: 1.15;
  text-align: center;
}
</style>
