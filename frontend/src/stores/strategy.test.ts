import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useStrategyStore } from './strategy'
import type { Strategy } from '../types/strategy'

// Mock API module
vi.mock('../api/strategies', () => ({
  listStrategies: vi.fn(),
  deleteStrategy: vi.fn(),
  updateStrategy: vi.fn(),
}))

import {
  listStrategies,
  deleteStrategy as apiDeleteStrategy,
  updateStrategy as apiUpdateStrategy,
} from '../api/strategies'

const mockedList = vi.mocked(listStrategies)
const mockedDelete = vi.mocked(apiDeleteStrategy)
const mockedUpdate = vi.mocked(apiUpdateStrategy)

function createMockStrategies(overrides?: Partial<Strategy>[]): Strategy[] {
  const defaults: Strategy[] = [
    {
      id: 'strat-1',
      name: 'value_lowvol',
      display_name: '价值低波',
      description: '低估值低波动策略',
      category: 'value',
      is_active: true,
      priority: 1,
    },
    {
      id: 'strat-2',
      name: 'momentum_growth',
      display_name: '动量成长',
      description: '动量趋势成长策略',
      category: 'momentum',
      is_active: false,
      priority: 2,
    },
    {
      id: 'strat-3',
      name: 'quality_blend',
      display_name: '质量均衡',
      description: '综合质量策略',
      category: 'quality',
      is_active: true,
      priority: 3,
    },
  ]
  if (!overrides) return defaults
  return defaults.map((d, i) => ({ ...d, ...(overrides[i] || {}) }))
}

