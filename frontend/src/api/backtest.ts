import { apiClient } from './client'
import type { BacktestRunRequest, BacktestResult, BacktestRunResponse, AvailableDates } from '../types/backtest'

export async function runBacktest(req: BacktestRunRequest): Promise<BacktestRunResponse> {
  const { data } = await apiClient.post('/backtest/run', req)
  return data
}

export async function listBacktestResults(strategy_id?: string): Promise<BacktestResult[]> {
  const params: Record<string, any> = {}
  if (strategy_id) params.strategy_id = strategy_id
  const { data } = await apiClient.get('/backtest/results', { params })
  return data
}

export async function getBacktestResult(backtest_id: string): Promise<BacktestResult> {
  const { data } = await apiClient.get(`/backtest/results/${backtest_id}`)
  return data
}

export async function getAvailableDates(): Promise<AvailableDates> {
  const { data } = await apiClient.get('/backtest/available-dates')
  return data
}
