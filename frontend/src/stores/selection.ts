import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { SelectionRecord } from '../types/selection'
import { getSelectionResults } from '../api/selection'

export const useSelectionStore = defineStore('selection', () => {
  const results = ref<SelectionRecord[]>([])
  const loading = ref(false)

  async function fetchResults(strategy_id?: string, trade_date?: string) {
    loading.value = true
    try {
      results.value = await getSelectionResults(strategy_id, trade_date)
    } catch (err: any) {
      // 忽略请求取消错误（来自 client.ts 的请求去重机制）
      if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return
      throw err // 重新抛出非取消错误，让调用方处理
    } finally {
      loading.value = false
    }
  }

  return {
    results,
    loading,
    fetchResults,
  }
})
