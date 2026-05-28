import { apiClient, type RequestOptions } from './client'
import type { SelectionRunRequest, SelectionRecord } from '../types/selection'

export async function runSelection(
  req: SelectionRunRequest,
  options?: RequestOptions
): Promise<any> {
  const { data } = await apiClient.post('/selection/run', req, {
    ...(options?.silent ? { __silent: true } : {}),
  } as any)
  return data
}

export async function getSelectionResults(
  strategy_id?: string,
  trade_date?: string,
  limit = 100,
  options?: RequestOptions
): Promise<SelectionRecord[]> {
  const params: Record<string, any> = { limit }
  if (strategy_id) params.strategy_id = strategy_id
  if (trade_date) params.trade_date = trade_date
  const { data } = await apiClient.get('/selection/results', {
    params,
    ...(options?.silent ? { __silent: true } : {}),
  } as any)
  return data
}

export async function getSelectionResultsByDate(
  trade_date: string,
  strategy_id?: string,
  options?: RequestOptions
): Promise<SelectionRecord[]> {
  const params: Record<string, any> = {}
  if (strategy_id) params.strategy_id = strategy_id
  const { data } = await apiClient.get(`/selection/results/${trade_date}`, {
    params,
    ...(options?.silent ? { __silent: true } : {}),
  } as any)
  return data
}

export interface PrepareStatus {
  status: 'preparing' | 'done' | 'failed' | 'unknown'
  trade_date: string
  result?: Record<string, any>
  error?: string
  factor_count?: number
  message?: string
}

export async function getPrepareStatus(
  tradeDate: string,
  options?: RequestOptions
): Promise<PrepareStatus> {
  const { data } = await apiClient.get(`/selection/prepare/status/${tradeDate}`, {
    ...(options?.silent ? { __silent: true } : {}),
  } as any)
  return data
}
