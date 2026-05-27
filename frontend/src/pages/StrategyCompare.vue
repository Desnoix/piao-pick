<script setup lang="ts">
import { h, ref, computed, onMounted, watch } from 'vue'
import {
  NSelect,
  NButton,
  NSpace,
  NDataTable,
  NTag,
  NAlert,
  NSwitch,
  NSpin,
} from 'naive-ui'
import type { DataTableColumns } from 'naive-ui'
import { useRoute } from 'vue-router'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import {
  TooltipComponent,
  GridComponent,
  LegendComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import NavCurveChart from '../components/charts/NavCurveChart.vue'
import { useStrategyStore } from '../stores/strategy'
import { useChartTheme } from '../composables/use-chart-theme'
import { getStrategy } from '../api/strategies'
import type { Strategy, NavSeries, FactorWeight } from '../types/strategy'
import yaml from 'js-yaml'
import { FACTOR_LABELS } from '../utils/constants'

use([BarChart, TooltipComponent, GridComponent, LegendComponent, CanvasRenderer])

const route = useRoute()
const strategyStore = useStrategyStore()
const { theme } = useChartTheme()

const selectedIds = ref<string[]>([])
const loadingData = ref(false)
const logScale = ref(false)

interface StrategyCompareData {
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
  navSeries: NavSeries
}

const compareData = ref<StrategyCompareData[]>([])

const strategyOptions = computed(() =>
  strategyStore.strategies.map((s: Strategy) => ({
    label: s.display_name || s.name || s.id,
    value: s.id,
  }))
)

const mockDates = [
  '2023-01', '2023-03', '2023-05', '2023-07', '2023-09', '2023-11',
  '2024-01', '2024-03', '2024-05', '2024-07', '2024-09', '2024-11',
]

const benchmarkNav = [
  1.0, 0.98, 1.01, 0.99, 1.02, 1.04, 1.01, 1.06, 1.08, 1.05, 1.10, 1.12,
]

function generateMockNav(base: number, volatility: number): number[] {
  const nav = [1.0]
  let current = 1.0
  for (let i = 1; i < mockDates.length; i++) {
    const change = base + (Math.random() - 0.4) * volatility
    current = current * (1 + change)
    nav.push(parseFloat(current.toFixed(4)))
  }
  return nav
}

const metricsColumns: DataTableColumns<StrategyCompareData> = [
  {
    title: '指标',
    key: 'metric_name',
    width: 120,
    fixed: 'left',
  },
]

const tableData = computed(() => {
  if (compareData.value.length === 0) return []

  const metricDefs = [
    { key: 'annual_return', label: '年化收益率', fmt: (v: number) => `${(v * 100).toFixed(2)}%`, best: 'high' },
    { key: 'sharpe_ratio', label: '夏普比率', fmt: (v: number) => v.toFixed(2), best: 'high' },
    { key: 'max_drawdown', label: '最大回撤', fmt: (v: number) => `${(v * 100).toFixed(2)}%`, best: 'low' },
    { key: 'calmar_ratio', label: 'Calmar比率', fmt: (v: number) => v.toFixed(2), best: 'high' },
    { key: 'win_rate', label: '月度胜率', fmt: (v: number) => `${(v * 100).toFixed(1)}%`, best: 'high' },
    { key: 'avg_turnover', label: '平均换手率', fmt: (v: number) => `${(v * 100).toFixed(1)}%`, best: 'low' },
  ]

  return metricDefs.map((def) => {
    const values = compareData.value.map((d) => d.metrics[def.key as keyof typeof d.metrics])
    const bestVal = def.best === 'high' ? Math.max(...values) : Math.min(...values)

    const row: Record<string, string | number> = { metric_name: def.label }
    compareData.value.forEach((d, i) => {
      const val = d.metrics[def.key as keyof typeof d.metrics]
      const isBest = val === bestVal
      row[d.id] = def.fmt(val)
      row[`${d.id}_best`] = isBest ? 1 : 0
    })
    return row
  })
})

const dynamicColumns = computed(() => {
  const cols: DataTableColumns = [
    { title: '指标', key: 'metric_name', width: 120, fixed: 'left' },
  ]
  compareData.value.forEach((d) => {
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

const navSeriesData = computed<NavSeries[]>(() => {
  const series: NavSeries[] = compareData.value.map((d, i) => ({
    name: d.name,
    dates: d.navSeries.dates,
    values: d.navSeries.values,
    color: theme.value.color[i % theme.value.color.length],
  }))
  series.push({
    name: '沪深300',
    dates: mockDates,
    values: benchmarkNav,
    color: '#A1A1AA',
  })
  return series
})

const allFactorIds = computed(() => {
  const ids = new Set<string>()
  compareData.value.forEach((d) => {
    d.factors.forEach((f) => ids.add(f.id))
  })
  return Array.from(ids)
})

const factorBarOption = computed(() => {
  const factorIds = allFactorIds.value
  const strategyNames = compareData.value.map((d) => d.name)

  const series = factorIds.map((fid) => ({
    name: FACTOR_LABELS[fid] || fid,
    type: 'bar' as const,
    stack: 'total',
    emphasis: { focus: 'series' as const },
    data: compareData.value.map((d) => {
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
        formatter: (params: Array<{ seriesName: string; data: number; color: string }>) => {
        if (!Array.isArray(params) || params.length === 0) return ''
        let html = `<strong>${params[0].seriesName}</strong><br/>`
        params.forEach((p: { seriesName: string; data: number; color: string }) => {
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
    grid: {
      left: '12%',
      right: '5%',
      top: '15%',
      bottom: '5%',
    },
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

async function runCompare() {
  if (selectedIds.value.length < 2) return

  loadingData.value = true
  try {
    const results: StrategyCompareData[] = []

    for (let i = 0; i < selectedIds.value.length; i++) {
      const id = selectedIds.value[i]
      const detail = await getStrategy(id)
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
        // ignore parse errors for compare
      }

      const nav = generateMockNav(0.008 + i * 0.002, 0.03)
      const annualReturn = nav[nav.length - 1] / nav[0] - 1
      const maxDD = -0.05 - Math.random() * 0.15

      results.push({
        id,
        name: detail.display_name || detail.name || id,
        factors: parsedFactors,
        metrics: {
          annual_return: annualReturn,
          sharpe_ratio: 1.2 + Math.random() * 1.5,
          max_drawdown: maxDD,
          calmar_ratio: Math.abs(annualReturn / maxDD),
          win_rate: 0.5 + Math.random() * 0.2,
          avg_turnover: 0.05 + Math.random() * 0.15,
        },
        navSeries: {
          name: detail.display_name || detail.name || id,
          dates: mockDates,
          values: nav,
          color: theme.value.color[i % theme.value.color.length],
        },
      })
    }

    compareData.value = results
  } catch {
    compareData.value = []
  } finally {
    loadingData.value = false
  }
}

onMounted(async () => {
  await strategyStore.fetchStrategies()

  const qIds = route.query.ids
  if (qIds) {
    const ids = Array.isArray(qIds) ? qIds.map(String) : [String(qIds)]
    selectedIds.value = ids
    if (ids.length >= 2) {
      await runCompare()
    }
  }
})
</script>

<template>
  <div class="flex flex-col gap-6">
    <div class="flex items-center justify-between">
      <h2 class="text-xl font-bold text-[var(--color-text-primary)]">策略对比</h2>
    </div>

    <!-- Strategy Selector -->
    <div class="glass-panel p-5 flex items-end gap-3 flex-wrap">
      <div class="flex-1 min-w-[300px]">
        <div class="text-sm mb-1 text-[var(--color-text-secondary)]">选择策略 (2-4个)</div>
        <NSelect
          v-model:value="selectedIds"
          :options="strategyOptions"
          multiple
          :max-tag-count="4"
          placeholder="选择要对比的策略"
          :filterable="true"
        />
      </div>
      <NButton
        type="primary"
        :disabled="selectedIds.length < 2"
        @click="runCompare"
      >
        运行对比
      </NButton>
    </div>

    <NAlert v-if="selectedIds.length < 2" type="info">
      请选择至少 2 个策略进行对比
    </NAlert>

    <NSpin :show="loadingData">
      <template v-if="compareData.length > 0">
        <!-- NAV Curve Chart -->
        <div class="glass-panel p-5">
          <div class="flex items-center justify-between mb-2">
            <h3 class="text-lg font-bold text-[var(--color-text-primary)]">净值曲线对比</h3>
            <div class="flex items-center gap-2">
              <span class="text-sm text-[var(--color-text-secondary)]">对数坐标</span>
              <NSwitch v-model:value="logScale" size="small" />
            </div>
          </div>
          <NavCurveChart :series="navSeriesData" :log-scale="logScale" :height="420" />
        </div>

        <!-- Metrics Table -->
        <div class="glass-panel p-5">
          <h3 class="text-lg font-bold mb-2 text-[var(--color-text-primary)]">指标对比</h3>
          <NDataTable
            :columns="dynamicColumns"
            :data="tableData"
            size="small"
            striped
            :bordered="true"
          />
          <div class="text-xs text-[var(--color-text-muted)] mt-1">红色高亮表示该指标最优</div>
        </div>

        <!-- Factor Composition Diff -->
        <div class="glass-panel p-5">
          <h3 class="text-lg font-bold mb-2 text-[var(--color-text-primary)]">因子构成分布</h3>
          <div class="w-full h-[300px]">
            <VChart :option="factorBarOption" autoresize />
          </div>
        </div>
      </template>
    </NSpin>
  </div>
</template>
