import { onMounted, onUnmounted, watch, ref, type Ref } from 'vue'

const DRAG_MARGIN = 40

export function useDraggable(
  targetRef: Ref<HTMLElement | null>,
  handleRef: Ref<HTMLElement | null>,
  enabled?: Ref<boolean>,
) {
  const enabledRef = enabled ?? ref(true)
  let startX = 0
  let startY = 0
  let originX = 0
  let originY = 0
  let dragging = false

  function onMouseDown(e: MouseEvent) {
    if (!enabledRef.value) return
    const target = targetRef.value
    if (!target || e.button !== 0) return
    if (e.target instanceof HTMLElement && e.target.closest('button, input, textarea, select, a')) return
    dragging = true
    startX = e.clientX
    startY = e.clientY
    const rect = target.getBoundingClientRect()
    originX = rect.left
    originY = rect.top
    target.style.position = 'fixed'
    target.style.right = 'auto'
    target.style.bottom = 'auto'
    target.style.left = `${originX}px`
    target.style.top = `${originY}px`
    target.style.margin = '0'
    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
    e.preventDefault()
  }

  function onMouseMove(e: MouseEvent) {
    if (!dragging || !targetRef.value) return
    const dx = e.clientX - startX
    const dy = e.clientY - startY
    const el = targetRef.value
    const w = el.offsetWidth
    const vw = window.innerWidth
    const vh = window.innerHeight
    const nextX = Math.max(-w + DRAG_MARGIN, Math.min(originX + dx, vw - DRAG_MARGIN))
    const nextY = Math.max(0, Math.min(originY + dy, vh - DRAG_MARGIN))
    el.style.left = `${nextX}px`
    el.style.top = `${nextY}px`
  }

  function onMouseUp() {
    dragging = false
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
  }

  function resetInlinePosition() {
    dragging = false
    const target = targetRef.value
    if (!target) return
    target.style.position = ''
    target.style.right = ''
    target.style.bottom = ''
    target.style.left = ''
    target.style.top = ''
    target.style.margin = ''
  }

  function bind() {
    handleRef.value?.addEventListener('mousedown', onMouseDown)
  }

  function unbind() {
    handleRef.value?.removeEventListener('mousedown', onMouseDown)
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
  }

  onMounted(() => {
    if (enabledRef.value) bind()
    watch(enabledRef, (on) => {
      unbind()
      if (on) {
        bind()
      } else {
        resetInlinePosition()
      }
    })
  })

  onUnmounted(() => {
    unbind()
    resetInlinePosition()
  })
}
