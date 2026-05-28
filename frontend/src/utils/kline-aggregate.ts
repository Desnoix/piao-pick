import type { Kline } from '../types/stock'

export type KlinePeriod = 'daily' | 'weekly' | 'monthly'

/**
 * 按 ISO 周获取分组 key: "2025W03"
 * Get ISO week grouping key
 */
function getISOWeekKey(date: Date): string {
  const d = new Date(date)
  d.setHours(0, 0, 0, 0)
  d.setDate(d.getDate() + 3 - ((d.getDay() + 6) % 7))
  const week1 = new Date(d.getFullYear(), 0, 4)
  const weekNum =
    1 +
    Math.round(((d.getTime() - week1.getTime()) / 86400000 - 3 + ((week1.getDay() + 6) % 7)) / 7)
  return `${d.getFullYear()}W${String(weekNum).padStart(2, '0')}`
}

/**
 * 获取月份分组 key: "2025-01"
 * Get month grouping key
 */
function getMonthKey(date: Date): string {
  const d = new Date(date)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

/**
 * 将日线数据聚合为周K或月K
 * Aggregate daily klines into weekly or monthly candles
 *
 * OHLCV 聚合规则 / Aggregation rules:
 * - Open  = 组内第 1 根的 Open
 * - High  = 组内所有 High 的最大值
 * - Low   = 组内所有 Low 的最小值
 * - Close = 组内最后 1 根的 Close
 * - Volume = 组内所有 Volume 之和
 */
export function aggregateKlines(data: Kline[], period: KlinePeriod): Kline[] {
  if (period === 'daily' || data.length === 0) return data

  const getGroupKey = period === 'weekly' ? getISOWeekKey : getMonthKey

  const groups = new Map<string, Kline[]>()
  for (const k of data) {
    const key = getGroupKey(new Date(k.trade_date))
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key)!.push(k)
  }

  const result: Kline[] = []
  for (const [, candles] of groups) {
    const first = candles[0]
    const last = candles[candles.length - 1]
    result.push({
      ts_code: first.ts_code,
      trade_date: last.trade_date,
      open: first.open,
      high: Math.max(...candles.map((c) => c.high ?? 0)),
      low: Math.min(...candles.map((c) => c.low ?? Infinity)),
      close: last.close,
      volume: candles.reduce((sum, c) => sum + (c.volume ?? 0), 0),
      amount: candles.reduce((sum, c) => sum + (c.amount ?? 0), 0),
      pct_chg: last.pct_chg,
    })
  }
  return result
}
