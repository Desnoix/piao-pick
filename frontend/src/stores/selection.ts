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
