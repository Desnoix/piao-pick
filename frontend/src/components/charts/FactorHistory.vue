<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  TooltipComponent,
  GridComponent,
  LegendComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { FACTOR_LABELS } from '../../utils/constants'

use([LineChart, TooltipComponent, GridComponent, LegendComponent, CanvasRenderer])

const props = defineProps<{
  dates: string[]
  factors: Record<string, number[]>
}>()

const PALETTE = [
  '#3B82F6', '#EF4444', '#22C55E', '#A78BFA',
  '#F59E0B', '#EC4899', '#14B8A6', '#F97316',
  '#6366F1', '#84CC16', '#06B6D4', '#E11D48',
  '#8B5CF6',
]

const option = computed(() => {
  const keys = Object.keys(props.factors)
  const legendData = keys.map((k) => FACTOR_LABELS[k] || k)

  const series = keys.map((key, idx) => ({
    name: FACTOR_LABELS[key] || key,
    type: 'line' as const,
    data: props.factors[key],
    smooth: true,
    symbol: 'none',
    lineStyle: { width: 1.5, color: PALETTE[idx % PALETTE.length] },
    itemStyle: { color: PALETTE[idx % PALETTE.length] },
  }))

  return {
    animation: false,
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(24,24,27,0.95)',
      borderColor: '#27272A',
      textStyle: { color: '#FAFAFA', fontSize: 12 },
    },
    legend: {
      type: 'scroll',
      data: legendData,
      top: 4,
      textStyle: { color: '#A1A1AA', fontSize: 11 },
      pageTextStyle: { color: '#A1A1AA' },
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
      axisLine: { lineStyle: { color: '#27272A' } },
      axisLabel: { color: '#A1A1AA', fontSize: 10 },
    },
    yAxis: {
      type: 'value' as const,
      axisLabel: { color: '#A1A1AA' },
      splitLine: { lineStyle: { color: '#27272A' } },
    },
    series,
  }
})
</script>

<template>
  <div class="w-full h-[350px]">
    <VChart :option="option" autoresize />
  </div>
</template>
