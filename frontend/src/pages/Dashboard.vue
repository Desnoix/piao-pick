<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, h } from 'vue'
import { NDataTable, NTag, NButton } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { useRouter } from 'vue-router'
import { getDataStatus, getTradeCalendar, syncData } from '../api/data'
import { listStrategies } from '../api/strategies'
import { getSelectionResults } from '../api/selection'
import { listBacktestResults } from '../api/backtest'
import { getMarketIndex } from '../api/market'
import type { MarketIndexResponse } from '../api/market'
import { formatZScore, getZScoreColor } from '../utils/format'
import {
  PhDatabase,
  PhChartLineUp,
  PhLightning,
  PhFunnel,
  PhSliders,
  PhArrowsClockwise,
  PhChartBar,
  PhArrowRight,
  PhClock,
  PhWarning,
  PhPlay,
} from '@phosphor-icons/vue'
import type { DataStatus } from '../types/api'
import type { Strategy } from '../types/strategy'
import type { SelectionRecord } from '../types/selection'
import type { BacktestResult } from '../types/backtest'

const router = useRouter()

// ===== State =====
const dataStatus = ref<DataStatus | null>(null)
const strategies = ref<Strategy[]>([])
const recentResults = ref<SelectionRecord[]>([])
const backtestResults = ref<BacktestResult[]>([])
const marketData = ref<MarketIndexResponse | null>(null)
const tradeCalendar = ref<string[]>([])
const loading = ref(true)
const syncRunning = ref(false)
const error = ref<string | null>(null)
let refreshTimer: ReturnType<typeof setInterval> | null = null

// ===== Computed: Date display =====
const formattedDate = computed(() => {
  const now = new Date()
  const month = now.getMonth() + 1
  const day = now.getDate()
  const weekdays = ['日', '一', '二', '三', '四', '五', '六']
  return `${month}月${day}日 周${weekdays[now.getDay()]}`
})

// ===== Computed: Trading day status =====
const todayStr = computed(() => {
  const now = new Date()
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
})

const isTradingDay = computed(() => {
  return tradeCalendar.value.includes(todayStr.value)
})

const nextTradingDay = computed(() => {
  const future = tradeCalendar.value.filter((d) => d > todayStr.value).sort()
  if (future.length === 0) return null
  const next = future[0]
  const now = new Date(todayStr.value)
  const target = new Date(next)
  const diffDays = Math.round((target.getTime() - now.getTime()) / 86400000)
  return { date: next, daysAway: diffDays }
})

// ===== Computed: Market trading hours =====
const marketSession = computed((): 'trading' | 'closed' | 'pre' | 'post' => {
  if (!isTradingDay.value) return 'closed'
  const now = new Date()
  const h = now.getHours()
  const m = now.getMinutes()
  const current = h * 60 + m
  const morningOpen = 9 * 60 + 30
  const morningClose = 11 * 60 + 30
  const afternoonOpen = 13 * 60
  const afternoonClose = 15 * 60
  if (current >= morningOpen && current <= morningClose) return 'trading'
  if (current >= afternoonOpen && current <= afternoonClose) return 'trading'
  if (current < morningOpen) return 'pre'
  return 'post'
})

const marketSessionLabel = computed(() => {
  switch (marketSession.value) {
    case 'trading':
      return '交易中'
    case 'pre':
      return '未开盘'
    case 'post':
      return '已收盘'
    default:
      return '休市'
  }
})

// ===== Computed: Data health =====
const dataHealth = computed(() => {
  if (!dataStatus.value) return null
  const klineDate = dataStatus.value.latest_kline_date
  const factorDate = dataStatus.value.latest_factor_date

  // Calculate staleness
  let staleDays = 0
  if (klineDate) {
    const kline = new Date(klineDate)
    const now = new Date()
    staleDays = Math.max(0, Math.round((now.getTime() - kline.getTime()) / 86400000))
  }

  const isStale = staleDays > 1 && isTradingDay.value

  // Coverage approximation: stale_days penalty
  const klineCoveragePct = klineDate
    ? Math.max(0, Math.min(100, 100 - Math.max(0, staleDays - 1) * 5))
    : 0

  return {
    kline_date: klineDate,
    factor_date: factorDate,
    kline_coverage_pct: klineCoveragePct,
    is_stale: isStale,
    stale_days: staleDays,
    has_kline: !!klineDate,
    has_factor: !!factorDate,
  }
})

