import { apiClient, type RequestOptions } from './client'

export interface FactorCoverageData {
  strategy_name: string
  total_factors: number
  available_factors: string[]
  stub_factors: string[]
  coverage_rate: number
  configured_weights: Record<string, number>
  effective_weights: Record<string, number>
  weight_drift: Record<string, number>
}

export interface AllCoverageData {
  strategies: FactorCoverageData[]
  global_stub_factors: string[]
}

/**
 * 获取策略因子覆盖率。
 * Get factor coverage for a strategy.
 */
export async function getFactorCoverage(
  name: string,
  options?: RequestOptions
): Promise<FactorCoverageData> {
  const { data } = await apiClient.get(`/strategies/${name}/factor-coverage`, {
    ...(options?.silent ? { __silent: true } : {}),
  } as any)
  return data
}

/**
 * 获取全部策略因子覆盖率。
 * Get factor coverage for all strategies.
 */
export async function getAllFactorCoverage(options?: RequestOptions): Promise<AllCoverageData> {
  const { data } = await apiClient.get('/strategies/factor-coverage-all', {
    ...(options?.silent ? { __silent: true } : {}),
  } as any)
  return data
}
