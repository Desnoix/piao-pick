<script setup lang="ts">
import { h, ref, computed, onMounted } from 'vue'
import { NSelect, NButton, NDataTable, NAlert, NSwitch, NSpin } from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { useRoute } from 'vue-router'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { TooltipComponent, GridComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import NavCurveChart from '../components/charts/NavCurveChart.vue'
import type { ChartEvent } from '../components/charts/NavCurveChart.vue'
import DifferenceChart from '../components/charts/DifferenceChart.vue'
import { useStrategyStore } from '../stores/strategy'
import { useChartTheme } from '../composables/use-chart-theme'
import { getStrategy } from '../api/strategies'
import { runBacktest, getAvailableDates } from '../api/backtest'
import { alignNavSeries, computeNavDifference, filterByTimeRange } from '../utils/timeAlign'
import type { Strategy, StrategyDetail, FactorWeight } from '../types/strategy'
import yaml from 'js-yaml'
import { FACTOR_LABELS } from '../utils/constants'

use([BarChart, TooltipComponent, GridComponent, LegendComponent, CanvasRenderer])

const route = useRoute()
const strategyStore = useStrategyStore()
const { theme } = useChartTheme()

const MAX_STRATEGIES = 5
const selectedIds = ref<string[]>([])
const loadingData = ref(false)
const logScale = ref(false)
const progressMessage = ref('')
const compareError = ref('')
const timeRange = ref<'1Y' | '3Y' | '5Y' | 'ALL'>('ALL')
const diffTargetId = ref('')
const diffBaseId = ref('')

interface RawStrategyData {
  id: string
  name: string
  factors: FactorWeight[]
  metrics: {
    annual_return: number
    sharpe_ratio: number
    max_drawdown: number
    calmar_ratio: number
    win_rate: number
    avg_turnover: number
  }
  rawNav: [string, number][]
}

const rawData = ref<RawStrategyData[]>([])

// Aligned series: intersection range, monthly grid, forward-fill
const aligned = computed(() => {
  const inputs = rawData.value.map((d, i) => ({
    name: d.name,
    points: d.rawNav,
    color: theme.value.color[i % theme.value.color.length],
  }))
  return alignNavSeries(inputs)
})

// Time-range filtered view
const filtered = computed(() =>
  filterByTimeRange(aligned.value.dates, aligned.value.series, timeRange.value)
)

// Chart-ready NAV series (each shares the same dates array)
const navSeriesForChart = computed(() =>
  filtered.value.series.map((item) => ({
    name: item.name,
    dates: filtered.value.dates,
    values: item.values,
    color: item.color,
  }))
)

const strategyOptions = computed(() =>
  strategyStore.strategies.map((s: Strategy) => ({
    label: s.display_name || s.name || s.id,
    value: s.id,
    disabled: selectedIds.value.length >= MAX_STRATEGIES && !selectedIds.value.includes(s.id),
  }))
)

// Market events for markLine annotations
const marketEvents: ChartEvent[] = [
  { date: '2020-01-20', label: '新冠疫情', type: 'market' },
  { date: '2020-03-09', label: '美股熔断', type: 'market' },
  { date: '2022-02-24', label: '俄乌冲突', type: 'market' },
  { date: '2024-09-24', label: '9.24行情', type: 'market' },
]

// Difference chart: A vs B
const diffData = computed(() => {
  if (!diffTargetId.value || !diffBaseId.value) return null
  const ti = rawData.value.findIndex((d) => d.id === diffTargetId.value)
  const bi = rawData.value.findIndex((d) => d.id === diffBaseId.value)
  if (ti < 0 || bi < 0) return null
  const ts = filtered.value.series[ti]
  const bs = filtered.value.series[bi]
  if (!ts || !bs) return null
  return {
    targetName: rawData.value[ti].name,
    baseName: rawData.value[bi].name,
    values: computeNavDifference(bs.values, ts.values),
  }
})

const diffOptions = computed(() => rawData.value.map((d) => ({ label: d.name, value: d.id })))

// --- Metrics table ---
const tableData = computed(() => {
  if (rawData.value.length === 0) return []

  const metricDefs = [
    {
      key: 'annual_return',
      label: '年化收益率',
      fmt: (v: number) => `${(v * 100).toFixed(2)}%`,
      best: 'high',
    },
    { key: 'sharpe_ratio', label: '夏普比率', fmt: (v: number) => v.toFixed(2), best: 'high' },
    {
      key: 'max_drawdown',
      label: '最大回撤',
      fmt: (v: number) => `${(v * 100).toFixed(2)}%`,
      best: 'low',
    },
    { key: 'calmar_ratio', label: 'Calmar比率', fmt: (v: number) => v.toFixed(2), best: 'high' },
    {
      key: 'win_rate',
      label: '月度胜率',
      fmt: (v: number) => `${(v * 100).toFixed(1)}%`,
      best: 'high',
    },
    {
      key: 'avg_turnover',
      label: '平均换手率',
      fmt: (v: number) => `${(v * 100).toFixed(1)}%`,
      best: 'low',
    },
  ]

  return metricDefs.map((def) => {
    const values = rawData.value.map((d) => d.metrics[def.key as keyof typeof d.metrics])
    const bestVal = def.best === 'high' ? Math.max(...values) : Math.min(...values)

    const row: Record<string, string | number> = { metric_name: def.label }
    rawData.value.forEach((d) => {
      const val = d.metrics[def.key as keyof typeof d.metrics]
      const isBest = val === bestVal
      row[d.id] = def.fmt(val)
      row[`${d.id}_best`] = isBest ? 1 : 0
    })
    return row
  })
})

const dynamicColumns = computed<DataTableColumns>(() => {
  const cols: DataTableColumns = [{ title: '指标', key: 'metric_name', width: 120, fixed: 'left' }]
  rawData.value.forEach((d) => {
    cols.push({
      title: d.name,
      key: d.id,
      width: 150,
      render(row) {
        const rec = row as Record<string, unknown>
        const isBest = rec[`${d.id}_best`] === 1
        return h(
          'span',
          {
            class: `data-mono ${isBest ? 'text-[var(--color-up)] font-bold' : ''}`,
          },
          String(rec[d.id] ?? '')
        )
      },
    })
  })
  return cols
})

// Factor bar chart
const allFactorIds = computed(() => {
  const ids = new Set<string>()
  rawData.value.forEach((d) => {
    d.factors.forEach((f) => ids.add(f.id))
  })
  return Array.from(ids)
})

const factorBarOption = computed(() => {
  const factorIds = allFactorIds.value
  const strategyNames = rawData.value.map((d) => d.name)

  const series = factorIds.map((fid) => ({
    name: FACTOR_LABELS[fid] || fid,
    type: 'bar' as const,
    stack: 'total',
    emphasis: { focus: 'series' as const },
    data: rawData.value.map((d) => {
      const factor = d.factors.find((f) => f.id === fid)
      return factor ? factor.weight : 0
    }),
  }))

  return {
    animation: false,
    color: theme.value.color,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: theme.value.tooltip.backgroundColor,
      borderColor: theme.value.tooltip.borderColor,
      textStyle: theme.value.tooltip.textStyle,
      formatter: (params: Array<{ seriesName: string; data: number }>) => {
        if (!Array.isArray(params) || params.length === 0) return ''
        let html = `<strong>${params[0].seriesName}</strong><br/>`
        params.forEach((p: { seriesName: string; data: number }) => {
          if (p.data > 0) {
            html += `${p.seriesName}: ${p.data}%<br/>`
          }
        })
        return html
      },
    },
    legend: {
      data: factorIds.map((fid) => FACTOR_LABELS[fid] || fid),
      top: 0,
      type: 'scroll',
    },
    grid: { left: '12%', right: '5%', top: '15%', bottom: '5%' },
    xAxis: {
      type: 'value',
      axisLabel: { formatter: '{value}%' },
    },
    yAxis: {
      type: 'category',
      data: strategyNames,
    },
    series,
  }
})

