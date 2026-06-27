import { readonly, ref } from 'vue'

export type ToastKind = 'success' | 'error' | 'info'

export interface ToastItem {
  id: number
  message: string
  kind: ToastKind
}

const toasts = ref<ToastItem[]>([])
let nextId = 0

function dismiss(toastId: number) {
  toasts.value = toasts.value.filter((item) => item.id !== toastId)
}

function push(message: string, kind: ToastKind = 'info', duration = 3200) {
  const item: ToastItem = { id: ++nextId, message, kind }
  toasts.value = [...toasts.value, item]
  window.setTimeout(() => dismiss(item.id), duration)
}

export function useToast() {
  return {
    toasts: readonly(toasts),
    push,
    dismiss,
    success: (message: string) => push(message, 'success'),
    error: (message: string) => push(message, 'error', 4200),
    info: (message: string) => push(message, 'info'),
  }
}
