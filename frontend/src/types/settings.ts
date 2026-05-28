/** 数据源配置 */
export interface DataSourceConfig {
  jqdata_token: string
  jqdata_password: string
  jqdata_configured: boolean
}

/** 更新数据源配置的请求 */
export interface DataSourceUpdateRequest {
  jqdata_token?: string
  jqdata_password?: string
}

/** 更新结果 */
export interface DataSourceUpdateResponse {
  status: string
  updated: string[]
}