export const API_BASE = import.meta.env.VITE_WACLI_API_BASE ?? 'http://127.0.0.1:8790'

export async function apiGet<T>(path: string): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`)
  if (!resp.ok) throw new Error(`${resp.status} ${await resp.text()}`)
  return resp.json() as Promise<T>
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!resp.ok) throw new Error(`${resp.status} ${await resp.text()}`)
  return resp.json() as Promise<T>
}

export interface AppStatus {
  authStatusText: string
  authenticated: boolean
  syncRunning: boolean
  authRunning: boolean
  currentPhone: string
  dbPath: string
  wacliExeExists: boolean
  mediaProgressText: string
  statusDetail: string
}

export function getStatus() {
  return apiGet<AppStatus>('/api/app/status')
}

export function startQrAuth() {
  return apiPost<{ ok: boolean; message?: string; error?: string }>('/api/auth/qr/start')
}

export function startPhoneAuth(phone: string) {
  return apiPost<{ ok: boolean; message?: string; error?: string }>('/api/auth/phone/start', { phone })
}

export function stopAuth() {
  return apiPost<{ ok: boolean }>('/api/auth/stop')
}

export function startSync() {
  return apiPost<{ ok: boolean }>('/api/sync/start', { interruptAuth: true })
}

export function stopSync() {
  return apiPost<{ ok: boolean }>('/api/sync/stop')
}

export function qrPngBase64(payload: string) {
  return apiPost<{ ok: boolean; pngBase64?: string; error?: string }>('/api/auth/qr/png', { payload })
}

export function subscribeAuthEvents(handlers: {
  onLog?: (line: string) => void
  onQr?: (payload: string) => void
  onPairing?: (code: string) => void
  onAuthState?: (state: string) => void
}) {
  const es = new EventSource(`${API_BASE}/api/auth/events`)

  es.addEventListener('log', (e) => {
    const msg = JSON.parse(e.data)
    handlers.onLog?.(msg.data.line)
  })
  es.addEventListener('qr', (e) => {
    const msg = JSON.parse(e.data)
    handlers.onQr?.(msg.data.payload)
  })
  es.addEventListener('pairing_code', (e) => {
    const msg = JSON.parse(e.data)
    handlers.onPairing?.(msg.data.code)
  })
  es.addEventListener('auth_state', (e) => {
    const msg = JSON.parse(e.data)
    handlers.onAuthState?.(msg.data.state)
  })

  return () => es.close()
}
