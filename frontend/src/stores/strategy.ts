import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Strategy } from '../types/strategy'
import {
  listStrategies,
  deleteStrategy as apiDeleteStrategy,
  updateStrategy as apiUpdateStrategy,
} from '../api/strategies'

export const useStrategyStore = defineStore('strategy', () => {
  const strategies = ref<Strategy[]>([])
  const loading = ref(false)

  const activeStrategies = computed(() => strategies.value.filter((s) => s.is_active))

  async function fetchStrategies(options?: { silent?: boolean }) {
    loading.value = true
    try {
      strategies.value = await listStrategies(options)
    } catch (err: any) {
      // 忽略请求取消错误（来自 client.ts 的请求去重机制）
      if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return
      throw err // 重新抛出非取消错误，让调用方处理
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
