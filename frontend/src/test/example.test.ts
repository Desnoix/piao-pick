import { describe, it, expect } from 'vitest'
import { ref, computed } from 'vue'

describe('Vitest setup verification', () => {
  it('should work with Vue composables', () => {
    const count = ref(0)
    const doubled = computed(() => count.value * 2)

    expect(doubled.value).toBe(0)
    count.value = 5
    expect(doubled.value).toBe(10)
  })

  it('should work with basic assertions', () => {
    expect(1 + 1).toBe(2)
  })

  it('should have jsdom environment', () => {
    expect(typeof window).toBe('object')
    expect(typeof document).toBe('object')
  })

  it('should have IntersectionObserver mock available', () => {
    const observer = new IntersectionObserver(() => {})
    expect(observer.observe).toBeDefined()
    expect(observer.disconnect).toBeDefined()
  })
})
