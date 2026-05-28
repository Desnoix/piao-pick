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
import { useChartTheme } from '../composables/use-chart-theme'

use([LineChart, TitleComponent, TooltipComponent, GridComponent, LegendComponent, CanvasRenderer])

const { theme } = useChartTheme()

const props = defineProps<{
  quarters: string[]
  revGrowth: number[]
  earGrowth: number[]
  grossMargin: number[]
}>()

const option = computed(() => {
  const colors = theme.value.color

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
      data: ['营收增长', '利润增长', '毛利率'],
      top: 4,
      textStyle: { color: theme.value.legend.textStyle.color },
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
      axisLine: { lineStyle: { color: theme.value.axisLine.lineStyle.color } },
      axisLabel: { color: theme.value.axisLabel.color },
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        color: theme.value.axisLabel.color,
        formatter: '{value}%',
      },
      axisLine: { lineStyle: { color: theme.value.axisLine.lineStyle.color } },
      splitLine: { lineStyle: { color: theme.value.splitLine.lineStyle.color } },
    },
    series: [
      {
        name: '营收增长',
        type: 'line',
        data: props.revGrowth,
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { width: 2, color: colors[0] },
        itemStyle: { color: colors[0] },
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
        lineStyle: { width: 2, color: colors[1] },
        itemStyle: { color: colors[1] },
      },
      {
        name: '毛利率',
        type: 'line',
        data: props.grossMargin,
        smooth: true,
        symbol: 'rect',
        symbolSize: 6,
        lineStyle: { width: 2, color: colors[2] },
        itemStyle: { color: colors[2] },
      },
    ],
  }
})
</script>

<template>
  <div class="h-[350px] w-full">
    <VChart :option="option" autoresize />
  </div>
</template>
