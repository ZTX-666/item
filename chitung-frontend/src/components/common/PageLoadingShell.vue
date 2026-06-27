<script setup lang="ts">
import SkeletonLoader from './SkeletonLoader.vue'
</script>

<template>
  <main class="workbench page-loading-shell" aria-busy="true" aria-label="页面加载中">
    <section class="page-loading-shell__hero">
      <div class="skeleton-bar skeleton-bar--hero-title" />
      <div class="skeleton-bar skeleton-bar--hero-text" />
    </section>
    <SkeletonLoader type="cards" :count="3" />
  </main>
</template>

<style scoped>
.page-loading-shell {
  min-height: calc(100vh - 56px);
}

.page-loading-shell__hero {
  background: var(--bg-white);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-xl);
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 16px;
  padding: 22px 26px;
}

.skeleton-bar {
  animation: skeleton-shimmer 1.4s ease-in-out infinite;
  background: linear-gradient(
    90deg,
    var(--bg-subtle) 25%,
    var(--bg-hover) 50%,
    var(--bg-subtle) 75%
  );
  background-size: 200% 100%;
  border-radius: var(--radius-sm);
  height: 12px;
}

.skeleton-bar--hero-title {
  height: 22px;
  width: 38%;
}

.skeleton-bar--hero-text {
  width: 62%;
}

@keyframes skeleton-shimmer {
  0% {
    background-position: 200% 0;
  }

  100% {
    background-position: -200% 0;
  }
}
</style>
