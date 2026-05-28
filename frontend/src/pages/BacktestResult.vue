<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useRouter } from 'vue-router'
import { NDatePicker, NButton, NStatistic, NSpin } from 'naive-ui'
import { PhArrowLeft } from '@phosphor-icons/vue'
import NavCurveChart from '../components/charts/NavCurveChart.vue'
import MonthlyDistribution from '../components/charts/MonthlyDistribution.vue'
import YearlyHeatmap from '../components/charts/YearlyHeatmap.vue'
import DrawdownChart from '../components/charts/DrawdownChart.vue'
import BenchmarkCompare from '../components/charts/BenchmarkCompare.vue'
import MonthlyReturnTable from '../components/charts/MonthlyReturnTable.vue'
import RollingSharpe from '../components/charts/RollingSharpe.vue'
import { runBacktest, getAvailableDates } from '../api/backtest'
import type { BacktestRunResponse, AvailableDates } from '../types/backtest'

const route = useRoute()
const router = useRouter()
const strategyId = route.params.strategyId as string

const loading = ref(false)
const error = ref<string | null>(null)
const result = ref<BacktestRunResponse | null>(null)

const startDate = ref<number>(0)
const endDate = ref<number>(0)
const availableDates = ref<AvailableDates | null>(null)

const monoValueStyle = { fontFamily: 'var(--font-mono)', fontVariantNumeric: 'tabular-nums' }

onMounted(async () => {
  await loadAvailableDates()
})

async function loadAvailableDates() {
  try {
    const dates = await getAvailableDates()
    availableDates.value = dates

    if (dates.start_date && dates.end_date) {
      const end = new Date(dates.end_date)
      const start = new Date(end)
      start.setFullYear(start.getFullYear() - 1)

      startDate.value = start.getTime()
      endDate.value = end.getTime()
    }
  } catch {
    // 拦截器已统一提示
  }
}

async function handleRunBacktest() {
  if (!startDate.value || !endDate.value) {
    error.value = '请选择开始和结束日期'
    return
  }

  loading.value = true
  error.value = null
  result.value = null

  try {
    const start = new Date(startDate.value).toISOString().split('T')[0]
    const end = new Date(endDate.value).toISOString().split('T')[0]

    const response = await runBacktest(
      {
        strategy_id: strategyId,
        start_date: start,
        end_date: end,
      },
      { silent: true }
    )

    result.value = response
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } }; message?: string }
    error.value = err?.response?.data?.detail || err?.message || '回测执行失败'
  } finally {
    loading.value = false
  }
}

const navData = computed(() => {
  if (!result.value) return null

  const dates = result.value.nav_series.map(([date, _]) => date)
  const strategyNav = result.value.nav_series.map(([_, nav]) => nav)

  // 基准 NAV (归一化后，与策略同日期对齐)
  let benchmarkNav: number[] | undefined = undefined
  if (result.value.benchmark_nav && result.value.benchmark_nav.length > 0) {
    const bmMap = new Map(result.value.benchmark_nav)
    benchmarkNav = dates.map((d) => bmMap.get(d) ?? null).filter((v): v is number => v !== null)
    // 如果长度不匹配，放弃基准线
    if (benchmarkNav.length !== dates.length) {
      benchmarkNav = undefined
    }
  }

  return { dates, strategyNav, benchmarkNav }
})

const monthlyReturns = computed(() => {
  if (!result.value) return []
  return result.value.returns.map((r) => r * 100)
})

const yearlyHeatmapData = computed(() => {
  if (!result.value) return { data: [], years: [] }

  const returns = result.value.returns
  const years: string[] = []
  const yearMap: Record<string, number[]> = {}

  result.value.nav_series.forEach((item, idx) => {
    if (idx === 0) return
    const [dateStr] = item
    const year = dateStr.substring(0, 4)
    const month = parseInt(dateStr.substring(5, 7)) - 1

    if (!yearMap[year]) {
      yearMap[year] = new Array(12).fill(0)
      years.push(year)
    }

    yearMap[year][month] = returns[idx - 1] * 100
  })

  const data: [number, number, number][] = []
  years.forEach((year, yearIdx) => {
    for (let monthIdx = 0; monthIdx < 12; monthIdx++) {
      const value = yearMap[year][monthIdx]
      if (value !== 0) {
        data.push([yearIdx, monthIdx, value])
      }
    }
  })

  return { data, years }
})

const drawdownData = computed(() => {
  if (!result.value) return null
  const series = result.value.nav_series
  const dates: string[] = []
  const drawdown: number[] = []
  let peak = series[0][1]
  for (const [date, nav] of series) {
    if (nav > peak) peak = nav
    dates.push(date)
    drawdown.push((nav - peak) / peak)
  }
  return { dates, drawdown }
})

