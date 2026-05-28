/**
 * Unit tests for src/api/client.ts
 * Tests axios instance config, request/response interceptors, error classification.
 *
 * Mock strategy:
 *   - axios: mocked entirely; axios.create() returns a controllable fake.
 *     Interceptor callbacks are captured for direct invocation.
 *   - naive-ui: createDiscreteApi returns mock message.toast fns.
 *   - AbortController: stubbed globally so we can track abort() calls.
 *   - navigator.onLine: stubbed for offline-scenario tests.
 *
 * NOTE: The response interceptor clears config.__silent BEFORE classifyError
 *       runs, so in practice __silent does NOT suppress toasts through the
 *       normal interceptor chain. This is a known ordering issue in client.ts.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

/* ------------------------------------------------------------------ */
/*  vi.hoisted — variables available inside hoisted vi.mock callbacks  */
/* ------------------------------------------------------------------ */

const {
  mockMessage,
  abortControllers,
  mockAxiosInstance,
  refs,
} = vi.hoisted(() => {
  const msgMock = {
    error: vi.fn(),
    warning: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
    loading: vi.fn(),
  }

  const controllers: { abort: ReturnType<typeof vi.fn>; signal: any }[] = []

  const r: Record<string, any> = {}

  const axInst = {
    interceptors: {
      request: {
        use: vi.fn((fn: any) => { r.reqInterceptor = fn }),
      },
      response: {
        use: vi.fn((success: any, error: any) => {
          r.resSuccess = success
          r.resError = error
        }),
      },
    },
    defaults: { headers: { common: {} } },
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    patch: vi.fn(),
    request: vi.fn(),
  }

  return {
    mockMessage: msgMock,
    abortControllers: controllers,
    mockAxiosInstance: axInst,
    refs: r,
  }
})

class MockAbortController {
  abort = vi.fn()
  signal = { aborted: false }
  constructor() {
    abortControllers.push(this)
  }
}

// Snapshot of original call counts (module-level side effects run once)
const initialInterceptorCounts = {
  request: 0,
  response: 0,
}

/* ------------------------------------------------------------------ */
/*  vi.mock calls (hoisted by vitest)                                  */
/* ------------------------------------------------------------------ */

vi.mock('axios', () => {
  class FakeAxiosError extends Error {
    config: any
    response: any
    code: string | undefined
    isAxiosError = true
    constructor(message?: string, code?: string, config?: any, response?: any) {
      super(message)
      this.name = 'AxiosError'
      this.code = code
      this.config = config
      this.response = response
    }
  }

  return {
    default: {
      create: vi.fn((config: any) => {
        refs.createConfig = config
        return mockAxiosInstance
      }),
      isAxiosError: (e: any) => e?.isAxiosError === true,
    },
    AxiosError: FakeAxiosError,
  }
})

vi.mock('naive-ui', () => ({
  createDiscreteApi: vi.fn(() => ({ message: mockMessage })),
}))

/* ------------------------------------------------------------------ */
/*  Import SUT *after* mocks so it uses mocked dependencies            */
/* ------------------------------------------------------------------ */
import { apiClient } from './client'

// Record interceptor call counts right after module init
initialInterceptorCounts.request = mockAxiosInstance.interceptors.request.use.mock.calls.length
initialInterceptorCounts.response = mockAxiosInstance.interceptors.response.use.mock.calls.length

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function makeConfig(overrides: Record<string, any> = {}) {
  return {
    method: 'get',
    url: '/test',
    params: {},
    data: '',
    headers: {},
    ...overrides,
  }
}

function makeAxiosError(fields: Record<string, any> = {}) {
  const config = fields.config ?? makeConfig()
  return {
    isAxiosError: true,
    message: fields.message ?? 'Unknown',
    code: fields.code,
    config,
    response: fields.response,
    toJSON: () => ({}),
  }
}

const reqInterceptor = () => refs.reqInterceptor as (config: any) => any
const resSuccess = () => refs.resSuccess as (response: any) => any
const resError = () => refs.resError as (error: any) => Promise<never>

/* ------------------------------------------------------------------ */
/*  Tests                                                              */
/* ------------------------------------------------------------------ */

