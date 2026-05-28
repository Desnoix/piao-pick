import { apiClient, type RequestOptions } from './client'
import type { DataSourceConfig, DataSourceUpdateRequest, DataSourceUpdateResponse } from '../types/settings'

/** 获取当前数据源配置 */
export async function getDataSources(options?: RequestOptions): Promise<DataSourceConfig> {
  const { data } = await apiClient.get('/settings/data-sources', {
    ...(options?.silent ? { __silent: true } : {}),
  } as any)
  return data
}

/** 更新数据源配置 */
export async function updateDataSources(
  config: DataSourceUpdateRequest,
  options?: RequestOptions,
): Promise<DataSourceUpdateResponse> {
  const { data } = await apiClient.put('/settings/data-sources', config, {
    ...(options?.silent ? { __silent: true } : {}),
  } as any)
  return data
}