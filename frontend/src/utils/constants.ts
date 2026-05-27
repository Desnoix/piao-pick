/** 颜色常量 */
export const COLORS = {
  primary: '#3B82F6',
  up: '#EF4444',
  down: '#22C55E',
  neutral: '#A1A1AA',
} as const

/** 因子名称映射 */
export const FACTOR_LABELS: Record<string, string> = {
  pe_ttm: 'PE TTM',
  pb: 'PB',
  ps_ttm: 'PS TTM',
  fcf_yield: 'FCF率',
  ret_20d: '20日动量',
  ret_60d_vol: '60日波动',
  turnover_20d: '20日换手',
  roe_ttm: 'ROE TTM',
  gross_margin: '毛利率',
  rev_growth_yoy: '营收增长',
  ear_growth_yoy: '利润增长',
  ln_market_cap: '对数市值',
  inst_holding_chg: '机构持仓',
} as const

/** 因子类别 */
export const FACTOR_CATEGORIES = {
  value: ['pe_ttm', 'pb', 'ps_ttm', 'fcf_yield'],
  momentum: ['ret_20d', 'ret_60d_vol', 'turnover_20d'],
  quality: ['roe_ttm', 'gross_margin', 'rev_growth_yoy', 'ear_growth_yoy'],
  size: ['ln_market_cap', 'inst_holding_chg'],
} as const
