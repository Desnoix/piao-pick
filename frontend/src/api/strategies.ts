import { apiClient } from './client'
import type { Strategy, StrategyDetail, StrategyCreateRequest, StrategyUpdateRequest } from '../types/strategy'

export async function listStrategies(): Promise<Strategy[]> {
  const { data } = await apiClient.get('/strategies/')
  return data
}

export async function getStrategy(id: string): Promise<StrategyDetail> {
  const { data } = await apiClient.get(`/strategies/${id}`)
  return data
}

export async function createStrategy(req: StrategyCreateRequest): Promise<StrategyDetail> {
  const { data } = await apiClient.post('/strategies/', req)
  return data
}

export async function updateStrategy(id: string, req: StrategyUpdateRequest): Promise<StrategyDetail> {
  const { data } = await apiClient.put(`/strategies/${id}`, req)
  return data
}

export async function deleteStrategy(id: string): Promise<void> {
  await apiClient.delete(`/strategies/${id}`)
}
