import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSelectionStore } from './selection'
import type { SelectionRecord } from '../types/selection'

// Mock API module
vi.mock('../api/selection', () => ({
  getSelectionResults: vi.fn(),
}))

import { getSelectionResults } from '../api/selection'
const mockedGetResults = vi.mocked(getSelectionResults)

function createMockRecords(overrides?: Partial<SelectionRecord>[]): SelectionRecord[] {
  const defaults: SelectionRecord[] = [
    {
      strategy_id: 'strat-1',
      ts_code: '000001',
      trade_date: '2026-01-15',
      rank: 1,
      composite_score: 85.5,
      status: 'active',
      factor_snapshot: { pe_ttm: 0.8, roe_ttm: 1.2 },
      name: '平安银行',
      industry: '银行',
    },
    {
      strategy_id: 'strat-1',
      ts_code: '600519',
      trade_date: '2026-01-15',
      rank: 2,
      composite_score: 78.3,
      status: 'active',
      factor_snapshot: { pe_ttm: 1.5, roe_ttm: 2.1 },
      name: '贵州茅台',
      industry: '白酒',
    },
  ]
  if (!overrides) return defaults
  return defaults.map((d, i) => ({ ...d, ...(overrides[i] || {}) }))
}

describe('selection store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('initial state', () => {
    it('should have empty results array', () => {
      const store = useSelectionStore()
      expect(store.results).toEqual([])
    })

    it('should have loading false', () => {
      const store = useSelectionStore()
      expect(store.loading).toBe(false)
    })
  })

  describe('fetchResults', () => {
    it('should fetch and store selection results', async () => {
      const mockData = createMockRecords()
      mockedGetResults.mockResolvedValue(mockData)

      const store = useSelectionStore()
      await store.fetchResults()

      expect(store.results).toEqual(mockData)
      expect(store.results).toHaveLength(2)
    })

    it('should set loading true during fetch', async () => {
      let resolvePromise: (val: SelectionRecord[]) => void
      mockedGetResults.mockImplementation(
        () =>
          new Promise<SelectionRecord[]>((resolve) => {
            resolvePromise = resolve
          })
      )

      const store = useSelectionStore()
      const fetchPromise = store.fetchResults()

      expect(store.loading).toBe(true)
      resolvePromise!([])
      await fetchPromise
      expect(store.loading).toBe(false)
    })

    it('should reset loading to false after successful fetch', async () => {
      mockedGetResults.mockResolvedValue([])

      const store = useSelectionStore()
      await store.fetchResults()

      expect(store.loading).toBe(false)
    })

    it('should reset loading to false after failed fetch', async () => {
      mockedGetResults.mockRejectedValue(new Error('Network error'))

      const store = useSelectionStore()
      await store.fetchResults().catch(() => {})

      expect(store.loading).toBe(false)
    })

    it('should pass strategy_id to API', async () => {
      mockedGetResults.mockResolvedValue([])

      const store = useSelectionStore()
      await store.fetchResults('strat-1')

      expect(mockedGetResults).toHaveBeenCalledWith('strat-1', undefined)
    })

    it('should pass trade_date to API', async () => {
      mockedGetResults.mockResolvedValue([])

      const store = useSelectionStore()
      await store.fetchResults(undefined, '2026-01-15')

      expect(mockedGetResults).toHaveBeenCalledWith(undefined, '2026-01-15')
    })

    it('should pass both strategy_id and trade_date to API', async () => {
      mockedGetResults.mockResolvedValue([])

      const store = useSelectionStore()
      await store.fetchResults('strat-1', '2026-01-15')

      expect(mockedGetResults).toHaveBeenCalledWith('strat-1', '2026-01-15')
    })

    it('should replace previous results on new fetch', async () => {
      const firstBatch = createMockRecords()
      mockedGetResults.mockResolvedValueOnce(firstBatch)

      const store = useSelectionStore()
      await store.fetchResults('strat-1')
      expect(store.results).toHaveLength(2)

      const secondBatch = createMockRecords([{ ts_code: '300750', rank: 1 }])
      mockedGetResults.mockResolvedValueOnce(secondBatch)
      await store.fetchResults('strat-1')

      expect(store.results).toHaveLength(2)
      expect(store.results[0].ts_code).toBe('300750')
    })

    it('should handle empty results gracefully', async () => {
      mockedGetResults.mockResolvedValue([])

      const store = useSelectionStore()
      await store.fetchResults()

      expect(store.results).toEqual([])
    })

    it('should call API exactly once', async () => {
      mockedGetResults.mockResolvedValue([])

      const store = useSelectionStore()
      await store.fetchResults()

      expect(mockedGetResults).toHaveBeenCalledTimes(1)
    })

    it('should retain results when API throws (not clear on error)', async () => {
      const initialData = createMockRecords()
      mockedGetResults.mockResolvedValueOnce(initialData)

      const store = useSelectionStore()
      await store.fetchResults()
      expect(store.results).toHaveLength(2)

      mockedGetResults.mockRejectedValueOnce(new Error('Timeout'))
      await store.fetchResults().catch(() => {})

      // Results remain from the previous successful fetch (store doesn't clear on error)
      expect(store.results).toHaveLength(2)
    })

    it('should handle records with optional fields as null', async () => {
      const records: SelectionRecord[] = [
        {
          strategy_id: 'strat-2',
          ts_code: '000002',
          trade_date: '2026-01-15',
          rank: 1,
          composite_score: 90,
          status: 'halted',
          factor_snapshot: {},
          name: null,
          industry: null,
          close: null,
          pct_change: null,
        },
      ]
      mockedGetResults.mockResolvedValue(records)

      const store = useSelectionStore()
      await store.fetchResults()

      expect(store.results[0].name).toBeNull()
      expect(store.results[0].industry).toBeNull()
      expect(store.results[0].close).toBeNull()
    })

    it('should handle records with extra market data', async () => {
      const records: SelectionRecord[] = [
        {
          strategy_id: 'strat-1',
          ts_code: '600519',
          trade_date: '2026-01-15',
          rank: 1,
          composite_score: 95,
          status: 'active',
          factor_snapshot: { pe_ttm: 2.0 },
          close: 1800.5,
          pct_change: 2.35,
          pe_ttm: 35.2,
          pb: 12.1,
          roe_ttm: 30.5,
          market_cap: 2_260_000_000_000,
        },
      ]
      mockedGetResults.mockResolvedValue(records)

      const store = useSelectionStore()
      await store.fetchResults()

      expect(store.results[0].close).toBe(1800.5)
      expect(store.results[0].pct_change).toBe(2.35)
      expect(store.results[0].pe_ttm).toBe(35.2)
      expect(store.results[0].market_cap).toBe(2_260_000_000_000)
    })
  })

  describe('store independence', () => {
    it('should isolate state between store instances', async () => {
      mockedGetResults.mockResolvedValue(createMockRecords())

      const store1 = useSelectionStore()
      await store1.fetchResults('strat-1')

      // Reset pinia (simulates a new scope)
      setActivePinia(createPinia())
      const store2 = useSelectionStore()

      expect(store2.results).toEqual([])
      expect(store1.results).toHaveLength(2)
    })
  })
})
