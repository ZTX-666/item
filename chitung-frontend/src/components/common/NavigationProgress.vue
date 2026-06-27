<script setup lang="ts">
defineProps<{
  active: boolean
  progress: number
}>()
</script>

<template>
  <div class="nav-progress" :class="{ 'nav-progress--active': active }" aria-hidden="true">
    <div class="nav-progress__bar" :style="{ width: `${progress}%` }" />
  </div>
</template>

<style scoped>
.nav-progress {
  height: 2px;
  left: 0;
  opacity: 0;
  pointer-events: none;
  position: fixed;
  right: 0;
  top: 56px;
  transition: opacity 180ms var(--ease-out);
  z-index: 40;
}

.nav-progress--active {
  opacity: 1;
}

.nav-progress__bar {
  background: linear-gradient(90deg, var(--brand-cyan), var(--brand-red-bright));
  box-shadow: 0 0 10px rgb(15 158 213 / 45%);
  height: 100%;
  transition: width 220ms var(--ease-out);
  width: 0;
}
</style>
