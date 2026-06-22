import { computed, ref } from 'vue'

type ThemeMode = 'light' | 'dark'

const STORAGE_KEY = 'chitung-theme'
const initialTheme = localStorage.getItem(STORAGE_KEY) === 'dark' ? 'dark' : 'light'
const theme = ref<ThemeMode>(initialTheme)

function applyTheme(next: ThemeMode) {
  document.documentElement.dataset.theme = next
}

applyTheme(theme.value)

export function useTheme() {
  const isDark = computed(() => theme.value === 'dark')

  function setTheme(next: ThemeMode) {
    theme.value = next
    localStorage.setItem(STORAGE_KEY, next)
    applyTheme(next)
  }

  function toggleTheme() {
    setTheme(theme.value === 'dark' ? 'light' : 'dark')
  }

  return {
    theme,
    isDark,
    setTheme,
    toggleTheme,
  }
}
