export interface BacktestRunRequest {
  strategy_id: string
  start_date: string
  end_date: string
  initial_capital?: number
  commission_rate?: number
  slippage?: number
}

export interface BacktestPeriod {
  start: string
  end: string
  rebalance_count: number
}

export interface BacktestMetrics {
  total_return: number
  annual_return: number
  annual_volatility: number
  sharpe_ratio: number
  max_drawdown: number
  calmar_ratio: number
  monthly_win_rate: number
  avg_turnover?: number
  // 基准对比指标
  benchmark_total_return?: number
  excess_return?: number
  tracking_error?: number
  information_ratio?: number
  alpha?: number
  beta?: number
}

export interface BacktestRunResponse {
  strategy_name: string
  start_date: string
  end_date: string
  period: BacktestPeriod
  metrics: BacktestMetrics
  nav_series: [string, number][]
  benchmark_nav?: [string, number][] // 归一化后的沪深 300 净值
  returns: number[]
  turnover_history: number[]
}

export interface AvailableDates {
  start_date: string | null
  end_date: string | null
  trade_date_count: number
}

/** @deprecated use BacktestRunResponse */
export interface BacktestResult {
  strategy_id: string
  start_date: string
  end_date: string
  total_return?: number | null
  annual_return?: number | null
  max_drawdown?: number | null
  sharpe_ratio?: number | null
  win_rate?: number | null
  trade_count: number
}
