import { apiClient, type RequestOptions } from './client'
import type {
  Strategy,
  StrategyDetail,
  StrategyCreateRequest,
  StrategyUpdateRequest,
} from '../types/strategy'

export async function listStrategies(options?: RequestOptions): Promise<Strategy[]> {
  const { data } = await apiClient.get('/strategies/', {
    ...(options?.silent ? { __silent: true } : {}),
  } as any)
  return data
}

export async function getStrategy(id: string, options?: RequestOptions): Promise<StrategyDetail> {
  const { data } = await apiClient.get(`/strategies/${id}`, {
    ...(options?.silent ? { __silent: true } : {}),
  } as any)
  return data
}

export async function createStrategy(
  req: StrategyCreateRequest,
  options?: RequestOptions
): Promise<StrategyDetail> {
  const { data } = await apiClient.post('/strategies/', req, {
    ...(options?.silent ? { __silent: true } : {}),
  } as any)
  return data
}

export async function updateStrategy(
  id: string,
  req: StrategyUpdateRequest,
  options?: RequestOptions
): Promise<StrategyDetail> {
  const { data } = await apiClient.put(`/strategies/${id}`, req, {
    ...(options?.silent ? { __silent: true } : {}),
  } as any)
  return data
}

export async function deleteStrategy(id: string, options?: RequestOptions): Promise<void> {
  await apiClient.delete(`/strategies/${id}`, {
    ...(options?.silent ? { __silent: true } : {}),
  } as any)
}
