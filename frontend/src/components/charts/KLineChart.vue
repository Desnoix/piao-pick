<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CandlestickChart, LineChart, BarChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  DataZoomComponent,
  LegendComponent,
  ToolboxComponent,
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
  ToolboxComponent,
  CanvasRenderer,
])

const { theme } = useChartTheme()
const chartRef = ref()

defineExpose({
  get chart() {
    return chartRef.value?.chart
  },
})

const props = defineProps<{
  data: Kline[]
}>()

const option = computed(() => {
  const dates = props.data.map((k) => k.trade_date)
  const ohlc = props.data.map((k) => [k.open, k.close, k.low, k.high])
  const closes = props.data.map((k) => k.close ?? 0)

  // 均线 MA
  const ma5 = calculateMA(closes, 5)
  const ma10 = calculateMA(closes, 10)
  const ma20 = calculateMA(closes, 20)
  const ma60 = calculateMA(closes, 60)

  // BOLL 布林带
  const boll = calculateBOLL(closes, 20)

  // MACD
  const macdData = calculateMACD(closes)

  // 成交量 (A股: 红涨绿跌)
  const volumeData = props.data.map((k) => ({
    value: k.volume ?? 0,
    itemStyle: {
      color: (k.close ?? 0) >= (k.open ?? 0) ? 'rgba(239,68,68,0.6)' : 'rgba(34,197,94,0.6)',
    },
  }))

  // MACD 柱状图颜色 (红正绿负)
  const macdBarData = macdData.macd.map((v) => ({
    value: v,
    itemStyle: {
      color: (v ?? 0) >= 0 ? 'rgba(239,68,68,0.8)' : 'rgba(34,197,94,0.8)',
    },
  }))

  return {
    animation: true,
    animationDuration: 600,
    animationEasing: 'cubicOut' as const,
    toolbox: {
      show: true,
      top: 0,
      right: '5%',
      feature: {
        saveAsImage: { title: '保存图片', pixelRatio: 2 },
        dataZoom: { title: { zoom: '区域缩放', back: '缩放还原' } },
        restore: { title: '重置' },
      },
      iconStyle: { borderColor: theme.value.axisLabel.color },
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: theme.value.tooltip.backgroundColor,
      borderColor: theme.value.tooltip.borderColor,
      textStyle: theme.value.tooltip.textStyle,
    },
    legend: {
      data: ['K线', 'MA5', 'MA10', 'MA20', 'MA60', 'BOLL上', 'BOLL下'],
      top: 30,
      textStyle: { color: theme.value.legend.textStyle.color, fontSize: 11 },
    },
    grid: [
      { left: '10%', right: '5%', top: '12%', height: '45%' },
      { left: '10%', right: '5%', top: '60%', height: '10%' },
      { left: '10%', right: '5%', top: '73%', height: '12%' },
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
        axisLabel: { show: false },
        axisLine: { lineStyle: { color: theme.value.axisLine.lineStyle.color } },
      },
      {
        type: 'category',
        data: dates,
        gridIndex: 2,
        axisLine: { lineStyle: { color: theme.value.axisLine.lineStyle.color } },
        axisLabel: { color: theme.value.axisLabel.color, fontSize: 10 },
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
      {
        scale: true,
        gridIndex: 2,
        axisLabel: { show: false },
        axisLine: { lineStyle: { color: theme.value.axisLine.lineStyle.color } },
      },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1, 2], start: 70, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1, 2], start: 70, end: 100, top: '90%', height: 20 },
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
        name: 'MA5',
        type: 'line',
        data: ma5,
        xAxisIndex: 0,
        yAxisIndex: 0,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1, color: '#F59E0B' },
        itemStyle: { color: '#F59E0B' },
      },
      {
        name: 'MA10',
        type: 'line',
        data: ma10,
        xAxisIndex: 0,
        yAxisIndex: 0,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1, color: '#3B82F6' },
        itemStyle: { color: '#3B82F6' },
      },
      {
        name: 'MA20',
        type: 'line',
        data: ma20,
        xAxisIndex: 0,
        yAxisIndex: 0,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1, color: '#8B5CF6' },
        itemStyle: { color: '#8B5CF6' },
      },
      {
        name: 'MA60',
        type: 'line',
        data: ma60,
        xAxisIndex: 0,
        yAxisIndex: 0,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1, color: '#EC4899' },
        itemStyle: { color: '#EC4899' },
      },
      {
        name: 'BOLL上',
        type: 'line',
        data: boll.upper,
        xAxisIndex: 0,
        yAxisIndex: 0,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1, type: 'dashed' as const, color: '#94A3B8' },
        itemStyle: { color: '#94A3B8' },
      },
      {
        name: 'BOLL下',
        type: 'line',
        data: boll.lower,
        xAxisIndex: 0,
        yAxisIndex: 0,
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 1, type: 'dashed' as const, color: '#94A3B8' },
        itemStyle: { color: '#94A3B8' },
      },
      {
        name: '成交量',
        type: 'bar',
        data: volumeData,
        xAxisIndex: 1,
        yAxisIndex: 1,
      },
      {
        name: 'DIF',
        type: 'line',
        data: macdData.dif,
        xAxisIndex: 2,
        yAxisIndex: 2,
        symbol: 'none',
        lineStyle: { width: 1.5, color: '#3B82F6' },
        itemStyle: { color: '#3B82F6' },
      },
      {
        name: 'DEA',
        type: 'line',
        data: macdData.dea,
        xAxisIndex: 2,
        yAxisIndex: 2,
        symbol: 'none',
        lineStyle: { width: 1.5, color: '#F59E0B' },
        itemStyle: { color: '#F59E0B' },
      },
      {
        name: 'MACD',
        type: 'bar',
        data: macdBarData,
        xAxisIndex: 2,
        yAxisIndex: 2,
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

function calculateBOLL(
  data: number[],
  period: number = 20,
  multiplier: number = 2
): { upper: (number | null)[]; mid: (number | null)[]; lower: (number | null)[] } {
  const mid = calculateMA(data, period)
  const upper: (number | null)[] = []
  const lower: (number | null)[] = []
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      upper.push(null)
      lower.push(null)
    } else {
      let sumSq = 0
      for (let j = 0; j < period; j++) {
        const diff = data[i - j] - mid[i]!
        sumSq += diff * diff
      }
      const std = Math.sqrt(sumSq / period)
      upper.push(mid[i]! + multiplier * std)
      lower.push(mid[i]! - multiplier * std)
    }
  }
  return { upper, mid, lower }
}

