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

use([LineChart, TitleComponent, TooltipComponent, GridComponent, LegendComponent, CanvasRenderer])

const props = defineProps<{
  dates?: string[]
  strategyNav?: number[]
  benchmarkNav?: number[]
  series?: NavSeries[]
  logScale?: boolean
  height?: number
}>()

const CHART_COLORS = [
  '#3B82F6',
  '#F59E0B',
  '#8B5CF6',
  '#EC4899',
  '#10B981',
  '#F97316',
  '#06B6D4',
  '#EF4444',
]

const option = computed(() => {
  if (props.series && props.series.length > 0) {
    return buildMultiSeriesOption()
  }
  return buildLegacyOption()
})

function buildLegacyOption() {
  return {
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
    },
    legend: {
      data: ['策略净值', '沪深300'],
      top: 10,
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
    },
    yAxis: {
      type: 'value',
      scale: true,
    },
    series: [
      {
        name: '策略净值',
        type: 'line',
        data: props.strategyNav || [],
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2 },
      },
      {
        name: '沪深300',
        type: 'line',
        data: props.benchmarkNav || [],
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2, type: 'dashed' },
      },
    ],
  }
}

function buildMultiSeriesOption() {
  const multiSeries = props.series || []
  const legendNames = multiSeries.map((s) => s.name)
  const xData = multiSeries.length > 0 ? multiSeries[0].dates : []

  const chartSeries = multiSeries.map((s, i) => ({
    name: s.name,
    type: 'line' as const,
    data: s.values,
    smooth: true,
    symbol: 'none',
    lineStyle: {
      width: 2,
      color: s.color || CHART_COLORS[i % CHART_COLORS.length],
      type: i === multiSeries.length - 1 && s.name.includes('沪深') ? ('dashed' as const) : ('solid' as const),
    },
    itemStyle: {
      color: s.color || CHART_COLORS[i % CHART_COLORS.length],
    },
  }))

  return {
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
    },
    legend: {
      data: legendNames,
      top: 10,
      type: 'scroll',
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
    },
    yAxis: {
      type: props.logScale ? 'log' : 'value',
      scale: true,
      min: props.logScale ? undefined : 'dataMin',
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
