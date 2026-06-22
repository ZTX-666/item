<script setup lang="ts">
import guardianLogo from '../../assets/logos/guardian.png'
import docmateLogo from '../../assets/logos/docmate.png'
import lingxunLogo from '../../assets/logos/lingxun.png'
import centerLogo from '../../assets/logos/center.png'
import yaoyaoLogo from '../../assets/logos/yaoyao.png'

defineProps<{
  activePanel: string
}>()

const emit = defineEmits<{
  select: [panel: string]
}>()

const panels = [
  { id: 'guardian', logo: guardianLogo, title: '赤瞳守护者', label: '望风险' },
  { id: 'docmate', logo: docmateLogo, title: '闪闪文档', label: '书文稿' },
  { id: 'lingxun', logo: lingxunLogo, title: '赤瞳灵讯', label: '闻动态' },
  { id: 'center', logo: centerLogo, title: '赤瞳中台', label: '统全局' },
  { id: 'yaoyao', logo: yaoyaoLogo, title: '耀耀慧读', label: '问制度' },
]
</script>

<template>
  <div class="activity-bar">
    <div class="activity-bar__top">
      <button
        v-for="panel in panels"
        :key="panel.id"
        class="activity-bar__item"
        :class="{ 'activity-bar__item--active': activePanel === panel.id }"
        :title="panel.title"
        @click="emit('select', panel.id)"
      >
        <img class="activity-bar__logo" :src="panel.logo" :alt="panel.title" />
        <span class="activity-bar__label">{{ panel.label }}</span>
      </button>
    </div>
    <div class="activity-bar__bottom">
      <button class="activity-bar__item" title="AI 助手" @click="emit('select', 'chatbot')">
        <span class="activity-bar__emoji">🤖</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.activity-bar {
  align-items: center;
  background: linear-gradient(180deg, var(--rail-bg-2, #14161b) 0%, var(--rail-bg, #181b21) 100%);
  border-right: 1px solid var(--rail-border, rgba(255, 255, 255, 0.07));
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
  border-radius: var(--radius-md, 8px);
  color: var(--rail-text-muted, #828a96);
  display: flex;
  flex-direction: column;
  gap: 4px;
  justify-content: center;
  margin: 0 8px;
  padding: 8px 0;
  position: relative;
  transition: color 0.15s, background 0.15s;
  width: 56px;
}

.activity-bar__item:hover {
  background: var(--rail-hover, rgba(255, 255, 255, 0.06));
  color: var(--rail-text, #cdd3dc);
}

.activity-bar__item--active {
  background: var(--rail-active-bg, rgba(231, 0, 18, 0.16));
  color: var(--rail-active-text, #ff707c);
}

.activity-bar__item--active::before {
  background: var(--rail-accent, #ff5a67);
  border-radius: 0 3px 3px 0;
  bottom: 10px;
  content: '';
  left: -8px;
  position: absolute;
  top: 10px;
  width: 3px;
}

.activity-bar__logo {
  border-radius: var(--radius-sm, 6px);
  height: 30px;
  object-fit: contain;
  opacity: 0.9;
  transition: opacity 0.15s, transform 0.15s;
  width: 30px;
}

.activity-bar__item:hover .activity-bar__logo,
.activity-bar__item--active .activity-bar__logo {
  opacity: 1;
  transform: scale(1.06);
}

.activity-bar__emoji {
  font-size: 22px;
  line-height: 1;
  opacity: 0.82;
  transition: opacity 0.15s, transform 0.15s;
}

.activity-bar__item:hover .activity-bar__emoji,
.activity-bar__item--active .activity-bar__emoji {
  opacity: 1;
  transform: scale(1.08);
}

.activity-bar__label {
  font-size: 10px;
  font-weight: 500;
  line-height: 1.15;
  text-align: center;
}
</style>
