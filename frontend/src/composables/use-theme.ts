import { computed } from 'vue'
import { useAppStore } from '../stores/app'

export function useTheme() {
  const appStore = useAppStore()

  const isDark = computed(() => appStore.isDark)
  const toggle = () => appStore.toggleTheme()

  return {
    isDark,
    toggle,
  }
}
