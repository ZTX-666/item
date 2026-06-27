<script setup lang="ts">
import { useToast } from '../../composables/useToast'

const { toasts, dismiss } = useToast()
</script>

<template>
  <div class="toast-host" aria-live="polite" aria-relevant="additions">
    <TransitionGroup name="toast-slide">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        class="toast-item"
        :class="`toast-item--${toast.kind}`"
        role="status"
      >
        <span class="toast-item__icon" aria-hidden="true">
          {{ toast.kind === 'success' ? '✓' : toast.kind === 'error' ? '!' : 'i' }}
        </span>
        <p class="toast-item__message">{{ toast.message }}</p>
        <button class="toast-item__close" type="button" aria-label="关闭" @click="dismiss(toast.id)">
          ×
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-host {
  bottom: 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
  position: fixed;
  right: 20px;
  width: min(360px, calc(100vw - 40px));
  z-index: 100;
}

.toast-item {
  align-items: flex-start;
  background: var(--bg-white);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  display: grid;
  gap: 10px;
  grid-template-columns: auto 1fr auto;
  padding: 12px 14px;
  pointer-events: auto;
}

.toast-item--success {
  border-left: 3px solid var(--brand-green);
}

.toast-item--error {
  border-left: 3px solid var(--brand-red);
}

.toast-item--info {
  border-left: 3px solid var(--brand-cyan);
}

.toast-item__icon {
  align-items: center;
  background: var(--bg-subtle);
  border-radius: var(--radius-round);
  display: inline-flex;
  font-size: 11px;
  font-weight: 700;
  height: 22px;
  justify-content: center;
  width: 22px;
}

.toast-item--success .toast-item__icon {
  background: #edf7e8;
  color: var(--brand-green);
}

.toast-item--error .toast-item__icon {
  background: var(--brand-red-light);
  color: var(--brand-red);
}

.toast-item--info .toast-item__icon {
  background: #e8f4fd;
  color: var(--brand-cyan);
}

.toast-item__message {
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.45;
  margin: 0;
  padding-top: 2px;
}

.toast-item__close {
  background: transparent;
  border: 0;
  color: var(--text-muted);
  font-size: 18px;
  line-height: 1;
  padding: 0 2px;
}

.toast-item__close:hover {
  color: var(--text-primary);
}

.toast-slide-enter-active,
.toast-slide-leave-active {
  transition: opacity 0.22s var(--ease-out), transform 0.22s var(--ease-out);
}

.toast-slide-enter-from,
.toast-slide-leave-to {
  opacity: 0;
  transform: translateX(12px);
}

.toast-slide-move {
  transition: transform 0.22s var(--ease-out);
}
</style>
