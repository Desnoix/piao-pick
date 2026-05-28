/**
 * CSV 导出工具函数
 * CSV export utility for selection results
 */

interface CsvColumn {
  key: string
  title: string
  formatter?: (value: any) => string
}

/**
 * 导出数组为 CSV 文件 (UTF-8 with BOM, Excel 兼容)
 * @param data - 数据数组
 * @param columns - 列配置 (key + title + 可选 formatter)
 * @param filename - 文件名 (不含扩展名)
 */
export function exportToCsv(data: any[], columns: CsvColumn[], filename: string): void {
  // UTF-8 BOM for Excel compatibility
  const BOM = '\uFEFF'

  // 表头
  const header = columns.map((col) => col.title).join(',')

  // 数据行
  const rows = data.map((item) =>
    columns
      .map((col) => {
        const value = item[col.key]
        const formatted = col.formatter ? col.formatter(value) : value
        // CSV 转义: 包含逗号、引号、换行的字段用双引号包裹
        const escaped = String(formatted ?? '').replace(/"/g, '""')
        return /[,"\n\r]/.test(escaped) ? `"${escaped}"` : escaped
      })
      .join(',')
  )

  // 拼接完整 CSV 内容
  const csvContent = BOM + header + '\n' + rows.join('\n')

  // 触发下载
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  const url = URL.createObjectURL(blob)
  link.setAttribute('href', url)
  link.setAttribute('download', `${filename}.csv`)
  link.style.visibility = 'hidden'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

/**
 * 导出选股结果为 CSV
 */
export function exportSelectionResults(
  results: any[],
  strategyName: string,
  tradeDate: string
): void {
  const columns: CsvColumn[] = [
    { key: 'rank', title: '排名' },
    { key: 'ts_code', title: '代码' },
    { key: 'name', title: '名称' },
    { key: 'industry', title: '行业' },
    {
      key: 'close',
      title: '最新价',
      formatter: (v) => (v !== null && v !== undefined ? v.toFixed(2) : ''),
    },
    {
      key: 'pct_change',
      title: '涨跌幅(%)',
      formatter: (v) => (v !== null && v !== undefined ? v.toFixed(2) : ''),
    },
    {
      key: 'pe_ttm',
      title: 'PE(TTM)',
      formatter: (v) => (v !== null && v !== undefined ? v.toFixed(2) : ''),
    },
    {
      key: 'pb',
      title: 'PB',
      formatter: (v) => (v !== null && v !== undefined ? v.toFixed(2) : ''),
    },
    {
      key: 'market_cap',
      title: '总市值(亿)',
      formatter: (v) => (v !== null && v !== undefined ? (v / 100000000).toFixed(2) : ''),
    },
    {
      key: 'composite_score',
      title: '综合评分',
      formatter: (v) => v.toFixed(2),
    },
    { key: 'trade_date', title: '选股日期' },
    { key: 'status', title: '状态' },
  ]

  const safeDate = tradeDate.replace(/-/g, '')
  const safeName = strategyName.replace(/[^a-zA-Z0-9一-龥]/g, '_')
  const filename = `选股结果_${safeName}_${safeDate}`

  exportToCsv(results, columns, filename)
}
