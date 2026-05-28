import type { Kline, FactorData } from '../types/stock'
import { FACTOR_LABELS } from './constants'

/**
 * 生成模拟K线数据（随机漫步）
 */
export function generateMockKline(
  days: number = 60,
  basePrice: number = 100,
  tsCode: string = '000000.SZ'
): Kline[] {
  const result: Kline[] = []
  let price = basePrice
  const now = new Date()

  for (let i = days - 1; i >= 0; i--) {
    const date = new Date(now)
    date.setDate(date.getDate() - i)
    // Skip weekends
    const dow = date.getDay()
    if (dow === 0 || dow === 6) continue

    const change = (Math.random() - 0.48) * price * 0.04
    const open = price
    const close = price + change
    const high = Math.max(open, close) + Math.random() * price * 0.015
    const low = Math.min(open, close) - Math.random() * price * 0.015
    const volume = Math.floor(50000 + Math.random() * 200000)
    const pct = ((close - open) / open) * 100

    const yyyy = date.getFullYear()
    const mm = String(date.getMonth() + 1).padStart(2, '0')
    const dd = String(date.getDate()).padStart(2, '0')

    result.push({
      ts_code: tsCode,
      trade_date: `${yyyy}-${mm}-${dd}`,
      open: parseFloat(open.toFixed(2)),
      high: parseFloat(high.toFixed(2)),
      low: parseFloat(low.toFixed(2)),
      close: parseFloat(close.toFixed(2)),
      volume,
      amount: parseFloat((volume * close).toFixed(2)),
      pct_chg: parseFloat(pct.toFixed(2)),
    })

    price = close
  }

  return result
}

/**
 * 获取所有因子 key
 */
export function getFactorKeys(): string[] {
  return Object.keys(FACTOR_LABELS)
}

/**
 * 生成模拟因子快照（Z-Score 范围, 近似 N(0, 0.8²)）
 */
export function generateMockFactorSnapshot(): Record<string, number> {
  const keys = getFactorKeys()
  const snapshot: Record<string, number> = {}
  for (const key of keys) {
    const u1 = Math.random(),
      u2 = Math.random()
    snapshot[key] = parseFloat(((u1 + u2 - 1) * 2).toFixed(2)) // ~N(0, 0.8²)
  }
  return snapshot
}

/**
 * 生成模拟因子历史数据（用于折线图）
 */
export function generateMockFactorHistory(
  quarters: number = 8,
  factorKeys?: string[]
): { dates: string[]; factors: Record<string, number[]> } {
  const keys = factorKeys ?? getFactorKeys()
  const now = new Date()
  const dates: string[] = []

  for (let i = quarters - 1; i >= 0; i--) {
    const d = new Date(now)
    d.setMonth(d.getMonth() - i * 3)
    const yyyy = d.getFullYear()
    const q = Math.floor(d.getMonth() / 3) + 1
    dates.push(`${yyyy}Q${q}`)
  }

  const factors: Record<string, number[]> = {}
  for (const key of keys) {
    const series: number[] = []
    let base = Math.random() * 60 + 20
    for (let i = 0; i < dates.length; i++) {
      base += (Math.random() - 0.5) * 15
      base = Math.max(5, Math.min(95, base))
      series.push(parseFloat(base.toFixed(1)))
    }
    factors[key] = series
  }

  return { dates, factors }
}

/**
 * 生成模拟财务趋势数据（营收增长/利润增长/毛利率，4季度）
 */
export function generateMockFinancialTrend(): {
  quarters: string[]
  revGrowth: number[]
  earGrowth: number[]
  grossMargin: number[]
} {
  const now = new Date()
  const quarters: string[] = []
  for (let i = 3; i >= 0; i--) {
    const d = new Date(now)
    d.setMonth(d.getMonth() - i * 3)
    const yyyy = d.getFullYear()
    const q = Math.floor(d.getMonth() / 3) + 1
    quarters.push(`${yyyy}Q${q}`)
  }

  const randAround = (center: number, spread: number) =>
    parseFloat((center + (Math.random() - 0.5) * spread).toFixed(2))

  return {
    quarters,
    revGrowth: quarters.map(() => randAround(12, 20)),
    earGrowth: quarters.map(() => randAround(8, 25)),
    grossMargin: quarters.map(() => randAround(35, 15)),
  }
}
