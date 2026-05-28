/**
 * Unit tests for src/api/request-guard.ts
 * Tests createRequestGuard's abortPrevious, signal, and abort behavior.
 *
 * Mock strategy: None needed – uses real AbortController (available in jsdom / Node 16+).
 */
import { describe, it, expect, vi } from 'vitest'
import { createRequestGuard } from './request-guard'

describe('createRequestGuard', () => {
  /* ---------- factory ---------- */

  it('should return an object with abortPrevious, signal, and abort', () => {
    const guard = createRequestGuard()
    expect(typeof guard.abortPrevious).toBe('function')
    expect(typeof guard.abort).toBe('function')
    // signal is a getter – initially undefined
    expect(guard).toHaveProperty('signal')
  })

  /* ---------- signal ---------- */

  describe('signal', () => {
    it('should be undefined before abortPrevious is called', () => {
      const guard = createRequestGuard()
      expect(guard.signal).toBeUndefined()
    })

    it('should return an AbortSignal after abortPrevious', () => {
      const guard = createRequestGuard()
      guard.abortPrevious()
      expect(guard.signal).toBeDefined()
      expect(guard.signal!.aborted).toBe(false)
    })
  })

  /* ---------- abortPrevious ---------- */

  describe('abortPrevious', () => {
    it('should create a new AbortController', () => {
      const guard = createRequestGuard()
      guard.abortPrevious()
      expect(guard.signal).toBeInstanceOf(AbortSignal)
    })

    it('should abort the previous signal on second call', () => {
      const guard = createRequestGuard()
      guard.abortPrevious()
      const firstSignal = guard.signal!

      guard.abortPrevious()

      expect(firstSignal.aborted).toBe(true)
      expect(guard.signal).not.toBe(firstSignal)
      expect(guard.signal!.aborted).toBe(false)
    })

    it('should produce independent signals on successive calls', () => {
      const guard = createRequestGuard()
      const signals: AbortSignal[] = []

      for (let i = 0; i < 5; i++) {
        guard.abortPrevious()
        signals.push(guard.signal!)
      }

      // All but the last should be aborted
      for (let i = 0; i < 4; i++) {
        expect(signals[i].aborted).toBe(true)
      }
      expect(signals[4].aborted).toBe(false)
    })

    it('should allow attaching onabort listener to signal', () => {
      const guard = createRequestGuard()
      guard.abortPrevious()
      const onabort = vi.fn()
      guard.signal!.onabort = onabort

      guard.abortPrevious() // triggers abort on previous

      expect(onabort).toHaveBeenCalledTimes(1)
    })
  })

  /* ---------- abort ---------- */

  describe('abort', () => {
    it('should abort the current signal', () => {
      const guard = createRequestGuard()
      guard.abortPrevious()

      expect(guard.signal!.aborted).toBe(false)
      guard.abort()
      expect(guard.signal).toBeUndefined()
    })

    it('should set signal to undefined after abort', () => {
      const guard = createRequestGuard()
      guard.abortPrevious()
      guard.abort()
      expect(guard.signal).toBeUndefined()
    })

    it('should be safe to call abort when no controller exists', () => {
      const guard = createRequestGuard()
      expect(() => guard.abort()).not.toThrow()
    })

    it('should abort current and allow fresh start', () => {
      const guard = createRequestGuard()
      guard.abortPrevious()
      const firstSignal = guard.signal!

      guard.abort()
      expect(firstSignal.aborted).toBe(true)
      expect(guard.signal).toBeUndefined()

      // Can start fresh
      guard.abortPrevious()
      expect(guard.signal).toBeDefined()
      expect(guard.signal!.aborted).toBe(false)
    })

    it('should trigger onabort callback on the aborted signal', () => {
      const guard = createRequestGuard()
      guard.abortPrevious()
      const onabort = vi.fn()
      guard.signal!.onabort = onabort

      guard.abort()

      expect(onabort).toHaveBeenCalledTimes(1)
    })
  })

  /* ---------- real-world usage pattern ---------- */

  describe('integration: fetch-like usage', () => {
    it('should cancel a pending fetch when abortPrevious is called again', async () => {
      const guard = createRequestGuard()

      // Simulate first click
      guard.abortPrevious()
      const signal1 = guard.signal!

      // Simulate second click before first completes
      guard.abortPrevious()
      const signal2 = guard.signal!

      expect(signal1.aborted).toBe(true)
      expect(signal2.aborted).toBe(false)

      // Simulate cleanup after response
      guard.abort()
      expect(signal2!.aborted).toBe(true)
    })

    it('should work with AbortSignal event listeners', () => {
      const guard = createRequestGuard()
      guard.abortPrevious()

      const listener = vi.fn()
      guard.signal!.addEventListener('abort', listener)

      guard.abort()

      expect(listener).toHaveBeenCalledTimes(1)
    })

    it('should support addEventListener with AbortController reason', () => {
      const guard = createRequestGuard()
      guard.abortPrevious()

      let capturedReason: any
      guard.signal!.addEventListener('abort', () => {
        capturedReason = guard.signal
      })

      guard.abortPrevious()
      expect(capturedReason).toBeDefined()
    })
  })
})
