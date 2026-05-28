<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  DataZoomComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { NavSeries } from '../../types/strategy'
import { useChartTheme } from '../../composables/use-chart-theme'

export interface ChartEvent {
  date: string
  label: string
  type: 'rebalance' | 'market'
}

use([
  LineChart,
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  DataZoomComponent,
  CanvasRenderer,
])

const { theme } = useChartTheme()

const props = defineProps<{
  dates?: string[]
  strategyNav?: number[]
  benchmarkNav?: number[]
  series?: NavSeries[]
  logScale?: boolean
  height?: number
  events?: ChartEvent[]
  showDataZoom?: boolean
}>()

const option = computed(() => {
  if (props.series && props.series.length > 0) {
    return buildMultiSeriesOption()
  }
  return buildLegacyOption()
})

function buildLegacyOption() {
  const hasBenchmark = props.benchmarkNav && props.benchmarkNav.length > 0
  const legendData = hasBenchmark ? ['策略净值', '沪深300', '超额收益'] : ['策略净值']

  // 计算超额收益序列: strategy - benchmark (逐点相减)
  const excessData: (number | null)[] = []
  if (hasBenchmark && props.strategyNav && props.benchmarkNav) {
    const minLen = Math.min(props.strategyNav.length, props.benchmarkNav.length)
    for (let i = 0; i < minLen; i++) {
      excessData.push(parseFloat((props.strategyNav[i] - props.benchmarkNav[i]).toFixed(4)))
    }
    for (let i = minLen; i < (props.strategyNav?.length ?? 0); i++) {
      excessData.push(null)
    }
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const seriesList: any[] = [
    {
      name: '策略净值',
      type: 'line' as const,
      data: props.strategyNav || [],
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 2, color: theme.value.color[0] },
      itemStyle: { color: theme.value.color[0] },
    },
  ]

  if (hasBenchmark) {
    seriesList.push({
      name: '沪深300',
      type: 'line' as const,
      data: props.benchmarkNav || [],
      smooth: true,
      symbol: 'none',
      lineStyle: {
        width: 2,
        type: 'dashed' as const,
        color: '#9CA3AF',
      },
      itemStyle: { color: '#9CA3AF' },
    })
    seriesList.push({
      name: '超额收益',
      type: 'line' as const,
      data: excessData,
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 1.5, color: theme.value.color[2] },
      areaStyle: {
        color: theme.value.color[2],
        opacity: 0.12,
      },
      itemStyle: { color: theme.value.color[2] },
    })
  }

  return {
    animation: true,
    animationDuration: 600,
    animationEasing: 'cubicOut' as const,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: theme.value.tooltip.backgroundColor,
      borderColor: theme.value.tooltip.borderColor,
      textStyle: theme.value.tooltip.textStyle,
    },
    legend: {
      data: legendData,
      top: 10,
      textStyle: { color: theme.value.legend.textStyle.color },
    },
    grid: {
      left: '10%',
      right: '5%',
      top: '15%',
      bottom: '10%',
    },
    xAxis: {
      type: 'category',
      data: props.dates || [],
      axisLine: { lineStyle: { color: theme.value.axisLine.lineStyle.color } },
      axisLabel: { color: theme.value.axisLabel.color },
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLine: { lineStyle: { color: theme.value.axisLine.lineStyle.color } },
      axisLabel: { color: theme.value.axisLabel.color },
      splitLine: { lineStyle: { color: theme.value.splitLine.lineStyle.color } },
    },
    series: seriesList,
  }
}

function buildMultiSeriesOption() {
  const multiSeries = props.series || []
  const legendNames = multiSeries.map((s) => s.name)
  const xData = multiSeries.length > 0 ? multiSeries[0].dates : []
  const colors = theme.value.color

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const chartSeries: any[] = multiSeries.map((s, i) => {
    const isBenchmark = s.name.includes('沪深')
    const lineColor =
      s.color || (isBenchmark ? theme.value.textStyle.color : colors[i % colors.length])
    return {
      name: s.name,
      type: 'line' as const,
      data: s.values,
      smooth: true,
      symbol: 'none',
      lineStyle: {
        width: 2,
        color: lineColor,
        type:
          i === multiSeries.length - 1 && isBenchmark ? ('dashed' as const) : ('solid' as const),
      },
      itemStyle: { color: lineColor },
    }
  })

  // Attach event markLine to the first series
  if (chartSeries.length > 0 && props.events && props.events.length > 0) {
    chartSeries[0] = {
      ...chartSeries[0],
      markLine: {
        silent: true,
        symbol: 'none',
        data: props.events.map((e) => ({
          xAxis: e.date,
          label: {
            formatter: e.label,
            position: 'insideEndTop' as const,
            fontSize: 10,
            color: e.type === 'market' ? '#f59e0b' : theme.value.axisLabel.color,
          },
          lineStyle: {
            type: (e.type === 'market' ? 'solid' : 'dotted') as 'solid' | 'dotted',
            color: e.type === 'market' ? '#f59e0b' : '#a1a1aa',
            width: 1,
          },
        })),
      },
    }
  }

  return {
    animation: true,
    animationDuration: 600,
    animationEasing: 'cubicOut' as const,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: theme.value.tooltip.backgroundColor,
      borderColor: theme.value.tooltip.borderColor,
      textStyle: theme.value.tooltip.textStyle,
    },
    legend: {
      data: legendNames,
      top: 10,
      type: 'scroll',
      textStyle: { color: theme.value.legend.textStyle.color },
    },
    grid: {
      left: '8%',
      right: '5%',
      top: '15%',
      bottom: props.showDataZoom ? '18%' : '10%',
    },
    xAxis: {
      type: 'category',
      data: xData,
      axisLine: { lineStyle: { color: theme.value.axisLine.lineStyle.color } },
      axisLabel: { color: theme.value.axisLabel.color },
    },
    yAxis: {
      type: props.logScale ? 'log' : 'value',
      scale: true,
      min: props.logScale ? undefined : 'dataMin',
      axisLine: { lineStyle: { color: theme.value.axisLine.lineStyle.color } },
      axisLabel: { color: theme.value.axisLabel.color },
      splitLine: { lineStyle: { color: theme.value.splitLine.lineStyle.color } },
    },
    series: chartSeries,
    dataZoom: props.showDataZoom
      ? [
          { type: 'inside', xAxisIndex: 0 },
          {
            type: 'slider',
            xAxisIndex: 0,
            height: 24,
            bottom: 4,
            borderColor: theme.value.splitLine.lineStyle.color,
            fillerColor: 'rgba(100,100,100,0.1)',
            handleStyle: { color: theme.value.color[0] },
          },
        ]
      : [],
  }
}
</script>

<template>
  <div class="w-full" :style="{ height: (height || 400) + 'px' }">
    <VChart :option="option" autoresize />
  </div>
</template>
