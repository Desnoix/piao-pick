<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { TooltipComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useChartTheme } from '../../composables/use-chart-theme'

use([BarChart, TooltipComponent, GridComponent, CanvasRenderer])

const { theme } = useChartTheme()

const props = defineProps<{
  data: number[]
}>()

const option = computed(() => {
  const months = [
    '1月',
    '2月',
    '3月',
    '4月',
    '5月',
    '6月',
    '7月',
    '8月',
    '9月',
    '10月',
    '11月',
    '12月',
  ]

  return {
    animation: true,
    animationDuration: 600,
    animationEasing: 'cubicOut' as const,
    tooltip: {
      trigger: 'axis',
      backgroundColor: theme.value.tooltip.backgroundColor,
      borderColor: theme.value.tooltip.borderColor,
      textStyle: theme.value.tooltip.textStyle,
      formatter: (params: any) => {
        return `${params[0].name}: ${params[0].value.toFixed(2)}%`
      },
    },
    grid: {
      left: '10%',
      right: '5%',
      top: '10%',
      bottom: '10%',
    },
    xAxis: {
      type: 'category',
      data: months,
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
        type: 'bar',
        data: props.data.map((val) => ({
          value: val,
          itemStyle: {
            color: val >= 0 ? '#EF4444' : '#22C55E',
          },
        })),
      },
    ],
  }
})
</script>

<template>
  <div class="h-[400px] w-full">
    <VChart :option="option" autoresize />
  </div>
</template>
