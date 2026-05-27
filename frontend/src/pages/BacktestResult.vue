<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useRouter } from 'vue-router'
import { NDatePicker, NButton, NAlert, NSpace, NCard, NStatistic, NSpin } from 'naive-ui'
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

onMounted(async () => {
  await loadAvailableDates()
})

async function loadAvailableDates() {
  try {
    const dates = await getAvailableDates()
    availableDates.value = dates
    
    if (dates.start_date && dates.end_date) {
      // Set default date range: last 1 year
      const end = new Date(dates.end_date)
      const start = new Date(end)
      start.setFullYear(start.getFullYear() - 1)
      
      startDate.value = start.getTime()
      endDate.value = end.getTime()
    }
  } catch (e: any) {
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
  } catch (e: any) {
    console.error('Backtest failed:', e)
    error.value = e.response?.data?.error || e.message || '回测执行失败'
  } finally {
    loading.value = false
  }
}

// Computed properties for charts
const navData = computed(() => {
  if (!result.value) return null
  
  const dates = result.value.nav_series.map(([date, _]) => date)
  const strategyNav = result.value.nav_series.map(([_, nav]) => nav)
  
  return { dates, strategyNav }
})

const monthlyReturns = computed(() => {
  if (!result.value) return []
  // Convert returns (decimal) to percentage
  return result.value.returns.map(r => r * 100)
})

const yearlyHeatmapData = computed(() => {
  if (!result.value) return { data: [], years: [] }

  const returns = result.value.returns
  const years: string[] = []
  const yearMap: Record<string, number[]> = {}

  // Group returns by year
  result.value.nav_series.forEach((item, idx) => {
    if (idx === 0) return // Skip first item (initial NAV)
    const [dateStr] = item
    const year = dateStr.substring(0, 4)
    const month = parseInt(dateStr.substring(5, 7)) - 1

    if (!yearMap[year]) {
      yearMap[year] = new Array(12).fill(0)
      years.push(year)
    }

    yearMap[year][month] = returns[idx - 1] * 100
  })

  // Convert to heatmap format: [yearIdx, monthIdx, value]
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

function getReturnColor(value: number): string {
  return value >= 0 ? '#10b981' : '#ef4444'
}
</script>

<template>
  <div class="backtest-page">
    <div class="page-header">
      <n-button @click="router.back()" quaternary>← 返回</n-button>
      <h2>{{ strategyId }} 回测</h2>
    </div>

    <n-card class="config-card">
      <n-space align="center" :size="16">
        <n-space vertical :size="4">
          <span class="label">开始日期</span>
          <n-date-picker
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
        </n-space>

        <n-space vertical :size="4">
          <span class="label">结束日期</span>
          <n-date-picker
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
        </n-space>

        <n-button
          type="primary"
          @click="handleRunBacktest"
          :loading="loading"
          :disabled="!startDate || !endDate"
        >
          运行回测
        </n-button>
      </n-space>

      <n-alert v-if="availableDates && availableDates.trade_date_count > 0" type="info" :bordered="false" class="mt-3">
        可用日期范围: {{ availableDates.start_date }} 至 {{ availableDates.end_date }}
        (共 {{ availableDates.trade_date_count }} 个交易日)
      </n-alert>
    </n-card>

    <n-alert v-if="error" type="error" class="mt-4">
      {{ error }}
    </n-alert>

    <n-spin :show="loading" class="mt-4">
      <div v-if="result" class="results">
        <n-card class="metrics-card">
          <n-space :size="24" justify="space-around">
            <n-statistic label="总收益" :value="formatPercent(result.metrics.total_return)">
              <template #prefix>
                <span :style="{ color: getReturnColor(result.metrics.total_return) }">●</span>
              </template>
            </n-statistic>

            <n-statistic label="年化收益" :value="formatPercent(result.metrics.annual_return)">
              <template #prefix>
                <span :style="{ color: getReturnColor(result.metrics.annual_return) }">●</span>
              </template>
            </n-statistic>

            <n-statistic label="夏普比率" :value="formatNumber(result.metrics.sharpe_ratio)" />

            <n-statistic label="最大回撤" :value="formatPercent(result.metrics.max_drawdown)" />

            <n-statistic label="月度胜率" :value="formatPercent(result.metrics.monthly_win_rate)" />

            <n-statistic label="调仓次数" :value="result.period.rebalance_count" />
          </n-space>
        </n-card>

        <n-card v-if="navData" title="净值曲线" class="chart-card">
          <NavCurveChart
            :dates="navData.dates"
            :strategy-nav="navData.strategyNav"
          />
        </n-card>

        <n-card v-if="monthlyReturns.length > 0" title="月度收益分布" class="chart-card">
          <MonthlyDistribution :data="monthlyReturns" />
        </n-card>

        <n-card
          v-if="yearlyHeatmapData.data.length > 0"
          title="年度热力图"
          class="chart-card"
        >
          <YearlyHeatmap :data="yearlyHeatmapData.data" :years="yearlyHeatmapData.years" />
        </n-card>
      </div>
    </n-spin>
  </div>
</template>

<style scoped>
.backtest-page {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.page-header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}

.config-card {
  margin-bottom: 16px;
}

.label {
  font-size: 13px;
  color: var(--n-text-color-3);
}

.results {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.metrics-card {
  margin-bottom: 16px;
}

.chart-card {
  margin-bottom: 16px;
}

.mt-3 {
  margin-top: 12px;
}

.mt-4 {
  margin-top: 16px;
}
</style>