// ===== Computed: Selection summary =====
const selectionSummary = computed(() => {
  if (recentResults.value.length === 0) return null

  // Group by most recent trade_date
  const dates = [...new Set(recentResults.value.map((r) => r.trade_date))].sort().reverse()
  if (dates.length === 0) return null

  const latestDate = dates[0]
  const latestBatch = recentResults.value.filter((r) => r.trade_date === latestDate)

  // Group by strategy
  const byStrategy = new Map<string, SelectionRecord[]>()
  for (const r of latestBatch) {
    const list = byStrategy.get(r.strategy_id) || []
    list.push(r)
    byStrategy.set(r.strategy_id, list)
  }

  const firstStrategy = byStrategy.entries().next().value
  if (!firstStrategy) return null

  const [strategyId, records] = firstStrategy
  const avgScore = records.reduce((s, r) => s + r.composite_score, 0) / records.length
  const topStock = records.reduce(
    (best, r) => (r.composite_score > best.composite_score ? r : best),
    records[0]
  )

  // Find strategy display name
  const strat = strategies.value.find((s) => s.id === strategyId)
  const displayName = strat?.display_name || strat?.name || strategyId

  return {
    trade_date: latestDate,
    strategy_id: strategyId,
    strategy_name: displayName,
    stock_count: records.length,
    avg_score: avgScore,
    top_stock_code: topStock.ts_code,
    top_stock_score: topStock.composite_score,
    total_strategies: byStrategy.size,
  }
})

// ===== Computed: Strategy cards with backtest data =====
const strategyCards = computed(() => {
  return strategies.value.map((s) => {
    const bt = backtestResults.value.find((b) => b.strategy_id === s.id)
    return {
      ...s,
      backtest: bt
        ? {
            annual_return: bt.annual_return,
            max_drawdown: bt.max_drawdown,
            sharpe_ratio: bt.sharpe_ratio,
          }
        : null,
    }
  })
})

// ===== Computed: Market index display =====
const indexChangeColor = computed(() => {
  if (!marketData.value) return 'var(--color-text-secondary)'
  const pct = marketData.value.latest.change_pct
  if (pct > 0) return 'var(--color-up)'
  if (pct < 0) return 'var(--color-down)'
  return 'var(--color-text-secondary)'
})

const sparklinePoints = computed(() => {
  if (!marketData.value?.history?.length) return null
  const closes = marketData.value.history.map((h) => h.close)
  if (closes.length < 2) return null
  const min = Math.min(...closes)
  const max = Math.max(...closes)
  const range = max - min || 1
  const width = 80
  const height = 32
  // Normalize to pixel coordinates
  return closes
    .map((c, i) => `${i * (width / (closes.length - 1))},${height - ((c - min) / range) * height}`)
    .join(' ')
})