const benchmarkData = computed(() => {
  if (!result.value) return null
  const series = result.value.nav_series
  const dates = series.map(([d]) => d)
  const strategyNav = series.map(([, n]) => n)
  // benchmark_nav is [string, number][] — align by date
  let benchmarkNav: number[] = []
  if (result.value.benchmark_nav && result.value.benchmark_nav.length > 0) {
    const bmMap = new Map(result.value.benchmark_nav)
    benchmarkNav = dates.map((d) => bmMap.get(d) ?? null).filter((v): v is number => v !== null)
    if (benchmarkNav.length !== dates.length) {
      benchmarkNav = []
    }
  }
  return { dates, strategyNav, benchmarkNav }
})

const monthlyMatrixData = computed(() => {
  if (!result.value) return null
  const returns = result.value.returns
  const series = result.value.nav_series
  const years: number[] = []
  const matrix: Record<number, number[]> = {}

  series.forEach((item, idx) => {
    if (idx === 0) return
    const year = parseInt(item[0].substring(0, 4))
    const month = parseInt(item[0].substring(5, 7)) - 1
    if (!matrix[year]) {
      matrix[year] = new Array(12).fill(NaN)
      years.push(year)
    }
    matrix[year][month] = returns[idx - 1] * 100
  })

  return { years, matrix }
})

const rollingSharpeData = computed(() => {
  if (!result.value) return null
  const returns = result.value.returns
  const series = result.value.nav_series
  const dates: string[] = []
  const values: number[] = []
  const window = 252

  for (let i = window; i < returns.length; i++) {
    const slice = returns.slice(i - window, i)
    const mean = slice.reduce((a, b) => a + b, 0) / slice.length
    const variance = slice.reduce((a, b) => a + (b - mean) ** 2, 0) / slice.length
    const std = Math.sqrt(variance)
    const annualizedReturn = mean * 252
    const annualizedStd = std * Math.sqrt(252)
    const sharpe = annualizedStd === 0 ? 0 : annualizedReturn / annualizedStd
    dates.push(series[i][0])
    values.push(sharpe)
  }
  return { dates, values }
})

function formatPercent(value: number | undefined): string {
  if (value === undefined || value === null) return '-'
  return `${(value * 100).toFixed(2)}%`
}

function formatNumber(value: number | undefined): string {
  if (value === undefined || value === null) return '-'
  return value.toFixed(2)
}
</script>

