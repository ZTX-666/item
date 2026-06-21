<template>
  <div class="layout">
    <header class="header">
      <strong>赤瞳灵讯 · Vue 对接示例</strong>
      <nav>
        <RouterLink to="/">首页</RouterLink>
        <RouterLink to="/login">登录配对</RouterLink>
      </nav>
    </header>
    <main class="main">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>