describe('strategy store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('initial state', () => {
    it('should have empty strategies array', () => {
      const store = useStrategyStore()
      expect(store.strategies).toEqual([])
    })

    it('should have loading false', () => {
      const store = useStrategyStore()
      expect(store.loading).toBe(false)
    })

    it('should have empty activeStrategies computed', () => {
      const store = useStrategyStore()
      expect(store.activeStrategies).toEqual([])
    })
  })

  describe('fetchStrategies', () => {
    it('should fetch and store strategies', async () => {
      const mockData = createMockStrategies()
      mockedList.mockResolvedValue(mockData)

      const store = useStrategyStore()
      await store.fetchStrategies()

      expect(store.strategies).toEqual(mockData)
      expect(store.strategies).toHaveLength(3)
    })

    it('should set loading true during fetch', async () => {
      let resolvePromise: (val: Strategy[]) => void
      mockedList.mockImplementation(
        () =>
          new Promise<Strategy[]>((resolve) => {
            resolvePromise = resolve
          })
      )

      const store = useStrategyStore()
      const fetchPromise = store.fetchStrategies()

      expect(store.loading).toBe(true)
      resolvePromise!([])
      await fetchPromise
      expect(store.loading).toBe(false)
    })

    it('should reset loading to false after successful fetch', async () => {
      mockedList.mockResolvedValue([])

      const store = useStrategyStore()
      await store.fetchStrategies()

      expect(store.loading).toBe(false)
    })

    it('should reset loading to false after failed fetch', async () => {
      mockedList.mockRejectedValue(new Error('Server error'))

      const store = useStrategyStore()
      await store.fetchStrategies().catch(() => {})

      expect(store.loading).toBe(false)
    })

    it('should pass silent option to API', async () => {
      mockedList.mockResolvedValue([])

      const store = useStrategyStore()
      await store.fetchStrategies({ silent: true })

      expect(mockedList).toHaveBeenCalledWith({ silent: true })
    })

    it('should call API without options when none provided', async () => {
      mockedList.mockResolvedValue([])

      const store = useStrategyStore()
      await store.fetchStrategies()

      expect(mockedList).toHaveBeenCalledWith(undefined)
    })

    it('should call API exactly once', async () => {
      mockedList.mockResolvedValue([])

      const store = useStrategyStore()
      await store.fetchStrategies()

      expect(mockedList).toHaveBeenCalledTimes(1)
    })

    it('should replace previous strategies on new fetch', async () => {
      mockedList.mockResolvedValueOnce(createMockStrategies())

      const store = useStrategyStore()
      await store.fetchStrategies()
      expect(store.strategies).toHaveLength(3)

      mockedList.mockResolvedValueOnce([createMockStrategies()[0]])
      await store.fetchStrategies()

      expect(store.strategies).toHaveLength(1)
    })

    it('should handle empty strategies gracefully', async () => {
      mockedList.mockResolvedValue([])

      const store = useStrategyStore()
      await store.fetchStrategies()

      expect(store.strategies).toEqual([])
    })
  })

  describe('activeStrategies computed', () => {
    it('should filter only active strategies', async () => {
      mockedList.mockResolvedValue(createMockStrategies())

      const store = useStrategyStore()
      await store.fetchStrategies()

      expect(store.activeStrategies).toHaveLength(2)
      expect(store.activeStrategies.every((s) => s.is_active === true)).toBe(true)
    })

    it('should return empty array when no strategies are active', async () => {
      mockedList.mockResolvedValue(
        createMockStrategies([{ is_active: false }, { is_active: false }, { is_active: false }])
      )

      const store = useStrategyStore()
      await store.fetchStrategies()

      expect(store.activeStrategies).toEqual([])
    })

    it('should return all strategies when all are active', async () => {
      mockedList.mockResolvedValue(createMockStrategies([{ is_active: true }, { is_active: true }]))

      const store = useStrategyStore()
      await store.fetchStrategies()

      // 3 strategies total (2 overridden to true, 1 default true)
      expect(store.activeStrategies).toHaveLength(3)
    })

    it('should update when strategies are refetched', async () => {
      mockedList.mockResolvedValueOnce(createMockStrategies())

      const store = useStrategyStore()
      await store.fetchStrategies()
      expect(store.activeStrategies).toHaveLength(2)

      // Refetch with different data - all inactive
      mockedList.mockResolvedValueOnce(
        createMockStrategies([{ is_active: false }, { is_active: false }, { is_active: false }])
      )
      await store.fetchStrategies()

      expect(store.activeStrategies).toEqual([])
    })
  })

  describe('toggleStrategy', () => {
    it('should call API with correct id and is_active flag', async () => {
      mockedList.mockResolvedValue(createMockStrategies())
      mockedUpdate.mockResolvedValue({} as any)

      const store = useStrategyStore()
      await store.fetchStrategies()

      await store.toggleStrategy('strat-2', true)

      expect(mockedUpdate).toHaveBeenCalledWith('strat-2', { is_active: true })
    })

    it('should update is_active in store after toggling', async () => {
      mockedList.mockResolvedValue(createMockStrategies())
      mockedUpdate.mockResolvedValue({} as any)

      const store = useStrategyStore()
      await store.fetchStrategies()

      // strat-2 is initially inactive
      expect(store.strategies.find((s) => s.id === 'strat-2')?.is_active).toBe(false)

      await store.toggleStrategy('strat-2', true)

      expect(store.strategies.find((s) => s.id === 'strat-2')?.is_active).toBe(true)
    })

    it('should update activeStrategies when toggling inactive to active', async () => {
      mockedList.mockResolvedValue(createMockStrategies())
      mockedUpdate.mockResolvedValue({} as any)

      const store = useStrategyStore()
      await store.fetchStrategies()
      expect(store.activeStrategies).toHaveLength(2)

      await store.toggleStrategy('strat-2', true)

      expect(store.activeStrategies).toHaveLength(3)
    })

    it('should update activeStrategies when toggling active to inactive', async () => {
      mockedList.mockResolvedValue(createMockStrategies())
      mockedUpdate.mockResolvedValue({} as any)

      const store = useStrategyStore()
      await store.fetchStrategies()
      expect(store.activeStrategies).toHaveLength(2)

      await store.toggleStrategy('strat-1', false)

      expect(store.activeStrategies).toHaveLength(1)
    })

    it('should not modify store if strategy id not found', async () => {
      mockedList.mockResolvedValue(createMockStrategies())
      mockedUpdate.mockResolvedValue({} as any)

      const store = useStrategyStore()
      await store.fetchStrategies()
      const before = [...store.strategies]

      await store.toggleStrategy('nonexistent', false)

      expect(store.strategies).toEqual(before)
    })

    it('should propagate API errors', async () => {
      mockedList.mockResolvedValue(createMockStrategies())
      mockedUpdate.mockRejectedValue(new Error('Update failed'))

      const store = useStrategyStore()
      await store.fetchStrategies()

      await expect(store.toggleStrategy('strat-1', false)).rejects.toThrow('Update failed')
    })

    it('should not modify store state when API call fails', async () => {
      mockedList.mockResolvedValue(createMockStrategies())
      mockedUpdate.mockRejectedValue(new Error('Update failed'))

      const store = useStrategyStore()
      await store.fetchStrategies()

      try {
        await store.toggleStrategy('strat-2', true)
      } catch {
        // expected
      }

      // Store state unchanged
      expect(store.strategies.find((s) => s.id === 'strat-2')?.is_active).toBe(false)
    })
  })

  describe('removeStrategy', () => {
    it('should call API with correct id', async () => {
      mockedList.mockResolvedValue(createMockStrategies())
      mockedDelete.mockResolvedValue(undefined)

      const store = useStrategyStore()
      await store.fetchStrategies()

      await store.removeStrategy('strat-1')

      expect(mockedDelete).toHaveBeenCalledWith('strat-1')
    })

    it('should remove strategy from array', async () => {
      mockedList.mockResolvedValue(createMockStrategies())
      mockedDelete.mockResolvedValue(undefined)

      const store = useStrategyStore()
      await store.fetchStrategies()
      expect(store.strategies).toHaveLength(3)

      await store.removeStrategy('strat-2')

      expect(store.strategies).toHaveLength(2)
      expect(store.strategies.find((s) => s.id === 'strat-2')).toBeUndefined()
    })

    it('should update activeStrategies after removing an active strategy', async () => {
      mockedList.mockResolvedValue(createMockStrategies())
      mockedDelete.mockResolvedValue(undefined)

      const store = useStrategyStore()
      await store.fetchStrategies()
      expect(store.activeStrategies).toHaveLength(2) // strat-1, strat-3

      await store.removeStrategy('strat-1') // active strategy

      expect(store.activeStrategies).toHaveLength(1)
      expect(store.activeStrategies[0].id).toBe('strat-3')
    })

    it('should not affect activeStrategies when removing inactive strategy', async () => {
      mockedList.mockResolvedValue(createMockStrategies())
      mockedDelete.mockResolvedValue(undefined)

      const store = useStrategyStore()
      await store.fetchStrategies()
      expect(store.activeStrategies).toHaveLength(2)

      await store.removeStrategy('strat-2') // inactive strategy

      expect(store.activeStrategies).toHaveLength(2)
    })

    it('should handle removing nonexistent id gracefully', async () => {
      mockedList.mockResolvedValue(createMockStrategies())
      mockedDelete.mockResolvedValue(undefined)

      const store = useStrategyStore()
      await store.fetchStrategies()

      await store.removeStrategy('nonexistent')

      expect(store.strategies).toHaveLength(3) // unchanged
    })

    it('should propagate API errors', async () => {
      mockedList.mockResolvedValue(createMockStrategies())
      mockedDelete.mockRejectedValue(new Error('Delete failed'))

      const store = useStrategyStore()
      await store.fetchStrategies()

      await expect(store.removeStrategy('strat-1')).rejects.toThrow('Delete failed')
    })

    it('should not modify store state when delete API call fails', async () => {
      mockedList.mockResolvedValue(createMockStrategies())
      mockedDelete.mockRejectedValue(new Error('Delete failed'))

      const store = useStrategyStore()
      await store.fetchStrategies()

      try {
        await store.removeStrategy('strat-1')
      } catch {
        // expected
      }

      expect(store.strategies).toHaveLength(3)
      expect(store.strategies.find((s) => s.id === 'strat-1')).toBeDefined()
    })
  })

  describe('store independence', () => {
    it('should isolate state between store instances', async () => {
      mockedList.mockResolvedValue(createMockStrategies())

      const store1 = useStrategyStore()
      await store1.fetchStrategies()

      setActivePinia(createPinia())
      const store2 = useStrategyStore()

      expect(store2.strategies).toEqual([])
      expect(store1.strategies).toHaveLength(3)
    })
  })
})
