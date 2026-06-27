import { ref } from 'vue'

/**
 * Wraps async actions with double-submit guard and delayed busy indicator.
 * Avoids spinner flicker for fast responses (< delayMs), per INP best practices.
 */
export function useBusyAction(delayMs = 220) {
  const busy = ref(false)
  const showBusy = ref(false)

  let delayTimer: number | undefined

  function clearDelayTimer() {
    if (delayTimer) {
      window.clearTimeout(delayTimer)
      delayTimer = undefined
    }
  }

  async function run<T>(fn: () => Promise<T>): Promise<T | undefined> {
    if (busy.value) return undefined
    busy.value = true
    delayTimer = window.setTimeout(() => {
      showBusy.value = true
    }, delayMs)

    try {
      return await fn()
    } finally {
      busy.value = false
      showBusy.value = false
      clearDelayTimer()
    }
  }

  return { busy, showBusy, run }
}
