import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAppStore } from './app'

// Override the naive-ui mock from setup.ts to include darkTheme
vi.mock('naive-ui', () => ({
  darkTheme: { name: 'dark', common: {}, Button: {} },
}))

describe('app store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    // Reset document class list
    document.documentElement.classList.remove('dark')
    // Mock matchMedia
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: query.includes('dark'),
        media: query,
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('initial state', () => {
    it('should default isDark to true', () => {
      const store = useAppStore()
      expect(store.isDark).toBe(true)
    })

    it('should compute naiveTheme as darkTheme when isDark=true', () => {
      const store = useAppStore()
      // isDark defaults to true
      expect(store.naiveTheme).toBeTruthy()
      expect(store.naiveTheme).toHaveProperty('name', 'dark')
    })

    it('should compute naiveTheme as null when isDark=false', async () => {
      const store = useAppStore()
      // Toggle to light
      store.toggleTheme()
      expect(store.isDark).toBe(false)
      expect(store.naiveTheme).toBeNull()
    })
  })

  describe('initTheme', () => {
    it('should restore dark theme from localStorage', () => {
      localStorage.setItem('theme', 'dark')
      const store = useAppStore()
      store.initTheme()
      expect(store.isDark).toBe(true)
    })

    it('should restore light theme from localStorage', () => {
      localStorage.setItem('theme', 'light')
      const store = useAppStore()
      store.initTheme()
      expect(store.isDark).toBe(false)
    })

    it('should apply dark class to document when theme is dark', () => {
      localStorage.setItem('theme', 'dark')
      const store = useAppStore()
      store.initTheme()
      expect(document.documentElement.classList.contains('dark')).toBe(true)
    })

    it('should remove dark class from document when theme is light', () => {
      localStorage.setItem('theme', 'light')
      const store = useAppStore()
      store.initTheme()
      expect(document.documentElement.classList.contains('dark')).toBe(false)
    })

    it('should use system preference when no localStorage value', () => {
      // matchMedia mock returns matches=true for dark
      const store = useAppStore()
      store.initTheme()
      expect(store.isDark).toBe(true)
    })

    it('should use light when system preference is light', () => {
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        value: vi.fn().mockImplementation((query: string) => ({
          matches: false,
          media: query,
          onchange: null,
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          dispatchEvent: vi.fn(),
        })),
      })
      const store = useAppStore()
      store.initTheme()
      expect(store.isDark).toBe(false)
    })

    it('should ignore invalid localStorage values', () => {
      localStorage.setItem('theme', 'invalid')
      const store = useAppStore()
      store.initTheme()
      // Falls back to matchMedia (matches=true for dark in our mock)
      expect(store.isDark).toBe(true)
    })
  })

  describe('toggleTheme', () => {
    it('should toggle isDark from true to false', () => {
      const store = useAppStore()
      expect(store.isDark).toBe(true)
      store.toggleTheme()
      expect(store.isDark).toBe(false)
    })

    it('should toggle isDark from false to true', () => {
      const store = useAppStore()
      store.toggleTheme() // true → false
      store.toggleTheme() // false → true
      expect(store.isDark).toBe(true)
    })

    it('should persist theme to localStorage when toggling to dark', () => {
      // Start with light
      localStorage.setItem('theme', 'light')
      const store = useAppStore()
      store.initTheme()
      expect(store.isDark).toBe(false)
      store.toggleTheme()
      expect(localStorage.getItem('theme')).toBe('dark')
    })

    it('should persist theme to localStorage when toggling to light', () => {
      const store = useAppStore()
      store.toggleTheme()
      expect(localStorage.getItem('theme')).toBe('light')
    })

    it('should apply dark class when toggling to dark', () => {
      const store = useAppStore()
      store.toggleTheme() // dark → light
      expect(document.documentElement.classList.contains('dark')).toBe(false)
      store.toggleTheme() // light → dark
      expect(document.documentElement.classList.contains('dark')).toBe(true)
    })

    it('should update naiveTheme reactively after toggle', () => {
      const store = useAppStore()
      expect(store.naiveTheme).toHaveProperty('name', 'dark')
      store.toggleTheme()
      expect(store.naiveTheme).toBeNull()
      store.toggleTheme()
      expect(store.naiveTheme).toHaveProperty('name', 'dark')
    })
  })
})
