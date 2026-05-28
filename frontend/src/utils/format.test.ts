import { describe, it, expect } from 'vitest'
import {
  formatPrice,
  formatPct,
  getPctColor,
  formatAmount,
  formatMarketCap,
  formatNumber,
  formatZScore,
  getZScoreColor,
  zScoreToPercentile,
} from './format'

// ─── formatPrice ──────────────────────────────────────────
describe('formatPrice', () => {
  it('formats positive number to 2 decimals', () => {
    expect(formatPrice(1680)).toBe('1680.00')
  })

  it('formats decimal number correctly', () => {
    expect(formatPrice(123.456)).toBe('123.46')
  })

  it('formats zero', () => {
    expect(formatPrice(0)).toBe('0.00')
  })

  it('formats negative number', () => {
    expect(formatPrice(-123.45)).toBe('-123.45')
  })

  it('returns dash for null', () => {
    expect(formatPrice(null)).toBe('-')
  })

  it('returns dash for undefined', () => {
    expect(formatPrice(undefined)).toBe('-')
  })
})

// ─── formatPct ────────────────────────────────────────────
describe('formatPct', () => {
  it('formats positive with + prefix and % suffix', () => {
    expect(formatPct(1.25)).toBe('+1.25%')
  })

  it('formats negative with - sign', () => {
    expect(formatPct(-0.85)).toBe('-0.85%')
  })

  it('formats zero without sign prefix', () => {
    expect(formatPct(0)).toBe('0.00%')
  })

  it('formats large positive value', () => {
    expect(formatPct(10.567)).toBe('+10.57%')
  })

  it('returns dash for null', () => {
    expect(formatPct(null)).toBe('-')
  })

  it('returns dash for undefined', () => {
    expect(formatPct(undefined)).toBe('-')
  })
})

// ─── getPctColor ──────────────────────────────────────────
describe('getPctColor', () => {
  it('returns text-up for positive', () => {
    expect(getPctColor(1.5)).toBe('text-up')
  })

  it('returns text-down for negative', () => {
    expect(getPctColor(-0.5)).toBe('text-down')
  })

  it('returns empty string for zero', () => {
    expect(getPctColor(0)).toBe('')
  })

  it('returns empty string for null', () => {
    expect(getPctColor(null)).toBe('')
  })

  it('returns empty string for undefined', () => {
    expect(getPctColor(undefined)).toBe('')
  })
})

// ─── formatAmount ─────────────────────────────────────────
describe('formatAmount', () => {
  it('formats value >= 1亿 with 亿 suffix', () => {
    expect(formatAmount(123000000)).toBe('1.23亿')
  })

  it('formats value >= 1万 with 万 suffix', () => {
    expect(formatAmount(5000000)).toBe('500万')
  })

  it('formats small number without suffix', () => {
    expect(formatAmount(9999)).toBe('9999.00')
  })

  it('formats zero', () => {
    expect(formatAmount(0)).toBe('0.00')
  })

  it('handles negative 亿 value', () => {
    expect(formatAmount(-200000000)).toBe('-2.00亿')
  })

  it('handles negative 万 value', () => {
    expect(formatAmount(-50000)).toBe('-5万')
  })

  it('returns dash for null', () => {
    expect(formatAmount(null)).toBe('-')
  })

  it('returns dash for undefined', () => {
    expect(formatAmount(undefined)).toBe('-')
  })
})

// ─── formatMarketCap ──────────────────────────────────────
describe('formatMarketCap', () => {
  it('formats large market cap to 亿 with 1 decimal', () => {
    expect(formatMarketCap(211000000000)).toBe('2110.0亿')
  })

  it('formats smaller cap', () => {
    expect(formatMarketCap(500000000)).toBe('5.0亿')
  })

  it('formats zero', () => {
    expect(formatMarketCap(0)).toBe('0.0亿')
  })

  it('returns dash for null', () => {
    expect(formatMarketCap(null)).toBe('-')
  })

  it('returns dash for undefined', () => {
    expect(formatMarketCap(undefined)).toBe('-')
  })
})

// ─── formatNumber ─────────────────────────────────────────
describe('formatNumber', () => {
  it('formats with default 2 decimals', () => {
    expect(formatNumber(123.456)).toBe('123.46')
  })

  it('formats with custom 0 decimals', () => {
    expect(formatNumber(123.456, 0)).toBe('123')
  })

  it('formats with custom 4 decimals', () => {
    expect(formatNumber(3.14159, 4)).toBe('3.1416')
  })

  it('formats zero', () => {
    expect(formatNumber(0)).toBe('0.00')
  })

  it('returns dash for null', () => {
    expect(formatNumber(null)).toBe('-')
  })

  it('returns dash for undefined', () => {
    expect(formatNumber(undefined)).toBe('-')
  })
})

// ─── formatZScore ─────────────────────────────────────────
describe('formatZScore', () => {
  it('formats positive with + prefix', () => {
    expect(formatZScore(1.85)).toBe('+1.85')
  })

  it('formats negative', () => {
    expect(formatZScore(-0.32)).toBe('-0.32')
  })

  it('formats zero without sign prefix', () => {
    expect(formatZScore(0)).toBe('0.00')
  })

  it('returns dash for null', () => {
    expect(formatZScore(null)).toBe('-')
  })

  it('returns dash for undefined', () => {
    expect(formatZScore(undefined)).toBe('-')
  })
})

// ─── getZScoreColor ───────────────────────────────────────
describe('getZScoreColor', () => {
  it('returns text-up for z > 0.5', () => {
    expect(getZScoreColor(1.0)).toBe('text-up')
  })

  it('returns text-down for z < -0.5', () => {
    expect(getZScoreColor(-1.0)).toBe('text-down')
  })

  it('returns empty string for z exactly 0.5 (boundary)', () => {
    expect(getZScoreColor(0.5)).toBe('')
  })

  it('returns empty string for z exactly -0.5 (boundary)', () => {
    expect(getZScoreColor(-0.5)).toBe('')
  })

  it('returns empty string for z = 0 (neutral)', () => {
    expect(getZScoreColor(0)).toBe('')
  })

  it('returns empty string for null', () => {
    expect(getZScoreColor(null)).toBe('')
  })

  it('returns empty string for undefined', () => {
    expect(getZScoreColor(undefined)).toBe('')
  })
})

// ─── zScoreToPercentile ───────────────────────────────────
describe('zScoreToPercentile', () => {
  it('maps z=0 to ~50 (median)', () => {
    expect(zScoreToPercentile(0)).toBe(50)
  })

  it('maps z=1 to ~83', () => {
    expect(zScoreToPercentile(1)).toBe(83)
  })

  it('maps z=2 to ~96', () => {
    expect(zScoreToPercentile(2)).toBe(96)
  })

  it('maps z=-1 to ~17 (symmetric)', () => {
    expect(zScoreToPercentile(-1)).toBe(17)
  })

  it('returns value in [0, 100] range', () => {
    for (const z of [-5, -2, -1, 0, 1, 2, 5]) {
      const p = zScoreToPercentile(z)
      expect(p).toBeGreaterThanOrEqual(0)
      expect(p).toBeLessThanOrEqual(100)
    }
  })
})
