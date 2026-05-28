/**
 * 格式化价格
 * @example formatPrice(1680) => "1680.00"
 */
export function formatPrice(price: number | null | undefined): string {
  if (price === null || price === undefined) return '-'
  return price.toFixed(2)
}

/**
 * 格式化百分比（A股：正红负绿）
 * @example formatPct(1.25) => "+1.25%"
 * @example formatPct(-0.85) => "-0.85%"
 */
export function formatPct(pct: number | null | undefined): string {
  if (pct === null || pct === undefined) return '-'
  const sign = pct > 0 ? '+' : ''
  return `${sign}${pct.toFixed(2)}%`
}

/**
 * 获取涨跌颜色 class
 * @returns "text-up" | "text-down" | ""
 */
export function getPctColor(pct: number | null | undefined): string {
  if (pct === null || pct === undefined) return ''
  if (pct > 0) return 'text-up'
  if (pct < 0) return 'text-down'
  return ''
}

/**
 * 格式化金额（亿/万）
 * @example formatAmount(123000000) => "1.23亿"
 * @example formatAmount(5000000) => "500万"
 */
export function formatAmount(amount: number | null | undefined): string {
  if (amount === null || amount === undefined) return '-'
  const abs = Math.abs(amount)
  if (abs >= 100000000) {
    return `${(amount / 100000000).toFixed(2)}亿`
  }
  if (abs >= 10000) {
    return `${(amount / 10000).toFixed(0)}万`
  }
  return amount.toFixed(2)
}

/**
 * 格式化市值
 * @example formatMarketCap(211000000000) => "21100.0亿"
 */
export function formatMarketCap(amount: number | null | undefined): string {
  if (amount === null || amount === undefined) return '-'
  const yi = amount / 100000000
  return `${yi.toFixed(1)}亿`
}

/**
 * 格式化数值（保留2位小数）
 */
export function formatNumber(num: number | null | undefined, decimals = 2): string {
  if (num === null || num === undefined) return '-'
  return num.toFixed(decimals)
}

/**
 * 格式化 Z-Score 值, 带正号前缀
 * @example formatZScore(1.85) => "+1.85"
 * @example formatZScore(-0.32) => "-0.32"
 */
export function formatZScore(z: number | null | undefined): string {
  if (z === null || z === undefined) return '-'
  const sign = z > 0 ? '+' : ''
  return `${sign}${z.toFixed(2)}`
}

/**
 * Z-Score 颜色: >0.5 红(涨), <-0.5 绿(跌), 其余无色
 */
export function getZScoreColor(z: number | null | undefined): string {
  if (z === null || z === undefined) return ''
  if (z > 0.5) return 'text-up'
  if (z < -0.5) return 'text-down'
  return ''
}

/**
 * Z-Score → 百分位 (用于可视化组件)
 * 近似: P ≈ 50 + 50·tanh(0.7988·z)
 * @example zScoreToPercentile(0) => 50, (1) => ~76, (2) => ~92
 */
export function zScoreToPercentile(z: number): number {
  return Math.round(50 + 50 * Math.tanh(0.7988 * z))
}
