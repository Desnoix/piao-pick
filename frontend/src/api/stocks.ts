import { apiClient } from './client'
import type { StockInfo, Kline, FactorData } from '../types/stock'
import type { PaginatedResponse } from '../types/api'

export async function listStocks(
  offset = 0,
  limit = 50,
  keyword?: string
): Promise<PaginatedResponse<StockInfo>> {
  const params: Record<string, any> = { offset, limit }
  if (keyword) params.keyword = keyword
  const { data } = await apiClient.get('/stocks/', { params })
  return data
}

export async function getStock(ts_code: string): Promise<StockInfo> {
  const { data } = await apiClient.get(`/stocks/${ts_code}`)
  return data
}

export async function getKline(
  ts_code: string,
  limit = 500,
  start_date?: string,
  end_date?: string
): Promise<Kline[]> {
  const params: Record<string, any> = { limit }
  if (start_date) params.start_date = start_date
  if (end_date) params.end_date = end_date
  const { data } = await apiClient.get(`/stocks/${ts_code}/kline`, { params })
  return data
}

export async function getFactors(
  ts_code: string,
  start_date?: string,
  end_date?: string
): Promise<FactorData[]> {
  const params: Record<string, any> = {}
  if (start_date) params.start_date = start_date
  if (end_date) params.end_date = end_date
  const { data } = await apiClient.get(`/stocks/${ts_code}/factors`, { params })
  return data
}
