import { onScopeDispose, ref } from 'vue'
import type { Router } from 'vue-router'

const navigating = ref(false)
const progress = ref(0)

let installCount = 0
let progressTimer: number | undefined
let finishTimer: number | undefined

function clearTimers() {
  if (progressTimer) {
    window.clearInterval(progressTimer)
    progressTimer = undefined
  }
  if (finishTimer) {
    window.clearTimeout(finishTimer)
    finishTimer = undefined
  }
}

function startProgress() {
  clearTimers()
  navigating.value = true
  progress.value = 18
  progressTimer = window.setInterval(() => {
    progress.value = Math.min(progress.value + 6, 88)
  }, 140)
}

function finishProgress() {
  clearTimers()
  progress.value = 100
  finishTimer = window.setTimeout(() => {
    navigating.value = false
    progress.value = 0
  }, 320)
}

export function useNavigationProgress(router: Router) {
  installCount += 1
  if (installCount > 1) {
    return { navigating, progress }
  }

  router.beforeEach((to, from, next) => {
    if (to.fullPath !== from.fullPath) startProgress()
    next()
  })

  router.afterEach(() => {
    finishProgress()
  })

  router.onError(() => {
    finishProgress()
  })

  onScopeDispose(() => {
    installCount = Math.max(0, installCount - 1)
    if (installCount === 0) clearTimers()
  })

  return { navigating, progress }
}
