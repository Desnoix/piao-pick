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
  DataZoomComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useChartTheme } from '../../composables/use-chart-theme'

use([
  LineChart,
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  DataZoomComponent,
  CanvasRenderer,
])

const { theme } = useChartTheme()

const props = withDefaults(
  defineProps<{
    dates: string[]
    strategyNav: number[]
    benchmarkNav: number[]
    height?: number
  }>(),
  {
    height: 420,
  }
)

const hasBenchmark = computed(() => props.benchmarkNav.length > 0)

const excessReturn = computed(() => {
  if (!hasBenchmark.value) return []
  const result: number[] = []
  for (let i = 0; i < props.strategyNav.length; i++) {
    const s = props.strategyNav[i]
    const b = props.benchmarkNav[i] ?? 1
    result.push((s / b - 1) * 100)
  }
  return result
})

const option = computed(() => {
  const series: any[] = [
    {
      name: '策略净值',
      type: 'line',
      data: props.strategyNav,
      xAxisIndex: 0,
      yAxisIndex: 0,
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 2, color: theme.value.color[0] },
      itemStyle: { color: theme.value.color[0] },
      z: 2,
    },
  ]

  if (hasBenchmark.value) {
    series.push({
      name: '沪深300',
      type: 'line',
      data: props.benchmarkNav,
      xAxisIndex: 0,
      yAxisIndex: 0,
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 1.5, type: 'dashed', color: theme.value.textStyle.color },
      itemStyle: { color: theme.value.textStyle.color },
      z: 1,
    })
    series.push({
      name: '累计超额',
      type: 'line',
      data: excessReturn.value,
      xAxisIndex: 0,
      yAxisIndex: 1,
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 1, color: '#8B5CF6' },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(139,92,246,0.25)' },
            { offset: 1, color: 'rgba(139,92,246,0.02)' },
          ],
        },
      },
    })
  }

  const legendData = hasBenchmark.value ? ['策略净值', '沪深300', '累计超额'] : ['策略净值']

  const yAxes: any[] = [
    {
      type: 'value',
      scale: true,
      gridIndex: 0,
      axisLine: { lineStyle: { color: theme.value.axisLine.lineStyle.color } },
      axisLabel: { color: theme.value.axisLabel.color },
      splitLine: { lineStyle: { color: theme.value.splitLine.lineStyle.color } },
    },
  ]

  if (hasBenchmark.value) {
    yAxes.push({
      type: 'value',
      gridIndex: 0,
      position: 'right',
      axisLine: { show: false },
      axisLabel: {
        color: '#8B5CF6',
        formatter: (v: number) => `${v.toFixed(0)}%`,
      },
      splitLine: { show: false },
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
      formatter: (params: any[]) => {
        let html = `${params[0].name}<br/>`
        for (const p of params) {
          const val = p.seriesName === '累计超额' ? `${p.value.toFixed(2)}%` : p.value.toFixed(4)
          html += `${p.marker} ${p.seriesName}: <b>${val}</b><br/>`
        }
        return html
      },
    },
    legend: {
      data: legendData,
      top: 8,
      textStyle: { color: theme.value.legend.textStyle.color },
    },
    grid: {
      left: '8%',
      right: hasBenchmark.value ? '10%' : '4%',
      top: '14%',
      bottom: '18%',
    },
    xAxis: {
      type: 'category',
      data: props.dates,
      yAxisIndex: 0,
      axisLine: { lineStyle: { color: theme.value.axisLine.lineStyle.color } },
      axisLabel: { color: theme.value.axisLabel.color, fontSize: 11 },
      boundaryGap: false,
    },
    yAxis: yAxes,
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      {
        type: 'slider',
        start: 0,
        end: 100,
        height: 16,
        bottom: 4,
        borderColor: theme.value.axisLine.lineStyle.color,
        fillerColor: 'rgba(6,182,212,0.08)',
        handleStyle: { color: theme.value.color[0] },
        textStyle: { color: theme.value.axisLabel.color },
      },
    ],
    series,
  }
})
</script>

<template>
  <div class="w-full" :style="{ height: height + 'px' }">
    <VChart :option="option" autoresize />
  </div>
</template>
