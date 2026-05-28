/**
 * Time-series alignment utility for strategy NAV comparison.
 * 策略净值时间轴对齐工具 — 将不同起止日期的净值序列对齐到统一的月频网格。
 *
 * Algorithm:
 *   1. Compute intersection range [max(min dates), min(max dates)]
 *   2. Generate monthly grid (end-of-month) within intersection
 *   3. Forward-fill each series onto grid points
 */

export interface RawNav {
  name: string
  points: [string, number][] // [YYYY-MM-DD, nav], ascending order
  color?: string
}

export interface AlignedResult {
  dates: string[]
  series: { name: string; values: number[]; color?: string }[]
  coverage: { name: string; startDate: string; endDate: string }[]
}

/**
 * Align multiple NAV series onto a shared monthly grid using forward-fill.
 * 将多条净值序列对齐到共享月频网格，使用前向填充。
 */
export function alignNavSeries(inputs: RawNav[]): AlignedResult {
  if (inputs.length === 0) return { dates: [], series: [], coverage: [] }

  const parsed = inputs.map((inp) => ({
    ...inp,
    points: inp.points.map(([d, v]) => [new Date(d + 'T00:00:00'), v] as [Date, number]),
  }))

  // Intersection range — only period where ALL series have data
  const rangeStart = new Date(Math.max(...parsed.map((p) => p.points[0][0].getTime())))
  const rangeEnd = new Date(
    Math.min(...parsed.map((p) => p.points[p.points.length - 1][0].getTime()))
  )
  if (rangeStart > rangeEnd) return { dates: [], series: [], coverage: [] }

  // Monthly grid (end-of-month dates within intersection)
  const grid: Date[] = []
  const cursor = new Date(rangeStart.getFullYear(), rangeStart.getMonth(), 1)
  while (cursor <= rangeEnd) {
    const endOfMonth = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0)
    if (endOfMonth >= rangeStart && endOfMonth <= rangeEnd) grid.push(endOfMonth)
    cursor.setMonth(cursor.getMonth() + 1)
  }

  if (grid.length === 0) return { dates: [], series: [], coverage: [] }

  // Forward-fill: for each grid point, find the most recent NAV value
  const series = parsed.map((p) => {
    const values: number[] = []
    let ptr = 0
    for (const gd of grid) {
      while (ptr + 1 < p.points.length && p.points[ptr + 1][0].getTime() <= gd.getTime()) {
        ptr++
      }
      values.push(p.points[ptr][0].getTime() <= gd.getTime() ? p.points[ptr][1] : NaN)
    }
    return { name: p.name, values, color: p.color }
  })

  const dates = grid.map((d) => fmt(d))
  const coverage = parsed.map((p) => ({
    name: p.name,
    startDate: fmt(p.points[0][0]),
    endDate: fmt(p.points[p.points.length - 1][0]),
  }))

  return { dates, series, coverage }
}

/**
 * Compute element-wise NAV difference: target - base.
 * 计算逐点净值差值: 目标 - 基准。
 */
export function computeNavDifference(baseNav: number[], targetNav: number[]): number[] {
  return targetNav.map((v, i) =>
    isNaN(v) || isNaN(baseNav[i]) ? NaN : parseFloat((v - baseNav[i]).toFixed(4))
  )
}

/**
 * Filter aligned series by time range (1Y / 3Y / 5Y / ALL).
 * 按时间范围筛选对齐后的序列。
 */
export function filterByTimeRange(
  dates: string[],
  series: { name: string; values: number[]; color?: string }[],
  range: '1Y' | '3Y' | '5Y' | 'ALL'
): AlignedResult {
  if (range === 'ALL' || dates.length === 0) {
    return {
      dates,
      series,
      coverage: series.map((s) => ({
        name: s.name,
        startDate: dates[0] || '',
        endDate: dates[dates.length - 1] || '',
      })),
    }
  }

  const years = parseInt(range)
  const cutoff = new Date()
  cutoff.setFullYear(cutoff.getFullYear() - years)
  const cutoffStr = fmt(cutoff)

  const idx = dates.findIndex((d) => d >= cutoffStr)
  if (idx < 0) return { dates, series, coverage: [] }

  const sD = dates.slice(idx)
  const sS = series.map((s) => ({ ...s, values: s.values.slice(idx) }))

  return {
    dates: sD,
    series: sS,
    coverage: sS.map((s) => ({
      name: s.name,
      startDate: sD[0],
      endDate: sD[sD.length - 1],
    })),
  }
}

function fmt(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