function calculateEMA(data: number[], period: number): number[] {
  const result: number[] = new Array(data.length)
  const multiplier = 2 / (period + 1)
  let sum = 0
  for (let i = 0; i < period && i < data.length; i++) {
    sum += data[i]
  }
  for (let i = 0; i < period - 1; i++) {
    result[i] = NaN
  }
  result[period - 1] = sum / period
  for (let i = period; i < data.length; i++) {
    result[i] = (data[i] - result[i - 1]) * multiplier + result[i - 1]
  }
  return result
}

function calculateMACD(data: number[]): {
  dif: (number | null)[]
  dea: (number | null)[]
  macd: (number | null)[]
} {
  const ema12 = calculateEMA(data, 12)
  const ema26 = calculateEMA(data, 26)
  const dif: (number | null)[] = []
  for (let i = 0; i < data.length; i++) {
    if (isNaN(ema12[i]) || isNaN(ema26[i])) {
      dif.push(null)
    } else {
      dif.push(ema12[i] - ema26[i])
    }
  }
  const difValues = dif.map((v) => v ?? 0)
  const deaRaw = calculateEMA(difValues, 9)
  const dea: (number | null)[] = deaRaw.map((v, i) => (dif[i] === null ? null : v))
  const macd: (number | null)[] = []
  for (let i = 0; i < data.length; i++) {
    if (dif[i] === null || dea[i] === null) {
      macd.push(null)
    } else {
      macd.push((dif[i]! - dea[i]!) * 2)
    }
  }
  return { dif, dea, macd }
}
</script>

<template>
  <div class="h-[600px] w-full">
    <VChart ref="chartRef" :option="option" autoresize />
  </div>
</template>
