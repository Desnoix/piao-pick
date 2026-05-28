import { describe, it, expect } from 'vitest'
import { COLORS, FACTOR_LABELS, FACTOR_CATEGORIES } from './constants'

// ─── COLORS ───────────────────────────────────────────────
describe('COLORS', () => {
  it('has all required color keys', () => {
    expect(COLORS).toHaveProperty('primary')
    expect(COLORS).toHaveProperty('up')
    expect(COLORS).toHaveProperty('down')
    expect(COLORS).toHaveProperty('neutral')
  })

  it('up is red (A股 convention)', () => {
    expect(COLORS.up).toBe('#EF4444')
  })

  it('down is green (A股 convention)', () => {
    expect(COLORS.down).toBe('#22C55E')
  })

  it('all values are valid hex color strings', () => {
    const hexRegex = /^#[0-9A-Fa-f]{6}$/
    for (const value of Object.values(COLORS)) {
      expect(value).toMatch(hexRegex)
    }
  })
})

// ─── FACTOR_LABELS ────────────────────────────────────────
describe('FACTOR_LABELS', () => {
  it('has all 13 expected factor keys', () => {
    const keys = Object.keys(FACTOR_LABELS)
    expect(keys).toHaveLength(13)
  })

  it('maps pe_ttm to PE TTM', () => {
    expect(FACTOR_LABELS['pe_ttm']).toBe('PE TTM')
  })

  it('maps ret_20d to 20日动量', () => {
    expect(FACTOR_LABELS['ret_20d']).toBe('20日动量')
  })

  it('all values are non-empty strings', () => {
    for (const value of Object.values(FACTOR_LABELS)) {
      expect(typeof value).toBe('string')
      expect(value.length).toBeGreaterThan(0)
    }
  })
})

// ─── FACTOR_CATEGORIES ────────────────────────────────────
describe('FACTOR_CATEGORIES', () => {
  it('has value, momentum, quality, size categories', () => {
    expect(FACTOR_CATEGORIES).toHaveProperty('value')
    expect(FACTOR_CATEGORIES).toHaveProperty('momentum')
    expect(FACTOR_CATEGORIES).toHaveProperty('quality')
    expect(FACTOR_CATEGORIES).toHaveProperty('size')
  })

  it('value category contains pe_ttm', () => {
    expect(FACTOR_CATEGORIES.value).toContain('pe_ttm')
  })

  it('all category factor IDs exist in FACTOR_LABELS', () => {
    const allCategoryFactors = Object.values(FACTOR_CATEGORIES).flat()
    const labelKeys = Object.keys(FACTOR_LABELS)
    for (const factor of allCategoryFactors) {
      expect(labelKeys).toContain(factor)
    }
  })

  it('total factors across categories equals FACTOR_LABELS count', () => {
    const totalFactorIds = Object.values(FACTOR_CATEGORIES).flat().length
    const labelCount = Object.keys(FACTOR_LABELS).length
    expect(totalFactorIds).toBe(labelCount)
  })
})
