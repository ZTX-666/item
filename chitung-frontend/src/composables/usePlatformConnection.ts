import { onBeforeUnmount, ref } from 'vue'
import { getHealth } from '../services/chitungApi'

const connected = ref(false)
const reconnecting = ref(false)
const lastError = ref('')
const lastOkAt = ref<string | null>(null)

/** Keep UI stable when center is busy (patrol/RAG) but still alive. */
const GRACE_MS = 45000
const FAILURES_BEFORE_DISCONNECT = 2

let timer: number | undefined
let probeInFlight = false
let failStreak = 0

function withinGraceWindow(): boolean {
  if (!lastOkAt.value) return false
  return Date.now() - Date.parse(lastOkAt.value) < GRACE_MS
}

async function probe(): Promise<boolean> {
  if (probeInFlight) return connected.value
  probeInFlight = true
  try {
    if (connected.value || withinGraceWindow()) {
      reconnecting.value = failStreak > 0
    } else if (failStreak > 0) {
      reconnecting.value = true
    }
    await getHealth()
    connected.value = true
    reconnecting.value = false
    lastError.value = ''
    failStreak = 0
    lastOkAt.value = new Date().toISOString()
    return true
  } catch (error) {
    failStreak += 1
    lastError.value = error instanceof Error ? error.message : String(error)
    const softFailure = withinGraceWindow() && failStreak < FAILURES_BEFORE_DISCONNECT
    if (softFailure) {
      connected.value = true
      reconnecting.value = true
      return true
    }
    connected.value = false
    reconnecting.value = true
    return false
  } finally {
    probeInFlight = false
  }
}

function scheduleNextProbe() {
  const delayMs = connected.value ? 8000 : failStreak > 0 ? 2500 : 4000
  timer = window.setTimeout(() => {
    void probe().finally(() => {
      scheduleNextProbe()
    })
  }, delayMs)
}

function startPlatformConnectionMonitor(_intervalMs = 5000) {
  stopPlatformConnectionMonitor()
  void probe().finally(() => {
    scheduleNextProbe()
  })
}

function stopPlatformConnectionMonitor() {
  if (timer) {
    window.clearTimeout(timer)
    timer = undefined
  }
}

export function usePlatformConnection() {
  onBeforeUnmount(() => {
    // Shared monitor lives for app lifetime; child components must not stop it.
  })

  return {
    connected,
    reconnecting,
    lastError,
    lastOkAt,
    probe,
    startPlatformConnectionMonitor,
    stopPlatformConnectionMonitor,
  }
}
