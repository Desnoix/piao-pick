import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { createDiscreteApi } from 'naive-ui'

/**
 * Discrete message API — works outside Vue component lifecycle.
 * 独立消息实例，不依赖组件上下文。
 */
const { message } = createDiscreteApi(['message'], {
  configProviderProps: { theme: null },
})

/**
 * Pending request registry for AbortController dedup.
 * 活跃请求注册表，按 key 维度去重。
 */
const pendingRequests = new Map<string, AbortController>()

function buildRequestKey(config: InternalAxiosRequestConfig): string {
  const { method, url, params, data } = config
  return `${method}:${url}:${JSON.stringify(params || {})}:${typeof data === 'string' ? data : JSON.stringify(data || '')}`
}

function cancelPendingRequest(key: string): void {
  const existing = pendingRequests.get(key)
  if (existing) {
    existing.abort()
    pendingRequests.delete(key)
  }
}

/**
 * Classify and report an API error to the user.
 * 对 API 错误分类并通过全局 toast 通知用户。
 */
function classifyError(error: AxiosError): void {
  const config = error.config as (InternalAxiosRequestConfig & { __silent?: boolean }) | undefined
  if (config?.__silent) return

  if (!navigator.onLine || (!error.response && error.code === 'ERR_NETWORK')) {
    message.error('网络连接已断开, 请检查网络后重试')
    return
  }

  if (error.code === 'ECONNABORTED' && error.message.includes('timeout')) {
    message.warning('请求超时, 后端响应过慢, 请稍后重试')
    return
  }

  if (error.response) {
    const status = error.response.status
    const detail = (error.response.data as Record<string, unknown>)?.detail as string | undefined

    if (status >= 400 && status < 500) {
      message.error(detail || `请求参数有误 (${status})`)
    } else if (status >= 500) {
      message.error(detail || `服务异常, 请稍后重试 (${status})`)
    } else {
      message.error(detail || `未知错误 (${status})`)
    }
    return
  }

  if (error.code === 'ERR_CANCELED') {
    return
  }

  message.error('未知错误, 请刷新页面')
}

/**
 * Shared options for all API functions.
 * 所有 API 函数共用的请求选项。
 */
export interface RequestOptions {
  /** Suppress global error toast — page handles error itself. 抑制全局 toast 提示 */
  silent?: boolean
}

export const apiClient = axios.create({
  baseURL: '/api/v1',
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json',
  },
})

/* ---- Request interceptor: dedup + cancel ---- */
apiClient.interceptors.request.use((config) => {
  const key = buildRequestKey(config)
  cancelPendingRequest(key)

  const controller = new AbortController()
  pendingRequests.set(key, controller)
  config.signal = controller.signal

  return config
})

/* ---- Response interceptor: cleanup + classify ---- */
apiClient.interceptors.response.use(
  (response) => {
    const config = response.config
    const key = buildRequestKey(config as InternalAxiosRequestConfig)
    pendingRequests.delete(key)
    ;(config as InternalAxiosRequestConfig & { __silent?: boolean }).__silent = undefined
    return response
  },
  (error: AxiosError) => {
    const config = error.config as InternalAxiosRequestConfig | undefined
    if (config) {
      const key = buildRequestKey(config)
      pendingRequests.delete(key)
      ;(config as InternalAxiosRequestConfig & { __silent?: boolean }).__silent = undefined
    }

    console.error('[API Error]', config?.url, error.message)
    classifyError(error)
    return Promise.reject(error)
  }
)
