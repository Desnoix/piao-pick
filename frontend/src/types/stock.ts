export interface StockInfo {
  ts_code: string
  name?: string | null
  industry?: string | null
  list_date?: string | null
  is_st: boolean
  is_suspended: boolean
}

export interface Kline {
  ts_code: string
  trade_date: string
  open?: number | null
  high?: number | null
  low?: number | null
  close?: number | null
  volume?: number | null
  amount?: number | null
  close_adj?: number | null
  pct_chg?: number | null
}

export interface FactorData {
  ts_code: string
  trade_date: string
  pe_ttm?: number | null
  pb?: number | null
  ps_ttm?: number | null
  fcf_yield?: number | null
  ret_20d?: number | null
  ret_60d_vol?: number | null
  turnover_20d?: number | null
  roe_ttm?: number | null
  gross_margin?: number | null
  rev_growth_yoy?: number | null
  ear_growth_yoy?: number | null
  ln_market_cap?: number | null
  inst_holding_chg?: number | null
}
