import { apiClient, type RequestOptions } from './client'

export interface MarketIndexLatest {
  code: string
  name: string
  price: number
  change_pct: number
  volume: number
  amount: number
}

export interface MarketIndexHistory {
  date: string
  close: number
}

export interface MarketIndexResponse {
  latest: MarketIndexLatest
  history: MarketIndexHistory[]
}

export async function getMarketIndex(
  code: string = '000300',
  days: number = 30,
  options?: RequestOptions
): Promise<MarketIndexResponse> {
  const { data } = await apiClient.get(`/market/index/${code}`, {
    params: { days },
    ...(options?.silent ? { __silent: true } : {}),
  } as any)
  return data
}