// ===== Data loading =====
async function loadData() {
  loading.value = true
  error.value = null
  try {
    const now = new Date()
    const startDate = new Date(now)
    startDate.setDate(startDate.getDate() - 7)
    const endDate = new Date(now)
    endDate.setDate(endDate.getDate() + 14)

    const [statusData, stratData, results, btResults, calendar, mktData] = await Promise.allSettled(
      [
        getDataStatus({ silent: true }),
        listStrategies({ silent: true }),
        getSelectionResults(undefined, undefined, 50, { silent: true }),
        listBacktestResults(undefined, { silent: true }),
        getTradeCalendar(startDate.toISOString().slice(0, 10), endDate.toISOString().slice(0, 10), {
          silent: true,
        }),
        getMarketIndex('000300', 30, { silent: true }),
      ]
    )

    if (statusData.status === 'fulfilled') dataStatus.value = statusData.value
    if (stratData.status === 'fulfilled') strategies.value = stratData.value
    if (results.status === 'fulfilled') recentResults.value = results.value
    if (btResults.status === 'fulfilled') backtestResults.value = btResults.value
    if (calendar.status === 'fulfilled') tradeCalendar.value = calendar.value.trading_days
    if (mktData.status === 'fulfilled') marketData.value = mktData.value
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

// ===== Silent refresh (no loading skeleton) =====
async function refreshData() {
  try {
    const [statusData, stratData, results, btResults, mktData] = await Promise.allSettled([
      getDataStatus({ silent: true }),
      listStrategies({ silent: true }),
      getSelectionResults(undefined, undefined, 50, { silent: true }),
      listBacktestResults(undefined, { silent: true }),
      getMarketIndex('000300', 30, { silent: true }),
    ])

    if (statusData.status === 'fulfilled') dataStatus.value = statusData.value
    if (stratData.status === 'fulfilled') strategies.value = stratData.value
    if (results.status === 'fulfilled') recentResults.value = results.value
    if (btResults.status === 'fulfilled') backtestResults.value = btResults.value
    if (mktData.status === 'fulfilled') marketData.value = mktData.value
  } catch {
    // Silent refresh — don't show errors
  }
}

// ===== Actions =====
async function handleSyncData() {
  syncRunning.value = true
  try {
    await syncData({}, { silent: true })
    await loadData()
  } catch {
    // Error handled by interceptor
  } finally {
    syncRunning.value = false
  }
}

function handleRunSelection() {
  router.push('/selection')
}

function handleRunBacktest() {
  router.push('/backtest')
}

// ===== Table columns =====
const recentColumns: DataTableColumns<SelectionRecord> = [
  {
    title: '#',
    key: 'rank',
    width: 56,
    render(row) {
      return h('span', { class: 'data-mono text-[var(--color-text-secondary)]' }, row.rank)
    },
  },
  {
    title: '代码',
    key: 'ts_code',
    width: 120,
    render(row) {
      return h(
        'a',
        {
          class: 'data-mono text-[var(--color-accent)] cursor-pointer hover:underline',
          onClick: () => router.push(`/stock/${row.ts_code}`),
        },
        row.ts_code
      )
    },
  },
  {
    title: '评分',
    key: 'composite_score',
    width: 110,
    render(row) {
      return h(
        'span',
        {
          class: `data-mono font-medium ${getZScoreColor(row.composite_score)}`,
          title: `加权 Z-Score: 典型范围 [-3, +3]`,
        },
        formatZScore(row.composite_score)
      )
    },
  },
  {
    title: '运行日期',
    key: 'trade_date',
    width: 100,
    render(row) {
      return h(
        'span',
        { class: 'text-xs text-[var(--color-text-muted)] data-mono' },
        row.trade_date
      )
    },
  },
  {
    title: '策略',
    key: 'strategy_id',
    width: 140,
    ellipsis: { tooltip: true },
    render(row) {
      const strat = strategies.value.find((s) => s.id === row.strategy_id)
      const label = strat?.display_name || row.strategy_id
      return h('span', { class: 'text-[var(--color-text-secondary)] text-xs' }, label)
    },
  },
  {
    title: '状态',
    key: 'status',
    width: 80,
    render(row) {
      const type = row.status === 'OK' ? 'success' : 'warning'
      return h(NTag, { type, size: 'small', round: true, bordered: false }, () => row.status)
    },
  },
]

onMounted(() => {
  loadData()
  // Auto-refresh every 5 minutes
  refreshTimer = setInterval(refreshData, 5 * 60 * 1000)
})

onBeforeUnmount(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>

<template>
  <div class="flex flex-col gap-6">
    <!-- ===== Header: date + trading day badge + market index ===== -->
    <header class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <span class="text-lg font-medium text-[var(--color-text-secondary)]">
          {{ formattedDate }}
        </span>
        <span
          v-if="!loading && isTradingDay"
          class="inline-flex items-center gap-1.5 rounded bg-[var(--color-accent-muted)] px-2 py-0.5 text-xs font-medium text-[var(--color-accent)]"
        >
          交易日
        </span>
        <span
          v-else-if="!loading && !isTradingDay"
          class="inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-xs text-[var(--color-text-muted)]"
        >
          休市
        </span>
      </div>

      <!-- Market index mini display -->
      <div v-if="!loading && marketData" class="flex items-center gap-3">
        <!-- Mini sparkline -->
        <svg v-if="sparklinePoints" width="80" height="32" class="opacity-60">
          <polyline
            fill="none"
            :stroke="indexChangeColor"
            stroke-width="1.5"
            :points="sparklinePoints"
          />
        </svg>
        <div class="text-right">
          <div class="text-xs text-[var(--color-text-muted)]">
            {{ marketData.latest.name }}
          </div>
          <div class="flex items-baseline gap-2">
            <span class="data-mono text-sm font-semibold" :style="{ color: indexChangeColor }">
              {{ marketData.latest.price.toFixed(2) }}
            </span>
            <span class="data-mono text-xs" :style="{ color: indexChangeColor }">
              {{ marketData.latest.change_pct >= 0 ? '+' : ''
              }}{{ marketData.latest.change_pct.toFixed(2) }}%
            </span>
          </div>
        </div>
      </div>
    </header>

    <!-- ===== Loading skeleton ===== -->
    <template v-if="loading">
      <div class="dashboard-grid">
        <div class="glass-panel col-span-1 p-6 md:col-span-2">
          <div class="skeleton-line skeleton-w24 mb-3" />
          <div class="skeleton-line skeleton-w32 skeleton-xl mb-2" />
          <div class="skeleton-line skeleton-w16" />
        </div>
        <div v-for="i in 2" :key="i" class="glass-panel p-5">
          <div class="mb-4 flex items-center gap-2">
            <div class="skeleton-line skeleton-w4 skeleton-circle" />
            <div class="skeleton-line skeleton-w20" />
          </div>
          <div class="skeleton-line skeleton-w24 skeleton-lg" />
        </div>
      </div>
      <div class="flex gap-3">
        <div v-for="i in 4" :key="i" class="skeleton-line skeleton-pill" />
      </div>
    </template>

    <!-- ===== Error state ===== -->
    <div v-else-if="error" class="glass-panel p-8 text-center">
      <p class="mb-4 text-sm text-[var(--color-error)]">{{ error }}</p>
      <NButton size="small" @click="loadData">重新加载</NButton>
    </div>

    <!-- ===== Data loaded ===== -->
    <template v-else>
      <!-- ===== Bento grid: 4 cards ===== -->
      <section class="dashboard-grid">
        <!-- Card 1: Selection Overview (featured, spans 2 cols on desktop) -->
        <div class="glass-panel flex flex-col p-5 md:col-span-2">
          <div class="mb-4 flex items-center gap-2">
            <PhFunnel :size="15" class="text-[var(--color-accent)]" />
            <span class="metric-label">今日选股概览</span>
          </div>

          <template v-if="selectionSummary">
            <div class="mb-1 flex items-baseline gap-2">
              <span class="data-mono text-2xl font-bold text-[var(--color-text-primary)]">
                {{ selectionSummary.stock_count }}
              </span>
              <span class="text-sm text-[var(--color-text-muted)]">只候选</span>
            </div>
            <div class="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-sm">
              <div>
                <span class="text-[var(--color-text-muted)]">策略:</span>
                <span class="font-medium text-[var(--color-text-primary)]">
                  {{ selectionSummary.strategy_name }}
                </span>
              </div>
              <div>
                <span class="text-[var(--color-text-muted)]">均分:</span>
                <span class="data-mono text-[var(--color-text-primary)]">
                  {{ selectionSummary.avg_score.toFixed(2) }}
                </span>
              </div>
              <div>
                <span class="text-[var(--color-text-muted)]">最高:</span>
                <a
                  class="data-mono cursor-pointer text-[var(--color-accent)] hover:underline"
                  @click="router.push(`/stock/${selectionSummary.top_stock_code}`)"
                >
                  {{ selectionSummary.top_stock_code }}
                  ({{ selectionSummary.top_stock_score.toFixed(2) }})
                </a>
              </div>
              <div>
                <span class="text-[var(--color-text-muted)]">日期:</span>
                <span class="data-mono text-[var(--color-text-secondary)]">
                  {{ selectionSummary.trade_date }}
                </span>
              </div>
            </div>
            <button
              class="mt-auto cursor-pointer self-start pt-4 text-xs text-[var(--color-accent)] hover:underline"
              @click="router.push('/selection')"
            >
              查看完整结果 →
            </button>
          </template>

          <template v-else>
            <div class="flex flex-1 flex-col items-center justify-center py-6">
              <PhFunnel :size="32" class="mb-3 text-[var(--color-text-muted)] opacity-20" />
              <p class="mb-3 text-sm text-[var(--color-text-muted)]">暂无选股结果</p>
              <NButton size="small" type="primary" ghost @click="handleRunSelection">
                <template #icon><PhPlay :size="14" /></template>
                运行选股
              </NButton>
            </div>
          </template>
        </div>

        <!-- Card 2: Market Status -->
        <div class="glass-panel flex flex-col p-5">
          <div class="mb-4 flex items-center gap-2">
            <PhClock :size="15" class="text-[var(--color-accent)]" />
            <span class="metric-label">市场状态</span>
          </div>

          <div class="flex flex-col gap-3">
            <div>
              <div class="mb-1 text-xs text-[var(--color-text-muted)]">当前状态</div>
              <div class="flex items-center gap-2">
                <span
                  class="inline-block h-2 w-2 rounded-full"
                  :class="{
                    'animate-pulse bg-[var(--color-success)]': marketSession === 'trading',
                    'bg-[var(--color-text-muted)]': marketSession !== 'trading',
                  }"
                />
                <span class="text-sm font-medium text-[var(--color-text-primary)]">
                  {{ marketSessionLabel }}
                </span>
              </div>
            </div>

            <div v-if="nextTradingDay">
              <div class="mb-1 text-xs text-[var(--color-text-muted)]">下一交易日</div>
              <span class="data-mono text-sm text-[var(--color-text-primary)]">
                {{ nextTradingDay.date }}
              </span>
              <span class="ml-2 text-xs text-[var(--color-text-muted)]">
                ({{ nextTradingDay.daysAway }}天后)
              </span>
            </div>
          </div>
        </div>

        <!-- Card 3: Data Health -->
        <div class="glass-panel flex flex-col p-5 md:col-span-2">
          <div class="mb-4 flex items-center gap-2">
            <PhDatabase :size="15" class="text-[var(--color-accent)]" />
            <span class="metric-label">数据健康度</span>
          </div>

          <template v-if="dataHealth">
            <div class="grid grid-cols-3 gap-4">
              <!-- K-line date -->
              <div>
                <div class="mb-1 text-xs text-[var(--color-text-muted)]">K线数据</div>
                <div class="data-mono text-sm text-[var(--color-text-primary)]">
                  {{ dataHealth.kline_date || '—' }}
                </div>
              </div>
              <!-- Factor date -->
              <div>
                <div class="mb-1 text-xs text-[var(--color-text-muted)]">因子数据</div>
                <div class="data-mono text-sm text-[var(--color-text-primary)]">
                  {{ dataHealth.factor_date || '—' }}
                </div>
              </div>
              <!-- Coverage + freshness -->
              <div>
                <div class="mb-1 text-xs text-[var(--color-text-muted)]">覆盖率</div>
                <div class="flex items-center gap-2">
                  <span class="data-mono text-sm text-[var(--color-text-primary)]">
                    {{ dataHealth.kline_coverage_pct.toFixed(0) }}%
                  </span>
                  <NTag
                    v-if="dataHealth.is_stale"
                    type="warning"
                    size="tiny"
                    round
                    :bordered="false"
                  >
                    需更新
                  </NTag>
                  <NTag v-else type="success" size="tiny" round :bordered="false">已更新</NTag>
                </div>
              </div>
            </div>

            <!-- Staleness detail -->
            <div
              v-if="dataHealth.is_stale"
              class="mt-3 flex items-center gap-2 text-xs text-[var(--color-warning)]"
            >
              <PhWarning :size="13" />
              K线数据已落后 {{ dataHealth.stale_days }} 天，建议同步
              <button
                class="ml-1 cursor-pointer text-[var(--color-accent)] hover:underline"
                :disabled="syncRunning"
                @click="handleSyncData"
              >
                {{ syncRunning ? '同步中...' : '立即同步' }}
              </button>
            </div>
          </template>
        </div>

        <!-- Card 4: Stock count (compact) -->
        <div class="glass-panel flex flex-col p-5">
          <div class="mb-4 flex items-center gap-2">
            <PhChartLineUp :size="15" class="text-[var(--color-accent)]" />
            <span class="metric-label">股票覆盖</span>
          </div>
          <span class="data-mono text-3xl font-bold text-[var(--color-text-primary)]">
            {{ dataStatus?.stock_count ?? 0 }}
          </span>
          <span class="mt-1 text-xs text-[var(--color-text-muted)]">全市场 A股</span>
        </div>
      </section>

      <!-- ===== Strategy cards ===== -->
      <section>
        <div class="mb-3 flex items-baseline gap-3">
          <div class="flex items-center gap-2">
            <PhLightning :size="14" class="text-[var(--color-accent)]" />
            <span class="metric-label">策略列表</span>
          </div>
          <span class="data-mono ml-auto text-xs text-[var(--color-text-muted)]">
            {{ strategies.filter((s) => s.is_active).length }} / {{ strategies.length }} 活跃
          </span>
        </div>

        <div class="strategy-cards">
          <div
            v-for="card in strategyCards"
            :key="card.id"
            class="strategy-card glass-panel cursor-pointer p-4"
            @click="router.push(`/strategy/${card.id}`)"
          >
            <div class="mb-2 flex items-center justify-between">
              <span class="truncate text-sm font-medium text-[var(--color-text-primary)]">
                {{ card.display_name || card.name || card.id }}
              </span>
              <NTag
                :type="card.is_active ? 'success' : 'default'"
                size="tiny"
                round
                :bordered="false"
              >
                {{ card.is_active ? '活跃' : '停用' }}
              </NTag>
            </div>

            <div v-if="card.category" class="mb-3 text-xs text-[var(--color-text-muted)]">
              {{ card.category }}
            </div>

            <template v-if="card.backtest">
              <div class="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span class="text-[var(--color-text-muted)]">年化</span>
                  <div
                    class="data-mono font-medium"
                    :style="{
                      color:
                        (card.backtest.annual_return ?? 0) >= 0
                          ? 'var(--color-up)'
                          : 'var(--color-down)',
                    }"
                  >
                    {{
                      card.backtest.annual_return != null
                        ? (card.backtest.annual_return * 100).toFixed(1) + '%'
                        : '—'
                    }}
                  </div>
                </div>
                <div>
                  <span class="text-[var(--color-text-muted)]">回撤</span>
                  <div class="data-mono font-medium text-[var(--color-text-primary)]">
                    {{
                      card.backtest.max_drawdown != null
                        ? (card.backtest.max_drawdown * 100).toFixed(1) + '%'
                        : '—'
                    }}
                  </div>
                </div>
              </div>
            </template>
            <div v-else class="text-xs text-[var(--color-text-muted)]">暂无回测数据</div>
          </div>
        </div>
      </section>

      <!-- ===== Quick actions ===== -->
      <nav class="flex flex-wrap items-center gap-2">
        <button class="action-pill action-pill--primary" @click="handleRunSelection">
          <PhFunnel :size="15" weight="duotone" />
          <span>立即选股</span>
        </button>
        <button class="action-pill" :disabled="syncRunning" @click="handleSyncData">
          <PhArrowsClockwise :size="15" weight="duotone" :class="{ 'animate-spin': syncRunning }" />
          <span>{{ syncRunning ? '同步中...' : '同步数据' }}</span>
        </button>
        <button class="action-pill" @click="handleRunBacktest">
          <PhChartBar :size="15" weight="duotone" />
          <span>运行回测</span>
        </button>
        <button class="action-pill" @click="router.push('/strategy/list')">
          <PhSliders :size="15" weight="duotone" />
          <span>策略管理</span>
        </button>
      </nav>

      <!-- ===== Recent selection results table ===== -->
      <section>
        <div class="mb-4 flex items-baseline gap-3">
          <div class="flex flex-col gap-0.5">
            <span class="section-label">最近选股</span>
            <span class="text-lg font-semibold text-[var(--color-text-primary)]">选股明细</span>
          </div>
          <span
            v-if="recentResults.length > 0"
            class="data-mono ml-auto text-xs text-[var(--color-text-muted)]"
          >
            {{ recentResults.length }} 条
          </span>
        </div>

        <div
          v-if="recentResults.length === 0"
          class="glass-panel flex flex-col items-center justify-center py-16"
        >
          <PhFunnel :size="40" class="mb-4 text-[var(--color-text-muted)] opacity-20" />
          <p class="mb-4 text-sm text-[var(--color-text-muted)]">运行策略开始选股</p>
          <NButton size="small" type="primary" ghost @click="router.push('/selection')">
            <template #icon><PhArrowRight :size="14" /></template>
            前往选股
          </NButton>
        </div>

        <div v-else class="glass-panel overflow-hidden">
          <NDataTable
            :columns="recentColumns"
            :data="recentResults"
            :bordered="false"
            size="small"
            :single-line="false"
          />
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.metric-label {
  font-size: 0.6875rem;
  font-weight: 500;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-text-muted);
}

