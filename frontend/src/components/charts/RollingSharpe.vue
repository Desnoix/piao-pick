<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  MarkLineComponent,
  DataZoomComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useChartTheme } from '../../composables/use-chart-theme'

use([
  LineChart,
  TitleComponent,
  TooltipComponent,
  GridComponent,
  MarkLineComponent,
  DataZoomComponent,
  CanvasRenderer,
])

const { theme } = useChartTheme()

const props = withDefaults(
  defineProps<{
    dates: string[]
    values: number[]
    height?: number
  }>(),
  {
    height: 300,
  }
)

const avgSharpe = computed(() => {
  if (props.values.length === 0) return 0
  return props.values.reduce((a, b) => a + b, 0) / props.values.length
})

const option = computed(() => ({
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
      const p = params[0]
      return `${p.name}<br/>滚动夏普: <b>${p.value.toFixed(3)}</b>`
    },
  },
  grid: {
    left: '8%',
    right: '4%',
    top: '8%',
    bottom: '18%',
  },
  xAxis: {
    type: 'category',
    data: props.dates,
    axisLine: { lineStyle: { color: theme.value.axisLine.lineStyle.color } },
    axisLabel: { color: theme.value.axisLabel.color, fontSize: 11 },
    boundaryGap: false,
  },
  yAxis: {
    type: 'value',
    scale: true,
    axisLine: { lineStyle: { color: theme.value.axisLine.lineStyle.color } },
    axisLabel: { color: theme.value.axisLabel.color },
    splitLine: { lineStyle: { color: theme.value.splitLine.lineStyle.color } },
  },
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
  series: [
    {
      name: '滚动夏普',
      type: 'line',
      data: props.values,
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 1.5, color: theme.value.color[0] },
      itemStyle: { color: theme.value.color[0] },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(6,182,212,0.18)' },
            { offset: 1, color: 'rgba(6,182,212,0.01)' },
          ],
        },
      },
      markLine: {
        silent: true,
        symbol: 'none',
        lineStyle: { type: 'dashed', width: 1 },
        label: { fontSize: 11 },
        data: [
          {
            yAxis: 0,
            name: '零轴',
            lineStyle: { color: theme.value.splitLine.lineStyle.color },
            label: { show: false },
          },
          {
            yAxis: avgSharpe.value,
            name: '均值',
            lineStyle: { color: '#F59E0B' },
            label: {
              formatter: `均值 ${avgSharpe.value.toFixed(2)}`,
              color: '#F59E0B',
              position: 'insideEndTop',
            },
          },
        ],
      },
    },
  ],
}))
</script>

<template>
  <div class="w-full" :style="{ height: height + 'px' }">
    <VChart :option="option" autoresize />
  </div>
</template>