// --- Core compare logic ---
async function runCompare() {
  if (selectedIds.value.length < 2) return

  loadingData.value = true
  compareError.value = ''
  progressMessage.value = '正在获取回测日期范围...'
  rawData.value = []

  try {
    const available = await getAvailableDates()
    if (!available.start_date || !available.end_date) {
      compareError.value = '无可用的回测日期范围, 请先在数据状态页同步历史数据'
      return
    }

    const results: RawStrategyData[] = []
    const errors: string[] = []

    for (let i = 0; i < selectedIds.value.length; i++) {
      const id = selectedIds.value[i]
      progressMessage.value = `正在回测第 ${i + 1}/${selectedIds.value.length} 个策略...`

      try {
        const [detail, bt] = await Promise.all([
          getStrategy(id),
          runBacktest({
            strategy_id: id,
            start_date: available.start_date,
            end_date: available.end_date,
          }),
        ])

        let parsedFactors: FactorWeight[] = []
        try {
          const parsed = yaml.load(detail.config) as Record<string, unknown>
          if (parsed && Array.isArray(parsed.factors)) {
            parsedFactors = parsed.factors.map((f: Record<string, unknown>) => ({
              id: String(f.id || ''),
              weight: Number(f.weight || 0),
              direction: (f.direction as 'positive' | 'negative') || 'positive',
              enabled: true,
            }))
          }
        } catch {
          /* YAML parse failed — keep empty factor list */
        }

        const displayName =
          (detail as StrategyDetail).display_name ||
          (detail as StrategyDetail).name ||
          bt.strategy_name ||
          id

        results.push({
          id,
          name: displayName,
          factors: parsedFactors,
          metrics: {
            annual_return: bt.metrics.annual_return,
            sharpe_ratio: bt.metrics.sharpe_ratio,
            max_drawdown: bt.metrics.max_drawdown,
            calmar_ratio: bt.metrics.calmar_ratio,
            win_rate: bt.metrics.monthly_win_rate,
            avg_turnover: bt.metrics.avg_turnover ?? 0,
          },
          rawNav: bt.nav_series,
        })
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err)
        errors.push(`策略 ${id} 回测失败: ${msg}`)
      }
    }

    if (errors.length > 0) {
      compareError.value = errors.join('; ')
    }
    rawData.value = results

    // Auto-select first two strategies for diff chart
    if (results.length >= 2) {
      diffTargetId.value = results[0].id
      diffBaseId.value = results[1].id
    }
  } catch (err: any) {
    // Ignore request cancellation errors (from request dedup mechanism in client.ts)
    if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return
    const msg = err instanceof Error ? err.message : String(err)
    compareError.value = msg
  } finally {
    loadingData.value = false
    progressMessage.value = ''
  }
}

