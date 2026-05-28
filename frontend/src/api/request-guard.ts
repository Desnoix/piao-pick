/**
 * Page-level AbortController guard for one-off async operations.
 * 页面级取消守卫，用于非幂等操作 (回测、选股等长时间运行请求)。
 *
 * Usage:
 *   const guard = createRequestGuard()
 *   // On button click:
 *   guard.abortPrevious()
 *   const result = await runSelection({ strategy_id }, { signal: guard.signal })
 */
export function createRequestGuard() {
  let controller: AbortController | null = null

  return {
    abortPrevious() {
      controller?.abort()
      controller = new AbortController()
    },
    get signal() {
      return controller?.signal
    },
    abort() {
      controller?.abort()
      controller = null
    },
  }
}
