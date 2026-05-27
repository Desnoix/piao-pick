<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CandlestickChart, LineChart, BarChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  DataZoomComponent,
  LegendComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { Kline } from '../../types/stock'
import { useChartTheme } from '../../composables/use-chart-theme'

use([
  CandlestickChart,
  LineChart,
  BarChart,
  TitleComponent,
  TooltipComponent,
  GridComponent,
  DataZoomComponent,
  LegendComponent,
  CanvasRenderer,
])

const { theme } = useChartTheme()

const props = defineProps<{
  data: Kline[]
}>()

const option = computed(() => {
  const dates = props.data.map((k) => k.trade_date)
  const ohlc = props.data.map((k) => [k.open, k.close, k.low, k.high])
  const volumes = props.data.map((k) => k.volume ?? 0)
  
  // Calculate MA20 and MA60
  const closes = props.data.map((k) => k.close ?? 0)
  const ma20 = calculateMA(closes, 20)
  const ma60 = calculateMA(closes, 60)

  // Volume colors: red for up candles, green for down (A-share convention)
  const volumeData = props.data.map((k) => ({
    value: k.volume ?? 0,
    itemStyle: {
      color: (k.close ?? 0) >= (k.open ?? 0) ? 'rgba(239,68,68,0.6)' : 'rgba(34,197,94,0.6)',
    },
  }))

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
      data: ['K线', 'MA20', 'MA60'],
      top: 10,
      textStyle: { color: theme.value.legend.textStyle.color },
    },
    grid: [
      { left: '10%', right: '5%', top: '15%', height: '55%' },
      { left: '10%', right: '5%', top: '75%', height: '15%' },
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        gridIndex: 0,
        axisLabel: { show: false },
        axisLine: { lineStyle: { color: theme.value.axisLine.lineStyle.color } },
      },
      {
        type: 'category',
        data: dates,
        gridIndex: 1,
        axisLine: { lineStyle: { color: theme.value.axisLine.lineStyle.color } },
        axisLabel: { color: theme.value.axisLabel.color },
      },
    ],
    yAxis: [
      {
        scale: true,
        gridIndex: 0,
        axisLine: { lineStyle: { color: theme.value.axisLine.lineStyle.color } },
        axisLabel: { color: theme.value.axisLabel.color },
        splitLine: { lineStyle: { color: theme.value.splitLine.lineStyle.color } },
      },
      {
        scale: true,
        gridIndex: 1,
        axisLabel: { show: false },
        axisLine: { lineStyle: { color: theme.value.axisLine.lineStyle.color } },
      },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 70, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], start: 70, end: 100, top: '95%', height: 20 },
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: ohlc,
        xAxisIndex: 0,
        yAxisIndex: 0,
        itemStyle: {
          color: '#EF4444',
          color0: '#22C55E',
          borderColor: '#EF4444',
          borderColor0: '#22C55E',
        },
      },
      {
        name: 'MA20',
        type: 'line',
        data: ma20,
        xAxisIndex: 0,
        yAxisIndex: 0,
        smooth: true,
        lineStyle: { width: 1, color: theme.value.color[0] },
        itemStyle: { color: theme.value.color[0] },
        symbol: 'none',
      },
      {
        name: 'MA60',
        type: 'line',
        data: ma60,
        xAxisIndex: 0,
        yAxisIndex: 0,
        smooth: true,
        lineStyle: { width: 1, color: theme.value.color[1] },
        itemStyle: { color: theme.value.color[1] },
        symbol: 'none',
      },
      {
        name: '成交量',
        type: 'bar',
        data: volumeData,
        xAxisIndex: 1,
        yAxisIndex: 1,
      },
    ],
  }
})

function calculateMA(data: number[], period: number): (number | null)[] {
  const result: (number | null)[] = []
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push(null)
    } else {
      let sum = 0
      for (let j = 0; j < period; j++) {
        sum += data[i - j]
      }
      result.push(sum / period)
    }
  }
  return result
}
</script>

<template>
  <div class="w-full h-[500px]">
    <VChart :option="option" autoresize />
  </div>
</template>
