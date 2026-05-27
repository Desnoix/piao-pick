<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useRouter } from 'vue-router'
import { NDatePicker, NButton, NStatistic, NSpin } from 'naive-ui'
import { PhArrowLeft } from '@phosphor-icons/vue'
import NavCurveChart from '../components/charts/NavCurveChart.vue'
import MonthlyDistribution from '../components/charts/MonthlyDistribution.vue'
import YearlyHeatmap from '../components/charts/YearlyHeatmap.vue'
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
  } catch (e: unknown) {
    console.error('Failed to load available dates:', e)
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

    const response = await runBacktest({
      strategy_id: strategyId,
      start_date: start,
      end_date: end,
    })

    result.value = response
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } }; message?: string }
    console.error('Backtest failed:', e)
    error.value = err.response?.data?.error || err.message || '回测执行失败'
  } finally {
    loading.value = false
  }
}

const navData = computed(() => {
  if (!result.value) return null
  
  const dates = result.value.nav_series.map(([date, _]) => date)
  const strategyNav = result.value.nav_series.map(([_, nav]) => nav)
  
  return { dates, strategyNav }
})

const monthlyReturns = computed(() => {
  if (!result.value) return []
  return result.value.returns.map(r => r * 100)
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
    <header class="flex items-center gap-3">
      <button
        class="inline-flex items-center gap-1.5 text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] transition-colors cursor-pointer"
        @click="router.back()"
      >
        <PhArrowLeft :size="16" />
        返回
      </button>
      <span class="w-px h-4 bg-[var(--color-border-muted)]"></span>
      <span class="text-lg font-semibold text-[var(--color-text-primary)]">{{ strategyId }}</span>
    </header>

    <!-- Config section -->
    <section>
      <div class="flex flex-col gap-0.5 mb-4">
        <span class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]">回测参数</span>
        <span class="text-lg font-semibold text-[var(--color-text-primary)]">配置区间</span>
      </div>
      <div class="glass-panel p-5">
        <div class="flex items-end gap-4 flex-wrap">
          <div class="flex flex-col gap-1.5">
            <span class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]">开始日期</span>
            <NDatePicker
              v-model:value="startDate"
              type="date"
              clearable
              :is-date-disabled="(date: number) => {
                if (!availableDates?.start_date || !availableDates?.end_date) return false
                const min = new Date(availableDates.start_date).getTime()
                const max = new Date(availableDates.end_date).getTime()
                return date < min || date > max
              }"
            />
          </div>

          <div class="flex flex-col gap-1.5">
            <span class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]">结束日期</span>
            <NDatePicker
              v-model:value="endDate"
              type="date"
              clearable
              :is-date-disabled="(date: number) => {
                if (!availableDates?.start_date || !availableDates?.end_date) return false
                const min = new Date(availableDates.start_date).getTime()
                const max = new Date(availableDates.end_date).getTime()
                return date < min || date > max
              }"
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
          class="mt-4 bg-[var(--color-surface-inset)] rounded-lg p-3 text-sm text-[var(--color-text-secondary)]"
        >
          可用日期范围: {{ availableDates.start_date }} 至 {{ availableDates.end_date }}
          <span class="text-[var(--color-text-muted)]">(共 {{ availableDates.trade_date_count }} 个交易日)</span>
        </div>
      </div>
    </section>

    <!-- Error banner -->
    <div
      v-if="error"
      class="flex rounded-lg overflow-hidden"
    >
      <div class="w-1 bg-[var(--color-error)] flex-shrink-0"></div>
      <div class="flex-1 px-4 py-3 text-sm bg-[rgba(239,68,68,0.06)] text-[var(--color-text-primary)]">
        {{ error }}
      </div>
    </div>

    <!-- Results -->
    <NSpin :show="loading">
      <div v-if="result" class="flex flex-col gap-8">
        <!-- Core metrics -->
        <section>
          <div class="flex flex-col gap-0.5 mb-4">
            <span class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]">核心指标</span>
            <span class="text-lg font-semibold text-[var(--color-text-primary)]">回测表现</span>
          </div>
          <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
            <div class="glass-panel p-5 flex flex-col gap-2">
              <span class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]">总收益</span>
              <span
                class="text-3xl font-bold data-mono leading-tight"
                :class="result.metrics.total_return >= 0 ? 'text-up' : 'text-down'"
              >
                {{ formatPercent(result.metrics.total_return) }}
              </span>
            </div>

            <div class="glass-panel p-5 flex flex-col gap-2">
              <span class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]">年化收益</span>
              <span
                class="text-3xl font-bold data-mono leading-tight"
                :class="result.metrics.annual_return >= 0 ? 'text-up' : 'text-down'"
              >
                {{ formatPercent(result.metrics.annual_return) }}
              </span>
            </div>

            <div class="glass-panel p-5 flex flex-col gap-2">
              <span class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]">夏普比率</span>
              <span class="text-3xl font-bold data-mono leading-tight text-[var(--color-text-primary)]">
                {{ formatNumber(result.metrics.sharpe_ratio) }}
              </span>
            </div>

            <div class="glass-panel p-5 flex flex-col gap-2">
              <span class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]">最大回撤</span>
              <span class="text-3xl font-bold data-mono leading-tight text-down">
                {{ formatPercent(result.metrics.max_drawdown) }}
              </span>
            </div>

            <div class="glass-panel p-5 flex flex-col gap-2">
              <span class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]">月度胜率</span>
              <span class="text-3xl font-bold data-mono leading-tight text-[var(--color-text-primary)]">
                {{ formatPercent(result.metrics.monthly_win_rate) }}
              </span>
            </div>

            <div class="glass-panel p-5 flex flex-col gap-2">
              <span class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]">调仓次数</span>
              <span class="text-3xl font-bold data-mono leading-tight text-[var(--color-text-primary)]">
                {{ result.period.rebalance_count }}
              </span>
            </div>
          </div>
        </section>

        <!-- Nav curve chart -->
        <section v-if="navData">
          <div class="flex flex-col gap-0.5 mb-4">
            <span class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]">净值曲线</span>
            <span class="text-lg font-semibold text-[var(--color-text-primary)]">走势对比</span>
          </div>
          <div class="glass-panel p-5">
            <NavCurveChart
              :dates="navData.dates"
              :strategy-nav="navData.strategyNav"
            />
          </div>
        </section>

        <!-- Monthly distribution -->
        <section v-if="monthlyReturns.length > 0">
          <div class="flex flex-col gap-0.5 mb-4">
            <span class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]">月度收益分布</span>
            <span class="text-lg font-semibold text-[var(--color-text-primary)]">收益拆解</span>
          </div>
          <div class="glass-panel p-5">
            <MonthlyDistribution :data="monthlyReturns" />
          </div>
        </section>

        <!-- Yearly heatmap -->
        <section v-if="yearlyHeatmapData.data.length > 0">
          <div class="flex flex-col gap-0.5 mb-4">
            <span class="text-[11px] font-medium tracking-[0.06em] text-[var(--color-text-muted)]">年度热力图</span>
            <span class="text-lg font-semibold text-[var(--color-text-primary)]">月度收益一览</span>
          </div>
          <div class="glass-panel p-5">
            <YearlyHeatmap :data="yearlyHeatmapData.data" :years="yearlyHeatmapData.years" />
          </div>
        </section>
      </div>
    </NSpin>
  </div>
</template>
