export interface PaginatedResponse<T> {
  total: number
  offset: number
  limit: number
  items: T[]
}

export interface DataStatus {
  db_path: string
  db_size_mb?: number | null
  stock_count: number
  latest_kline_date?: string | null
  latest_factor_date?: string | null
}

export interface TradeCalendar {
  start_date: string
  end_date: string
  trading_days: string[]
  count: number
}

export interface SyncRequest {
  trade_date?: string | null
  stock_codes?: string[] | null
}

export interface SyncResponse {
  success: boolean
  message: string
  trade_date?: string | null
  synced_count: number
  failed_count: number
  errors: string[]
}
