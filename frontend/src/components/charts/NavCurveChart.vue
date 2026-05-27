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
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { NavSeries } from '../../types/strategy'
import { useChartTheme } from '../../composables/use-chart-theme'

use([LineChart, TitleComponent, TooltipComponent, GridComponent, LegendComponent, CanvasRenderer])

const { theme } = useChartTheme()

const props = defineProps<{
  dates?: string[]
  strategyNav?: number[]
  benchmarkNav?: number[]
  series?: NavSeries[]
  logScale?: boolean
  height?: number
}>()

const option = computed(() => {
  if (props.series && props.series.length > 0) {
    return buildMultiSeriesOption()
  }
  return buildLegacyOption()
})

function buildLegacyOption() {
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
      data: ['策略净值', '沪深300'],
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
    series: [
      {
        name: '策略净值',
        type: 'line',
        data: props.strategyNav || [],
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2, color: theme.value.color[0] },
        itemStyle: { color: theme.value.color[0] },
      },
      {
        name: '沪深300',
        type: 'line',
        data: props.benchmarkNav || [],
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2, type: 'dashed', color: theme.value.textStyle.color },
        itemStyle: { color: theme.value.textStyle.color },
      },
    ],
  }
}

function buildMultiSeriesOption() {
  const multiSeries = props.series || []
  const legendNames = multiSeries.map((s) => s.name)
  const xData = multiSeries.length > 0 ? multiSeries[0].dates : []
  const colors = theme.value.color

  const chartSeries = multiSeries.map((s, i) => {
    const isBenchmark = s.name.includes('沪深')
    const lineColor = s.color || (isBenchmark ? theme.value.textStyle.color : colors[i % colors.length])
    return {
      name: s.name,
      type: 'line' as const,
      data: s.values,
      smooth: true,
      symbol: 'none',
      lineStyle: {
        width: 2,
        color: lineColor,
        type: i === multiSeries.length - 1 && isBenchmark ? ('dashed' as const) : ('solid' as const),
      },
      itemStyle: { color: lineColor },
    }
  })

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
      bottom: '10%',
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
  }
}
</script>

<template>
  <div class="w-full" :style="{ height: (height || 400) + 'px' }">
    <VChart :option="option" autoresize />
  </div>
</template>