<template>
  <div class="flex flex-col gap-8">
    <!-- Header: breadcrumb + strategy name -->
    <header class="flex flex-wrap items-center gap-3">
      <button
        class="back-btn -mx-2 inline-flex min-h-[44px] cursor-pointer items-center gap-1.5 rounded-lg px-2 text-sm text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-text-primary)] active:bg-[var(--color-surface-inset)]"
        @click="router.back()"
      >
        <PhArrowLeft :size="16" />
        返回
      </button>
      <span class="h-4 w-px bg-[var(--color-border-muted)]"></span>
      <span class="text-lg font-semibold text-[var(--color-text-primary)]">{{ strategyId }}</span>
    </header>

    <!-- Config section -->
    <section>
      <div class="mb-4 flex flex-col gap-0.5">
        <span class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]">
          回测参数
        </span>
        <span class="text-lg font-semibold text-[var(--color-text-primary)]">配置区间</span>
      </div>
      <div class="glass-panel p-5">
        <div class="flex flex-wrap items-end gap-4">
          <div class="flex flex-col gap-1.5">
            <span class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]">
              开始日期
            </span>
            <NDatePicker
              v-model:value="startDate"
              type="date"
              clearable
              :is-date-disabled="
                (date: number) => {
                  if (!availableDates?.start_date || !availableDates?.end_date) return false
                  const min = new Date(availableDates.start_date).getTime()
                  const max = new Date(availableDates.end_date).getTime()
                  return date < min || date > max
                }
              "
            />
          </div>

          <div class="flex flex-col gap-1.5">
            <span class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]">
              结束日期
            </span>
            <NDatePicker
              v-model:value="endDate"
              type="date"
              clearable
              :is-date-disabled="
                (date: number) => {
                  if (!availableDates?.start_date || !availableDates?.end_date) return false
                  const min = new Date(availableDates.start_date).getTime()
                  const max = new Date(availableDates.end_date).getTime()
                  return date < min || date > max
                }
              "
            />
          </div>

          <NButton
            type="primary"
            @click="handleRunBacktest"
            :loading="loading"
            :disabled="!startDate || !endDate"
          >
            运行回测
          </NButton>
        </div>

        <div
          v-if="availableDates && availableDates.trade_date_count > 0"
          class="mt-4 rounded-lg bg-[var(--color-surface-inset)] p-3 text-sm text-[var(--color-text-secondary)]"
        >
          可用日期范围: {{ availableDates.start_date }} 至 {{ availableDates.end_date }}
          <span class="text-[var(--color-text-muted)]">
            (共 {{ availableDates.trade_date_count }} 个交易日)
          </span>
        </div>
      </div>
    </section>

    <!-- Error banner -->
    <div v-if="error" class="flex overflow-hidden rounded-lg">
      <div class="w-1 flex-shrink-0 bg-[var(--color-error)]"></div>
      <div
        class="flex-1 bg-[rgba(239,68,68,0.06)] px-4 py-3 text-sm text-[var(--color-text-primary)]"
      >
        {{ error }}
      </div>
    </div>

    <!-- Results -->
    <NSpin :show="loading">
      <div v-if="result" class="flex flex-col gap-8">
        <!-- Core metrics -->
        <section>
          <div class="mb-4 flex flex-col gap-0.5">
            <span class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]">
              核心指标
            </span>
            <span class="text-lg font-semibold text-[var(--color-text-primary)]">回测表现</span>
          </div>
          <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
            <div class="glass-panel flex flex-col gap-2 p-5">
              <span
                class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]"
              >
                总收益
              </span>
              <span
                class="data-mono text-3xl leading-tight font-bold"
                :class="result.metrics.total_return >= 0 ? 'text-up' : 'text-down'"
              >
                {{ formatPercent(result.metrics.total_return) }}
              </span>
            </div>

            <div class="glass-panel flex flex-col gap-2 p-5">
              <span
                class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]"
              >
                年化收益
              </span>
              <span
                class="data-mono text-3xl leading-tight font-bold"
                :class="result.metrics.annual_return >= 0 ? 'text-up' : 'text-down'"
              >
                {{ formatPercent(result.metrics.annual_return) }}
              </span>
            </div>

            <div class="glass-panel flex flex-col gap-2 p-5">
              <span
                class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]"
              >
                夏普比率
              </span>
              <span
                class="data-mono text-3xl leading-tight font-bold text-[var(--color-text-primary)]"
              >
                {{ formatNumber(result.metrics.sharpe_ratio) }}
              </span>
            </div>

            <div class="glass-panel flex flex-col gap-2 p-5">
              <span
                class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]"
              >
                最大回撤
              </span>
              <span class="data-mono text-down text-3xl leading-tight font-bold">
                {{ formatPercent(result.metrics.max_drawdown) }}
              </span>
            </div>

            <div class="glass-panel flex flex-col gap-2 p-5">
              <span
                class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]"
              >
                月度胜率
              </span>
              <span
                class="data-mono text-3xl leading-tight font-bold text-[var(--color-text-primary)]"
              >
                {{ formatPercent(result.metrics.monthly_win_rate) }}
              </span>
            </div>

            <div class="glass-panel flex flex-col gap-2 p-5">
              <span
                class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]"
              >
                调仓次数
              </span>
              <span
                class="data-mono text-3xl leading-tight font-bold text-[var(--color-text-primary)]"
              >
                {{ result.period.rebalance_count }}
              </span>
            </div>
          </div>

          <!-- 基准对比 (沪深 300) 指标卡片 -->
          <div
            v-if="result.metrics.alpha !== undefined"
            class="glass-panel mt-3 flex flex-col gap-2 p-5"
          >
            <span class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]">
              基准对比 (沪深 300)
            </span>
            <div class="mt-1 grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-5">
              <div class="flex flex-col gap-1">
                <span class="text-[11px] text-[var(--color-text-muted)]">超额收益 (年化)</span>
                <span
                  class="data-mono text-xl font-bold"
                  :class="(result.metrics.excess_return ?? 0) >= 0 ? 'text-up' : 'text-down'"
                >
                  {{ formatPercent(result.metrics.excess_return) }}
                </span>
              </div>
              <div class="flex flex-col gap-1">
                <span class="text-[11px] text-[var(--color-text-muted)]">Alpha</span>
                <span
                  class="data-mono text-xl font-bold"
                  :class="(result.metrics.alpha ?? 0) >= 0 ? 'text-up' : 'text-down'"
                >
                  {{ formatPercent(result.metrics.alpha) }}
                </span>
              </div>
              <div class="flex flex-col gap-1">
                <span class="text-[11px] text-[var(--color-text-muted)]">Beta</span>
                <span class="data-mono text-xl font-bold text-[var(--color-text-primary)]">
                  {{ formatNumber(result.metrics.beta) }}
                </span>
              </div>
              <div class="flex flex-col gap-1">
                <span class="text-[11px] text-[var(--color-text-muted)]">信息比率</span>
                <span class="data-mono text-xl font-bold text-[var(--color-text-primary)]">
                  {{ formatNumber(result.metrics.information_ratio) }}
                </span>
              </div>
              <div class="flex flex-col gap-1">
                <span class="text-[11px] text-[var(--color-text-muted)]">跟踪误差</span>
                <span class="data-mono text-xl font-bold text-[var(--color-text-primary)]">
                  {{ formatPercent(result.metrics.tracking_error) }}
                </span>
              </div>
            </div>
          </div>
        </section>

        <!-- Nav curve chart -->
        <section v-if="navData">
          <div class="mb-4 flex flex-col gap-0.5">
            <span class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]">
              净值曲线
            </span>
            <span class="text-lg font-semibold text-[var(--color-text-primary)]">走势对比</span>
          </div>
          <div class="glass-panel p-5">
            <NavCurveChart
              :dates="navData.dates"
              :strategy-nav="navData.strategyNav"
              :benchmark-nav="navData.benchmarkNav"
            />
          </div>
        </section>

        <!-- Monthly distribution -->
        <section v-if="monthlyReturns.length > 0">
          <div class="mb-4 flex flex-col gap-0.5">
            <span class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]">
              月度收益分布
            </span>
            <span class="text-lg font-semibold text-[var(--color-text-primary)]">收益拆解</span>
          </div>
          <div class="glass-panel p-5">
            <MonthlyDistribution :data="monthlyReturns" />
          </div>
        </section>

        <!-- Yearly heatmap -->
        <section v-if="yearlyHeatmapData.data.length > 0">
          <div class="mb-4 flex flex-col gap-0.5">
            <span class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]">
              年度热力图
            </span>
            <span class="text-lg font-semibold text-[var(--color-text-primary)]">月度收益一览</span>
          </div>
          <div class="glass-panel p-5">
            <YearlyHeatmap :data="yearlyHeatmapData.data" :years="yearlyHeatmapData.years" />
          </div>
        </section>

        <!-- Benchmark comparison -->
        <section v-if="benchmarkData">
          <div class="mb-4 flex flex-col gap-0.5">
            <span class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]">
              基准对比
            </span>
            <span class="text-lg font-semibold text-[var(--color-text-primary)]">
              策略 vs 沪深300
            </span>
          </div>
          <div class="glass-panel p-5">
            <BenchmarkCompare
              :dates="benchmarkData.dates"
              :strategy-nav="benchmarkData.strategyNav"
              :benchmark-nav="benchmarkData.benchmarkNav"
            />
          </div>
        </section>

        <!-- Drawdown chart -->
        <section v-if="drawdownData">
          <div class="mb-4 flex flex-col gap-0.5">
            <span class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]">
              回撤分析
            </span>
            <span class="text-lg font-semibold text-[var(--color-text-primary)]">水下曲线</span>
          </div>
          <div class="glass-panel p-5">
            <DrawdownChart :dates="drawdownData.dates" :drawdown="drawdownData.drawdown" />
          </div>
        </section>

        <!-- Monthly return table -->
        <section v-if="monthlyMatrixData">
          <div class="mb-4 flex flex-col gap-0.5">
            <span class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]">
              月度收益矩阵
            </span>
            <span class="text-lg font-semibold text-[var(--color-text-primary)]">逐年月度一览</span>
          </div>
          <div class="glass-panel p-5">
            <MonthlyReturnTable
              :years="monthlyMatrixData.years"
              :matrix="monthlyMatrixData.matrix"
            />
          </div>
        </section>

        <!-- Rolling Sharpe -->
        <section v-if="rollingSharpeData && rollingSharpeData.values.length > 0">
          <div class="mb-4 flex flex-col gap-0.5">
            <span class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]">
              滚动夏普
            </span>
            <span class="text-lg font-semibold text-[var(--color-text-primary)]">
              12 月窗口滚动夏普比率
            </span>
          </div>
          <div class="glass-panel p-5">
            <RollingSharpe :dates="rollingSharpeData.dates" :values="rollingSharpeData.values" />
          </div>
        </section>
      </div>
    </NSpin>
  </div>
</template>

<style scoped>
/* Touch-friendly back button */
.back-btn {
  -webkit-tap-highlight-color: transparent;
}

/* Responsive config flex-wrap on small screens */
@media (max-width: 640px) {
  .glass-panel > .flex.items-end {
    flex-direction: column;
    align-items: stretch;
  }
}

/* Touch: disable sticky hover on touch devices */
@media (hover: none) {
  .back-btn:hover {
    color: var(--color-text-muted);
  }
}
</style>
