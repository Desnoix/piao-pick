<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  TooltipComponent,
  GridComponent,
  MarkLineComponent,
  DataZoomComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useChartTheme } from '../../composables/use-chart-theme'

use([
  LineChart,
  TooltipComponent,
  GridComponent,
  MarkLineComponent,
  DataZoomComponent,
  CanvasRenderer,
])

const { theme } = useChartTheme()

const props = defineProps<{
  dates: string[]
  diffValues: number[]
  targetName: string
  baseName: string
  height?: number
  dataZoom?: boolean
}>()

const option = computed(() => {
  const pos = props.diffValues.map((v) => (v >= 0 ? v : null))
  const neg = props.diffValues.map((v) => (v < 0 ? v : null))

  return {
    animation: true,
    animationDuration: 600,
    tooltip: {
      trigger: 'axis',
      backgroundColor: theme.value.tooltip.backgroundColor,
      borderColor: theme.value.tooltip.borderColor,
      textStyle: theme.value.tooltip.textStyle,
      formatter: (params: Array<{ dataIndex: number }>) => {
        if (!params?.length) return ''
        const val = props.diffValues[params[0].dataIndex]
        if (isNaN(val)) return '无数据'
        const c = val >= 0 ? '#ef4444' : '#22c55e'
        return `${props.dates[params[0].dataIndex]}<br/>${props.targetName} vs ${props.baseName}<br/><span style="color:${c};font-weight:bold">${val >= 0 ? '+' : ''}${(val * 100).toFixed(2)}%</span>`
      },
    },
    grid: {
      left: '8%',
      right: '5%',
      top: '12%',
      bottom: props.dataZoom ? '20%' : '15%',
    },
    xAxis: {
      type: 'category',
      data: props.dates,
      axisLine: { lineStyle: { color: theme.value.axisLine.lineStyle.color } },
      axisLabel: { color: theme.value.axisLabel.color },
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLabel: {
        color: theme.value.axisLabel.color,
        formatter: (v: number) => `${(v * 100).toFixed(0)}%`,
      },
      splitLine: {
        lineStyle: { color: theme.value.splitLine.lineStyle.color },
      },
    },
    series: [
      {
        name: '收益差 (正)',
        type: 'line',
        data: pos,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#ef4444', width: 2 },
        areaStyle: { color: 'rgba(239,68,68,0.15)' },
        connectNulls: false,
      },
      {
        name: '收益差 (负)',
        type: 'line',
        data: neg,
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#22c55e', width: 2 },
        areaStyle: { color: 'rgba(34,197,94,0.15)' },
        connectNulls: false,
      },
      {
        type: 'line',
        data: [],
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { type: 'dashed', color: '#71717a', width: 1 },
          data: [{ yAxis: 0 }],
          label: { formatter: '零轴', position: 'insideEndTop' },
        },
      },
    ],
    dataZoom: props.dataZoom
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
})
</script>

<template>
  <div class="w-full" :style="{ height: (height || 300) + 'px' }">
    <VChart :option="option" autoresize />
  </div>
</template>
