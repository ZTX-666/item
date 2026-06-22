<script setup lang="ts">
import { onMounted, ref } from 'vue'
import brandLogo from '../../assets/logos/brand.jpg'

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
    <img class="topbar__logo" :src="brandLogo" alt="赤瞳安全智能平台" />
    <div class="topbar__brand">
      <strong>赤瞳安全智能平台</strong>
      <span>CSCEC Safety Intelligence · Cursor Edition</span>
    </div>
    <div class="topbar__right">
      <span class="desktop-pill">{{ runtimeLabel }}</span>
      <button class="icon-button" title="通知">🔔</button>
      <button class="icon-button" title="设置">⚙️</button>
      <div class="avatar">陈</div>
    </div>
  </header>
</template>
