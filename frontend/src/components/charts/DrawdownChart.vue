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
    drawdown: number[]
    height?: number
  }>(),
  {
    height: 300,
  }
)

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
      const val = (p.value * 100).toFixed(2)
      return `${p.name}<br/>回撤: <b style="color:#22C55E">${val}%</b>`
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
    max: 0,
    axisLine: { lineStyle: { color: theme.value.axisLine.lineStyle.color } },
    axisLabel: {
      color: theme.value.axisLabel.color,
      formatter: (v: number) => `${(v * 100).toFixed(0)}%`,
    },
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
      fillerColor: 'rgba(34,197,94,0.08)',
      handleStyle: { color: '#22C55E' },
      textStyle: { color: theme.value.axisLabel.color },
    },
  ],
  series: [
    {
      name: '回撤',
      type: 'line',
      data: props.drawdown,
      smooth: true,
      symbol: 'none',
      lineStyle: { width: 1.5, color: '#22C55E' },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(34,197,94,0.35)' },
            { offset: 1, color: 'rgba(34,197,94,0.02)' },
          ],
        },
      },
      markLine: {
        silent: true,
        symbol: 'none',
        lineStyle: { type: 'dashed', color: '#EF4444', width: 1 },
        label: {
          formatter: (p: any) => `${(p.value * 100).toFixed(1)}%`,
          color: '#EF4444',
          fontSize: 11,
        },
        data: [
          {
            name: '最大回撤',
            yAxis: Math.min(...props.drawdown),
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
