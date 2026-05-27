import { ref, watch, type Ref } from 'vue'
import { getStock, getKline, getFactors } from '../api/stocks'
import type { StockInfo, Kline, FactorData } from '../types/stock'
import {
  generateMockKline,
  generateMockFactorSnapshot,
  generateMockFactorHistory,
  generateMockFinancialTrend,
} from '../utils/mock'

export interface StockDetailResult {
  stockInfo: Ref<StockInfo | null>
  klines: Ref<Kline[]>
  factorSnapshot: Ref<Record<string, number>>
  factorHistory: Ref<{ dates: string[]; factors: Record<string, number[]> }>
  financialTrend: Ref<{
    quarters: string[]
    revGrowth: number[]
    earGrowth: number[]
    grossMargin: number[]
  }>
  mockKline: Ref<boolean>
  mockFactors: Ref<boolean>
  loading: Ref<boolean>
  error: Ref<string>
  reload: () => Promise<void>
}

export function useStockDetail(tsCode: Ref<string>): StockDetailResult {
  const stockInfo = ref<StockInfo | null>(null)
  const klines = ref<Kline[]>([])
  const factorSnapshot = ref<Record<string, number>>({})
  const factorHistory = ref<{ dates: string[]; factors: Record<string, number[]> }>({
    dates: [],
    factors: {},
  })
  const financialTrend = ref<{
    quarters: string[]
    revGrowth: number[]
    earGrowth: number[]
    grossMargin: number[]
  }>({ quarters: [], revGrowth: [], earGrowth: [], grossMargin: [] })

  const mockKline = ref(false)
  const mockFactors = ref(false)
  const loading = ref(false)
  const error = ref('')

  async function loadData() {
    if (!tsCode.value) return
    loading.value = true
    error.value = ''
    mockKline.value = false
    mockFactors.value = false

    try {
      const [info, klineData, factorData] = await Promise.all([
        getStock(tsCode.value).catch(() => null),
        getKline(tsCode.value, 120).catch(() => [] as Kline[]),
        getFactors(tsCode.value).catch(() => [] as FactorData[]),
      ])

      stockInfo.value = info

      // Kline: real or mock
      if (klineData && klineData.length > 0) {
        klines.value = klineData
      } else {
        klines.value = generateMockKline(60, 50, tsCode.value)
        mockKline.value = true
      }

      // Factors: extract snapshot from latest record
      if (factorData && factorData.length > 0) {
        const latest = factorData[factorData.length - 1]
        const snapshot: Record<string, number> = {}
        for (const [key, val] of Object.entries(latest)) {
          if (key !== 'ts_code' && key !== 'trade_date' && typeof val === 'number') {
            snapshot[key] = Math.min(100, Math.max(0, val ?? 0))
          }
        }
        factorSnapshot.value = snapshot

        // Build factor history from full series
        const dates = factorData.map((f) => f.trade_date)
        const factorKeys = Object.keys(snapshot)
        const factors: Record<string, number[]> = {}
        for (const key of factorKeys) {
          factors[key] = factorData.map((f) => {
            const v = (f as unknown as Record<string, unknown>)[key]
            return typeof v === 'number' ? parseFloat(v.toFixed(1)) : 0
          })
        }
        factorHistory.value = { dates, factors }
      } else {
        factorSnapshot.value = generateMockFactorSnapshot()
        factorHistory.value = generateMockFactorHistory(8)
        mockFactors.value = true
      }

      // Financial trend: always mock for now (backend doesn't serve this yet)
      financialTrend.value = generateMockFinancialTrend()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string }
      error.value = err?.response?.data?.detail || err?.message || '加载失败'
    } finally {
      loading.value = false
    }
  }

  watch(tsCode, () => {
    loadData()
  }, { immediate: true })

  return {
    stockInfo,
    klines,
    factorSnapshot,
    factorHistory,
    financialTrend,
    mockKline,
    mockFactors,
    loading,
    error,
    reload: loadData,
  }
}
