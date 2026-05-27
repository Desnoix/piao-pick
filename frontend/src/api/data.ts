import { apiClient } from './client'
import type { DataStatus, TradeCalendar, SyncRequest, SyncResponse } from '../types/api'

export async function getDataStatus(): Promise<DataStatus> {
  const { data } = await apiClient.get('/data/status')
  return data
}

export async function syncData(req: SyncRequest): Promise<SyncResponse> {
  const { data } = await apiClient.post('/data/sync', req)
  return data
}

export async function getTradeCalendar(
  start_date?: string,
  end_date?: string
): Promise<TradeCalendar> {
  const params: Record<string, any> = {}
  if (start_date) params.start_date = start_date
  if (end_date) params.end_date = end_date
  const { data } = await apiClient.get('/data/trade-calendar', { params })
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

export async function startHistorySync(req: HistorySyncRequest): Promise<HistorySyncProgress> {
  const { data } = await apiClient.post('/data/history-sync', req)
  return data.data
}

export async function getHistorySyncStatus(taskId?: string): Promise<HistorySyncProgress | null> {
  const url = taskId ? `/data/history-sync/${taskId}` : '/data/history-sync/status'
  const { data } = await apiClient.get(url)
  return data.data
}

export async function listHistorySyncTasks(limit: number = 10): Promise<HistorySyncProgress[]> {
  const { data } = await apiClient.get('/data/history-sync/history', { params: { limit } })
  return data.data
}

export interface FactorComputeRequest {
  start_date?: string
  end_date?: string
  stock_codes?: string[]
}

export async function computeFactors(req?: FactorComputeRequest): Promise<any> {
  const { data } = await apiClient.post('/data/factor-compute', req || {})
  return data
}