describe('api/client', () => {
  beforeEach(() => {
    // Only clear the message toast mocks, NOT interceptor registration mocks
    mockMessage.error.mockClear()
    mockMessage.warning.mockClear()
    mockMessage.success.mockClear()
    mockMessage.info.mockClear()
    abortControllers.length = 0

    // Stub global AbortController with our tracking mock
    vi.stubGlobal('AbortController', MockAbortController)

    // Restore navigator.onLine default
    Object.defineProperty(navigator, 'onLine', { value: true, configurable: true })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  /* ---------- 1. Axios instance configuration ---------- */

  describe('axios.create configuration', () => {
    it('should set baseURL to /api/v1', () => {
      expect(refs.createConfig.baseURL).toBe('/api/v1')
    })

    it('should set timeout to 120000ms', () => {
      expect(refs.createConfig.timeout).toBe(120_000)
    })

    it('should set Content-Type to application/json', () => {
      expect(refs.createConfig.headers['Content-Type']).toBe('application/json')
    })
  })

  describe('exported apiClient', () => {
    it('should be the instance returned by axios.create', () => {
      expect(apiClient).toBe(mockAxiosInstance)
    })
  })

  /* ---------- 2. Interceptor registration ---------- */

  describe('interceptor registration', () => {
    it('should have registered a request interceptor at module load', () => {
      expect(initialInterceptorCounts.request).toBeGreaterThanOrEqual(1)
      expect(refs.reqInterceptor).toBeTypeOf('function')
    })

    it('should have registered a response interceptor at module load', () => {
      expect(initialInterceptorCounts.response).toBeGreaterThanOrEqual(1)
      expect(refs.resSuccess).toBeTypeOf('function')
      expect(refs.resError).toBeTypeOf('function')
    })
  })

  /* ---------- 3. Request interceptor – dedup & abort ---------- */

  describe('request interceptor', () => {
    it('should create an AbortController and attach its signal to config', () => {
      const config = makeConfig({ method: 'get', url: '/stocks' })

      const result = reqInterceptor()(config)

      expect(abortControllers).toHaveLength(1)
      expect(result.signal).toBe(abortControllers[0].signal)
    })

    it('should abort a previous request with the same key', () => {
      const cfg1 = makeConfig({ method: 'get', url: '/stocks', params: { page: 1 } })
      const cfg2 = makeConfig({ method: 'get', url: '/stocks', params: { page: 1 } })

      reqInterceptor()(cfg1)
      const firstAbort = abortControllers[0].abort

      reqInterceptor()(cfg2)

      expect(firstAbort).toHaveBeenCalledTimes(1)
    })

    it('should NOT abort a previous request when keys differ', () => {
      const cfg1 = makeConfig({ method: 'get', url: '/stocks' })
      const cfg2 = makeConfig({ method: 'get', url: '/strategies' })

      reqInterceptor()(cfg1)
      const firstAbort = abortControllers[0].abort

      reqInterceptor()(cfg2)

      expect(firstAbort).not.toHaveBeenCalled()
    })

    it('should build distinct keys for different HTTP methods', () => {
      const getCfg = makeConfig({ method: 'get', url: '/data' })
      const postCfg = makeConfig({ method: 'post', url: '/data' })

      reqInterceptor()(getCfg)
      const firstAbort = abortControllers[0].abort
      reqInterceptor()(postCfg)

      expect(firstAbort).not.toHaveBeenCalled()
    })

    it('should build distinct keys for different params', () => {
      const cfg1 = makeConfig({ method: 'get', url: '/x', params: { a: 1 } })
      const cfg2 = makeConfig({ method: 'get', url: '/x', params: { a: 2 } })

      reqInterceptor()(cfg1)
      const firstAbort = abortControllers[0].abort
      reqInterceptor()(cfg2)

      expect(firstAbort).not.toHaveBeenCalled()
    })

    it('should build distinct keys for different body data', () => {
      const cfg1 = makeConfig({ method: 'post', url: '/x', data: '{"a":1}' })
      const cfg2 = makeConfig({ method: 'post', url: '/x', data: '{"a":2}' })

      reqInterceptor()(cfg1)
      const firstAbort = abortControllers[0].abort
      reqInterceptor()(cfg2)

      expect(firstAbort).not.toHaveBeenCalled()
    })
  })

  /* ---------- 4. Response interceptor – success path ---------- */

  describe('response interceptor – success', () => {
    it('should return the response unchanged', () => {
      const config = makeConfig()
      reqInterceptor()(config) // register in pending map

      const response = { data: { id: 1 }, config, status: 200 }
      const result = resSuccess()(response)

      expect(result).toBe(response)
    })

    it('should clean up pending request from the map on success', () => {
      const config = makeConfig({ method: 'get', url: '/cleanup-test' })
      reqInterceptor()(config) // 1st: adds to map
      reqInterceptor()(config) // 2nd: aborts 1st (key in map), adds new

      // Trigger success – should remove key from pending map
      resSuccess()({ config, data: {} })

      // 3rd identical request – key was removed, so no stale abort
      reqInterceptor()(config)
      const thirdController = abortControllers[2]
      expect(thirdController.abort).not.toHaveBeenCalled()
    })
  })

  /* ---------- 5. Response interceptor – error path ---------- */

  describe('response interceptor – error classification', () => {
    it('should reject with the original error', async () => {
      const err = makeAxiosError({ message: 'fail' })
      await expect(resError()(err)).rejects.toBe(err)
    })

    // --- network ---
    it('should show network toast when navigator is offline', async () => {
      Object.defineProperty(navigator, 'onLine', { value: false, configurable: true })
      const err = makeAxiosError({ message: 'Network Error', code: 'ERR_NETWORK' })

      await expect(resError()(err)).rejects.toBeDefined()
      expect(mockMessage.error).toHaveBeenCalledWith('网络连接已断开, 请检查网络后重试')
    })

    it('should show network toast on ERR_NETWORK with no response even when online', async () => {
      // navigator.onLine is true but no response + ERR_NETWORK triggers second OR branch
      const err = makeAxiosError({ message: 'Network Error', code: 'ERR_NETWORK' })

      await expect(resError()(err)).rejects.toBeDefined()
      // Same toast regardless of which branch triggered
      expect(mockMessage.error).toHaveBeenCalledWith('网络连接已断开, 请检查网络后重试')
    })

    // --- timeout ---
    it('should show timeout warning on ECONNABORTED + timeout message', async () => {
      const err = makeAxiosError({
        message: 'timeout of 120000ms exceeded',
        code: 'ECONNABORTED',
      })

      await expect(resError()(err)).rejects.toBeDefined()
      expect(mockMessage.warning).toHaveBeenCalledWith('请求超时, 后端响应过慢, 请稍后重试')
    })

    // --- 4xx ---
    it('should show detail from 4xx response body', async () => {
      const err = makeAxiosError({
        message: 'Bad Request',
        response: { status: 400, data: { detail: '无效的 strategy_id' } },
      })

      await expect(resError()(err)).rejects.toBeDefined()
      expect(mockMessage.error).toHaveBeenCalledWith('无效的 strategy_id')
    })

    it('should show generic 4xx message when detail is absent', async () => {
      const err = makeAxiosError({
        message: 'Not Found',
        response: { status: 404, data: {} },
      })

      await expect(resError()(err)).rejects.toBeDefined()
      expect(mockMessage.error).toHaveBeenCalledWith('请求参数有误 (404)')
    })

    it('should handle 422 Unprocessable Entity correctly', async () => {
      const err = makeAxiosError({
        message: 'Unprocessable',
        response: { status: 422, data: { detail: '字段格式错误' } },
      })

      await expect(resError()(err)).rejects.toBeDefined()
      expect(mockMessage.error).toHaveBeenCalledWith('字段格式错误')
    })

    // --- 5xx ---
    it('should show detail from 5xx response body', async () => {
      const err = makeAxiosError({
        message: 'Internal Server Error',
        response: { status: 500, data: { detail: '数据库连接失败' } },
      })

      await expect(resError()(err)).rejects.toBeDefined()
      expect(mockMessage.error).toHaveBeenCalledWith('数据库连接失败')
    })

    it('should show generic 5xx message when detail is absent', async () => {
      const err = makeAxiosError({
        message: 'Bad Gateway',
        response: { status: 502, data: {} },
      })

      await expect(resError()(err)).rejects.toBeDefined()
      expect(mockMessage.error).toHaveBeenCalledWith('服务异常, 请稍后重试 (502)')
    })

    // --- unknown status ---
    it('should show unknown-status message for non-4xx/5xx responses', async () => {
      const err = makeAxiosError({
        message: 'Redirect',
        response: { status: 301, data: {} },
      })

      await expect(resError()(err)).rejects.toBeDefined()
      expect(mockMessage.error).toHaveBeenCalledWith('未知错误 (301)')
    })

    // --- canceled ---
    it('should NOT show any toast for ERR_CANCELED', async () => {
      const err = makeAxiosError({ message: 'canceled', code: 'ERR_CANCELED' })

      await expect(resError()(err)).rejects.toBeDefined()
      expect(mockMessage.error).not.toHaveBeenCalled()
      expect(mockMessage.warning).not.toHaveBeenCalled()
    })

    // --- __silent ordering issue ---
    it('should clear __silent on config before classifyError (known interceptor ordering)', async () => {
      // The response error interceptor sets config.__silent = undefined BEFORE
      // calling classifyError(). So even if the caller sets __silent = true,
      // classifyError sees undefined and shows the toast. This tests actual behavior.
      const config = makeConfig()
      ;(config as any).__silent = true
      const err = makeAxiosError({
        message: 'Server Error',
        response: { status: 500, data: { detail: 'oops' } },
        config,
      })

      await expect(resError()(err)).rejects.toBeDefined()
      // __silent was cleared by interceptor before classifyError ran
      // so the detail toast IS shown — this documents the current (buggy) behavior
      expect(mockMessage.error).toHaveBeenCalledWith('oops')
      // Config __silent should be cleared after interceptor runs
      expect((config as any).__silent).toBeUndefined()
    })

    // --- fallback ---
    it('should show generic fallback for unknown error types', async () => {
      const err = makeAxiosError({ message: 'something weird', code: 'UNKNOWN_CODE' })

      await expect(resError()(err)).rejects.toBeDefined()
      expect(mockMessage.error).toHaveBeenCalledWith('未知错误, 请刷新页面')
    })

    // --- cleanup ---
    it('should clean up pending request from the map on error', async () => {
      const config = makeConfig({ method: 'get', url: '/err-cleanup' })
      reqInterceptor()(config) // add to map

      const err = makeAxiosError({ message: 'fail', config })
      await expect(resError()(err)).rejects.toBeDefined()

      // New identical request – pending key was removed, no stale abort
      reqInterceptor()(config)
      const latest = abortControllers[abortControllers.length - 1]
      expect(latest.abort).not.toHaveBeenCalled()
    })

    it('should handle error with no config gracefully', async () => {
      const err = { isAxiosError: true, message: 'no-config', code: 'ERR_NETWORK' }
      await expect(resError()(err)).rejects.toBe(err)
      // Should still attempt toast (navigator online + ERR_NETWORK path)
      expect(mockMessage.error).toHaveBeenCalled()
    })
  })

  /* ---------- 6. console.error logging ---------- */

  describe('error logging', () => {
    it('should log error URL and message to console.error', async () => {
      const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
      const err = makeAxiosError({ message: 'boom', config: makeConfig({ url: '/logged' }) })

      await expect(resError()(err)).rejects.toBeDefined()

      expect(spy).toHaveBeenCalledWith('[API Error]', '/logged', 'boom')
      spy.mockRestore()
    })

    it('should log undefined url when config has no url', async () => {
      const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
      const err = { isAxiosError: true, message: 'lost', code: 'ERR_NETWORK' }

      await expect(resError()(err)).rejects.toBeDefined()

      // config is undefined → config?.url is undefined
      expect(spy).toHaveBeenCalledWith('[API Error]', undefined, 'lost')
      spy.mockRestore()
    })
  })
})
