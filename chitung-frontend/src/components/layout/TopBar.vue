<script setup lang="ts">
import { onMounted, ref } from 'vue'

const navItems = ['工作台', '隐患管理', '视觉巡检', '智能填表', '机械与 LALG', '整改通知', '风险雷达']
const runtimeLabel = ref('桌面控制台')

onMounted(async () => {
  if (!window.chitungDesktop) {
    runtimeLabel.value = '本地开发模式'
    return
  }

  const runtime = await window.chitungDesktop.getRuntime()
  runtimeLabel.value = `桌面版 · ${runtime.platform}`
})
</script>

<template>
  <header class="topbar">
    <div class="topbar__logo">中建</div>
    <div class="topbar__brand">
      <strong>赤瞳守护者</strong>
      <span>CSCEC Safety Intelligence</span>
    </div>
    <nav class="topbar__nav" aria-label="主导航">
      <button
        v-for="item in navItems"
        :key="item"
        class="topbar__nav-item"
        :class="{ 'topbar__nav-item--active': item === '工作台' }"
      >
        {{ item }}
      </button>
    </nav>
    <div class="topbar__right">
      <span class="desktop-pill">{{ runtimeLabel }}</span>
      <button class="icon-button" title="通知">🔔</button>
      <button class="icon-button" title="设置">⚙️</button>
      <div class="avatar">陈</div>
    </div>
  </header>
</template>
