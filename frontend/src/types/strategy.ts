export interface Strategy {
  id: string
  name?: string | null
  display_name?: string | null
  description?: string | null
  category?: string | null
  is_active: boolean
  priority: number
}

export interface StrategyDetail extends Strategy {
  config: string
}

export interface StrategyCreateRequest {
  name: string
  display_name?: string | null
  description?: string | null
  category?: string | null
  config: string
  is_active?: boolean
  priority?: number
}

export interface StrategyUpdateRequest {
  display_name?: string | null
  description?: string | null
  category?: string | null
  config?: string | null
  is_active?: boolean | null
  priority?: number | null
}

export type StrategyCategory = 'value' | 'momentum' | 'quality' | 'growth' | 'blended'

export interface FactorWeight {
  id: string
  weight: number
  direction: 'positive' | 'negative'
  enabled: boolean
}

export interface UniverseConfig {
  exclude_st: boolean
  exclude_new_listing_days: number
  exclude_suspended: boolean
  exclude_bse: boolean
  min_market_cap: number
  min_daily_amount: number
}

export interface FilterRule {
  type: string
  value?: number
  max_per_industry?: number
  [key: string]: unknown
}

export interface OutputConfig {
  max_stocks: number
  sort_by: string
  sort_order: 'asc' | 'desc'
}

export interface StrategyConfig {
  name: string
  display_name: string
  description: string
  category: StrategyCategory
  version: string
  default_active: boolean
  default_priority: number
  universe: UniverseConfig
  factors: FactorWeight[]
  filters: FilterRule[]
  output: OutputConfig
}

export interface NavSeries {
  name: string
  dates: string[]
  values: number[]
  color?: string
}

export interface CompareMetrics {
  strategy_id: string
  display_name: string
  annual_return: number
  sharpe_ratio: number
  max_drawdown: number
  calmar_ratio: number
  win_rate: number
  avg_turnover: number
}
