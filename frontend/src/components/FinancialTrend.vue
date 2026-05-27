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

use([LineChart, TitleComponent, TooltipComponent, GridComponent, LegendComponent, CanvasRenderer])

const props = defineProps<{
  quarters: string[]
  revGrowth: number[]
  earGrowth: number[]
  grossMargin: number[]
}>()

const CHART_COLORS = {
  primary: '#3B82F6',
  up: '#EF4444',
  down: '#22C55E',
  accent: '#A78BFA',
}

const option = computed(() => ({
  animation: false,
  tooltip: {
    trigger: 'axis',
    backgroundColor: 'rgba(24,24,27,0.95)',
    borderColor: '#27272A',
    textStyle: { color: '#FAFAFA', fontSize: 12 },
  },
  legend: {
    data: ['营收增长', '利润增长', '毛利率'],
    top: 4,
    textStyle: { color: '#A1A1AA' },
  },
  grid: {
    left: '12%',
    right: '5%',
    top: '18%',
    bottom: '10%',
  },
  xAxis: {
    type: 'category',
    data: props.quarters,
    axisLine: { lineStyle: { color: '#27272A' } },
    axisLabel: { color: '#A1A1AA' },
  },
  yAxis: {
    type: 'value',
    axisLabel: {
      color: '#A1A1AA',
      formatter: '{value}%',
    },
    splitLine: { lineStyle: { color: '#27272A' } },
  },
  series: [
    {
      name: '营收增长',
      type: 'line',
      data: props.revGrowth,
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { width: 2, color: CHART_COLORS.up },
      itemStyle: { color: CHART_COLORS.up },
      label: {
        show: false,
      },
    },
    {
      name: '利润增长',
      type: 'line',
      data: props.earGrowth,
      smooth: true,
      symbol: 'diamond',
      symbolSize: 6,
      lineStyle: { width: 2, color: CHART_COLORS.primary },
      itemStyle: { color: CHART_COLORS.primary },
    },
    {
      name: '毛利率',
      type: 'line',
      data: props.grossMargin,
      smooth: true,
      symbol: 'rect',
      symbolSize: 6,
      lineStyle: { width: 2, color: CHART_COLORS.accent },
      itemStyle: { color: CHART_COLORS.accent },
    },
  ],
}))
</script>

<template>
  <div class="w-full h-[350px]">
    <VChart :option="option" autoresize />
  </div>
</template>
