import { apiClient, type RequestOptions } from './client'
import type { DataStatus, TradeCalendar, SyncRequest, SyncResponse } from '../types/api'

export async function getDataStatus(options?: RequestOptions): Promise<DataStatus> {
  const { data } = await apiClient.get('/data/status', {
    ...(options?.silent ? { __silent: true } : {}),
  } as any)
  return data
}

export async function syncData(req: SyncRequest, options?: RequestOptions): Promise<SyncResponse> {
  const { data } = await apiClient.post('/data/sync', req, {
    ...(options?.silent ? { __silent: true } : {}),
  } as any)
  return data
}

export async function getTradeCalendar(
  start_date?: string,
  end_date?: string,
  options?: RequestOptions
): Promise<TradeCalendar> {
  const params: Record<string, any> = {}
  if (start_date) params.start_date = start_date
  if (end_date) params.end_date = end_date
  const { data } = await apiClient.get('/data/trade-calendar', {
    params,
    ...(options?.silent ? { __silent: true } : {}),
  } as any)
  return data
}

export interface HistorySyncRequest {
  start_date: string
  end_date?: string
  adjust_type?: string
  stock_codes?: string[]
  use_existing?: boolean
}

export interface HistorySyncProgress {
  task_id: string
  status: string
  start_date: string
  end_date: string
  progress: {
    total: number
    completed: number
    failed: number
    total_klines: number
    percent: number
    current_stock: string | null
  }
  created_at: string
  started_at: string | null
  completed_at: string | null
  error_messages: string | null
}

export async function startHistorySync(
  req: HistorySyncRequest,
  options?: RequestOptions
): Promise<HistorySyncProgress> {
  const { data } = await apiClient.post('/data/history-sync', req, {
    ...(options?.silent ? { __silent: true } : {}),
  } as any)
  return data.data
}

export async function getHistorySyncStatus(
  taskId?: string,
  options?: RequestOptions
): Promise<HistorySyncProgress | null> {
  const url = taskId ? `/data/history-sync/${taskId}` : '/data/history-sync/status'
  const { data } = await apiClient.get(url, {
    ...(options?.silent ? { __silent: true } : {}),
  } as any)
  return data.data
}

export async function listHistorySyncTasks(
  limit: number = 10,
  options?: RequestOptions
): Promise<HistorySyncProgress[]> {
  const { data } = await apiClient.get('/data/history-sync/history', {
    params: { limit },
    ...(options?.silent ? { __silent: true } : {}),
  } as any)
  return data.data
}

export interface FactorComputeRequest {
  start_date?: string
  end_date?: string
  stock_codes?: string[]
}

export async function computeFactors(
  req?: FactorComputeRequest,
  options?: RequestOptions
): Promise<any> {
  const { data } = await apiClient.post('/data/factor-compute', req || {}, {
    ...(options?.silent ? { __silent: true } : {}),
  } as any)
  return data
}
