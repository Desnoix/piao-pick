import { apiClient, type RequestOptions } from './client'
import type {
  BacktestRunRequest,
  BacktestResult,
  BacktestRunResponse,
  AvailableDates,
} from '../types/backtest'

export async function runBacktest(
  req: BacktestRunRequest,
  options?: RequestOptions
): Promise<BacktestRunResponse> {
  const { data } = await apiClient.post('/backtest/run', req, {
    ...(options?.silent ? { __silent: true } : {}),
  } as any)
  return data
}

export async function listBacktestResults(
  strategy_id?: string,
  options?: RequestOptions
): Promise<BacktestResult[]> {
  const params: Record<string, any> = {}
  if (strategy_id) params.strategy_id = strategy_id
  const { data } = await apiClient.get('/backtest/results', {
    params,
    ...(options?.silent ? { __silent: true } : {}),
  } as any)
  return data
}

export async function getBacktestResult(
  backtest_id: string,
  options?: RequestOptions
): Promise<BacktestResult> {
  const { data } = await apiClient.get(`/backtest/results/${backtest_id}`, {
    ...(options?.silent ? { __silent: true } : {}),
  } as any)
  return data
}

export async function getAvailableDates(options?: RequestOptions): Promise<AvailableDates> {
  const { data } = await apiClient.get('/backtest/available-dates', {
    ...(options?.silent ? { __silent: true } : {}),
  } as any)
  return data
}

/**
 * Run backtest for multiple strategies sequentially.
 * 批量运行多个策略的回测。
 */
export async function runBacktestBatch(
  requests: BacktestRunRequest[],
  options?: RequestOptions
): Promise<{ strategyId: string; result: BacktestRunResponse }[]> {
  const results: { strategyId: string; result: BacktestRunResponse }[] = []
  for (const req of requests) {
    const result = await runBacktest(req, options)
    results.push({ strategyId: req.strategy_id, result })
  }
  return results
}
