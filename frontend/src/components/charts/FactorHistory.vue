<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  TooltipComponent,
  GridComponent,
  LegendComponent,
  DataZoomComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { FACTOR_LABELS } from '../../utils/constants'
import { useChartTheme } from '../../composables/use-chart-theme'

use([
  LineChart,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  DataZoomComponent,
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
  dates: string[]
  factors: Record<string, number[]>
}>()

const option = computed(() => {
  const keys = Object.keys(props.factors)
  const legendData = keys.map((k) => FACTOR_LABELS[k] || k)
  const colors = theme.value.color

  const series = keys.map((key, idx) => ({
    name: FACTOR_LABELS[key] || key,
    type: 'line' as const,
    data: props.factors[key],
    smooth: true,
    symbol: 'none',
    lineStyle: { width: 1.5, color: colors[idx % colors.length] },
    itemStyle: { color: colors[idx % colors.length] },
  }))

  return {
    animation: true,
    animationDuration: 600,
    animationEasing: 'cubicOut' as const,
    tooltip: {
      trigger: 'axis',
      backgroundColor: theme.value.tooltip.backgroundColor,
      borderColor: theme.value.tooltip.borderColor,
      textStyle: theme.value.tooltip.textStyle,
    },
    legend: {
      type: 'scroll',
      data: legendData,
      top: 4,
      textStyle: { color: theme.value.legend.textStyle.color, fontSize: 11 },
      pageTextStyle: { color: theme.value.legend.textStyle.color },
    },
    grid: {
      left: '10%',
      right: '5%',
      top: '18%',
      bottom: '10%',
    },
    xAxis: {
      type: 'category' as const,
      data: props.dates,
      axisLine: { lineStyle: { color: theme.value.axisLine.lineStyle.color } },
      axisLabel: { color: theme.value.axisLabel.color, fontSize: 10 },
    },
    yAxis: {
      type: 'value' as const,
      axisLabel: { color: theme.value.axisLabel.color },
      axisLine: { lineStyle: { color: theme.value.axisLine.lineStyle.color } },
      splitLine: { lineStyle: { color: theme.value.splitLine.lineStyle.color } },
    },
    dataZoom: [{ type: 'inside', xAxisIndex: 0, start: 70, end: 100 }],
    series,
  }
})
</script>

<template>
  <div class="h-[350px] w-full">
    <VChart ref="chartRef" :option="option" autoresize />
  </div>
</template>
