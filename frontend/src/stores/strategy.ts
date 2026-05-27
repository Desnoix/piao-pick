import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Strategy } from '../types/strategy'
import { listStrategies, deleteStrategy as apiDeleteStrategy, updateStrategy as apiUpdateStrategy } from '../api/strategies'

export const useStrategyStore = defineStore('strategy', () => {
  const strategies = ref<Strategy[]>([])
  const loading = ref(false)

  const activeStrategies = computed(() => strategies.value.filter((s) => s.is_active))

  async function fetchStrategies() {
    loading.value = true
    try {
      strategies.value = await listStrategies()
    } finally {
      loading.value = false
    }
  }

  async function toggleStrategy(id: string, is_active: boolean) {
    await apiUpdateStrategy(id, { is_active })
    const idx = strategies.value.findIndex((s) => s.id === id)
    if (idx >= 0) {
      strategies.value[idx].is_active = is_active
    }
  }

  async function removeStrategy(id: string) {
    await apiDeleteStrategy(id)
    strategies.value = strategies.value.filter((s) => s.id !== id)
  }

  return {
    strategies,
    activeStrategies,
    loading,
    fetchStrategies,
    toggleStrategy,
    removeStrategy,
  }
})
