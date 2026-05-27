export interface StockScore {
  rank: number
  ts_code: string
  name?: string | null
  industry?: string | null
  composite_score: number
  status: string
  close?: number | null
  pct_change?: number | null
  pe_ttm?: number | null
  pb?: number | null
  roe_ttm?: number | null
  market_cap?: number | null
  factor_snapshot: Record<string, number>
}

export interface SelectionResult {
  trade_date: string
  strategy_name: string
  universe_count: number
  filtered_count: number
  candidate_count: number
  final_count: number
  results: StockScore[]
}

export interface SelectionRunRequest {
  strategy_id?: string | null
  trade_date?: string | null
}

export interface SelectionRecord {
  strategy_id: string
  ts_code: string
  trade_date: string
  rank: number
  composite_score: number
  status: string
  factor_snapshot: Record<string, number>
  created_at?: string | null
}