.section-label {
  font-size: 0.6875rem;
  font-weight: 500;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-text-muted);
}

/* Dashboard bento grid: 3 columns desktop, 2 tablet, 1 mobile */
.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
}

@media (max-width: 1199px) {
  .dashboard-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 767px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }
}

/* Strategy cards: horizontal scroll row */
.strategy-cards {
  display: flex;
  gap: 0.75rem;
  overflow-x: auto;
  padding-bottom: 4px;
  scrollbar-width: thin;
}

.strategy-card {
  min-width: 200px;
  max-width: 260px;
  flex-shrink: 0;
  transition: border-color 0.15s ease;
}

.strategy-card:hover {
  border-color: var(--color-accent);
}

/* Quick action pills */
.action-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border-radius: 9999px;
  border: 1px solid var(--color-border);
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 0.8125rem;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  transition:
    border-color 0.15s ease,
    color 0.15s ease,
    background-color 0.15s ease;
  font-family: inherit;
}

.action-pill:hover:not(:disabled) {
  border-color: var(--color-accent);
  color: var(--color-accent);
  background: var(--color-accent-muted);
}

.action-pill:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.action-pill--primary {
  background: var(--color-accent);
  border-color: var(--color-accent);
  color: var(--color-surface);
}

.action-pill--primary:hover {
  background: var(--color-accent-hover);
  border-color: var(--color-accent-hover);
  color: var(--color-surface);
}

/* Skeleton shimmer (preserved from original) */
.skeleton-line {
  height: 12px;
  border-radius: 6px;
  background: linear-gradient(
    90deg,
    var(--color-surface-inset) 0%,
    var(--color-border) 40%,
    var(--color-surface-inset) 80%
  );
  background-size: 200% 100%;
  animation: shimmer 1.6s ease-in-out infinite;
}

.skeleton-xl {
  height: 48px;
  border-radius: 8px;
}
.skeleton-lg {
  height: 24px;
  border-radius: 6px;
}
.skeleton-circle {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  flex-shrink: 0;
}
.skeleton-pill {
  height: 36px;
  width: 100px;
  border-radius: 9999px;
}
.skeleton-w4 {
  width: 16px;
}
.skeleton-w16 {
  width: 64px;
}
.skeleton-w20 {
  width: 80px;
}
.skeleton-w24 {
  width: 96px;
}
.skeleton-w32 {
  width: 128px;
}

@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
</style>