onMounted(async () => {
  await strategyStore.fetchStrategies()

  const qIds = route.query.ids
  if (qIds) {
    const ids = Array.isArray(qIds) ? qIds.map(String) : [String(qIds)]
    selectedIds.value = ids.slice(0, MAX_STRATEGIES)
    if (ids.length >= 2) {
      await runCompare()
    }
  }
})
</script>

<template>
  <div class="flex flex-col gap-8">
    <!-- Strategy Selector Section -->
    <section>
      <span class="section-label">对比设置</span>
      <div class="glass-panel mt-3 flex flex-wrap items-end gap-3 p-5">
        <div class="min-w-[300px] flex-1">
          <div class="select-hint">选择策略 (2~5 个)</div>
          <NSelect
            v-model:value="selectedIds"
            :options="strategyOptions"
            multiple
            :max-tag-count="5"
            placeholder="选择要对比的策略"
            :filterable="true"
          />
        </div>
        <NButton type="primary" :disabled="selectedIds.length < 2" @click="runCompare">
          运行对比
        </NButton>
      </div>
    </section>

    <!-- Hint when not enough strategies selected -->
    <div v-if="selectedIds.length < 2" class="hint-banner">
      <span class="hint-dot" />
      请选择至少 2 个策略进行对比
    </div>

    <NAlert v-if="compareError" type="warning" :bordered="false" class="mb-4">
      {{ compareError }}
    </NAlert>

    <NSpin :show="loadingData" :description="progressMessage">
      <template v-if="rawData.length > 0">
        <div class="flex flex-col gap-8">
          <!-- NAV Curve -->
          <section>
            <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
              <span class="section-label">净值曲线</span>
              <div class="flex items-center gap-3">
                <div class="flex gap-1">
                  <NButton
                    v-for="r in ['1Y', '3Y', '5Y', 'ALL'] as const"
                    :key="r"
                    :type="timeRange === r ? 'primary' : 'default'"
                    size="small"
                    secondary
                    @click="timeRange = r"
                  >
                    {{ r === 'ALL' ? '全部' : r }}
                  </NButton>
                </div>
                <div class="toggle-group">
                  <span class="toggle-label">对数</span>
                  <NSwitch v-model:value="logScale" size="small" />
                </div>
              </div>
            </div>

            <!-- Empty intersection fallback -->
            <div
              v-if="navSeriesForChart.length === 0 || filtered.dates.length === 0"
              class="glass-panel p-8 text-center"
            >
              <p class="text-sm text-[var(--color-text-muted)]">
                所选策略的回测时间段无交集，无法进行对比。
              </p>
            </div>
            <div v-else class="glass-panel p-5">
              <NavCurveChart
                :series="navSeriesForChart"
                :log-scale="logScale"
                :height="420"
                :events="marketEvents"
                :show-data-zoom="true"
              />
            </div>
          </section>

          <!-- Difference Chart (shown when 2+ strategies loaded) -->
          <section v-if="rawData.length >= 2">
            <span class="section-label">累计收益差</span>
            <div class="glass-panel mt-3 flex flex-col gap-3 p-5">
              <div class="flex flex-wrap items-center gap-3">
                <NSelect
                  v-model:value="diffTargetId"
                  :options="diffOptions"
                  placeholder="策略 A"
                  class="diff-select"
                />
                <span class="text-sm text-[var(--color-text-muted)]">相对</span>
                <NSelect
                  v-model:value="diffBaseId"
                  :options="diffOptions"
                  placeholder="策略 B"
                  class="diff-select"
                />
              </div>
              <DifferenceChart
                v-if="diffData && filtered.dates.length > 0"
                :dates="filtered.dates"
                :diff-values="diffData.values"
                :target-name="diffData.targetName"
                :base-name="diffData.baseName"
                :height="280"
              />
            </div>
          </section>

          <!-- Metrics Table -->
          <section>
            <span class="section-label">指标对比</span>
            <div class="glass-panel mt-3 overflow-hidden p-5">
              <NDataTable
                :columns="dynamicColumns"
                :data="tableData"
                size="small"
                striped
                :bordered="true"
              />
              <div class="metrics-note">红色高亮表示该指标最优</div>
            </div>
          </section>

          <!-- Factor Composition -->
          <section>
            <span class="section-label">因子构成</span>
            <div class="glass-panel mt-3 p-5">
              <div class="h-[300px] w-full">
                <VChart :option="factorBarOption" autoresize />
              </div>
            </div>
          </section>
        </div>
      </template>
    </NSpin>
  </div>
</template>

<style scoped>
.section-label {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.06em;
  color: var(--color-text-muted);
}

.select-hint {
  font-size: 12px;
  color: var(--color-text-muted);
  margin-bottom: 6px;
}

.hint-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 8px;
  background: var(--color-surface-elevated);
  border: 1px solid var(--color-border);
  font-size: 13px;
  color: var(--color-text-muted);
}

.hint-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-accent);
  flex-shrink: 0;
}

.toggle-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toggle-label {
  font-size: 12px;
  color: var(--color-text-muted);
}

.metrics-note {
  font-size: 11px;
  color: var(--color-text-muted);
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid var(--color-glass-highlight);
}

.diff-select {
  width: 160px;
}
</style>
