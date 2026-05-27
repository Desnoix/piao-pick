import { apiClient } from './client'
import type { SelectionRunRequest, SelectionRecord } from '../types/selection'

export async function runSelection(req: SelectionRunRequest): Promise<any> {
  const { data } = await apiClient.post('/selection/run', req)
  return data
}

export async function getSelectionResults(
  strategy_id?: string,
  trade_date?: string,
  limit = 100
): Promise<SelectionRecord[]> {
  const params: Record<string, any> = { limit }
  if (strategy_id) params.strategy_id = strategy_id
  if (trade_date) params.trade_date = trade_date
  const { data } = await apiClient.get('/selection/results', { params })
  return data
}

export async function getSelectionResultsByDate(
  trade_date: string,
  strategy_id?: string
): Promise<SelectionRecord[]> {
  const params: Record<string, any> = {}
  if (strategy_id) params.strategy_id = strategy_id
  const { data } = await apiClient.get(`/selection/results/${trade_date}`, { params })
  return data
}
