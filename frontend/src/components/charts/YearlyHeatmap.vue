<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { HeatmapChart } from 'echarts/charts'
import {
  TooltipComponent,
  GridComponent,
  VisualMapComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useChartTheme } from '../../composables/use-chart-theme'

use([HeatmapChart, TooltipComponent, GridComponent, VisualMapComponent, CanvasRenderer])

const { theme, isDark } = useChartTheme()

const props = defineProps<{
  data: Array<[number, number, number]>
  years: string[]
}>()

const option = computed(() => {
  const neutralBg = isDark.value ? '#1E293B' : '#F1F5F9'
  
  return {
    animation: true,
    animationDuration: 600,
    animationEasing: 'cubicOut' as const,
    tooltip: {
      position: 'top',
      backgroundColor: theme.value.tooltip.backgroundColor,
      borderColor: theme.value.tooltip.borderColor,
      textStyle: theme.value.tooltip.textStyle,
      formatter: (params: any) => {
        const year = props.years[params.value[0]]
        const month = params.value[1] + 1
        return `${year}年${month}月: ${params.value[2].toFixed(2)}%`
      },
    },
    grid: {
      left: '10%',
      right: '15%',
      top: '10%',
      bottom: '10%',
    },
    xAxis: {
      type: 'category',
      data: props.years,
      splitArea: { show: true },
      axisLine: { lineStyle: { color: theme.value.axisLine.lineStyle.color } },
      axisLabel: { color: theme.value.axisLabel.color },
    },
    yAxis: {
      type: 'category',
      data: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'],
      splitArea: { show: true },
      axisLine: { lineStyle: { color: theme.value.axisLine.lineStyle.color } },
      axisLabel: { color: theme.value.axisLabel.color },
    },
    visualMap: {
      min: -10,
      max: 10,
      calculable: true,
      orient: 'vertical',
      right: 10,
      top: 'center',
      textStyle: { color: theme.value.textStyle.color },
      inRange: {
        color: isDark.value
          ? ['#166534', '#22C55E', neutralBg, '#EF4444', '#991B1B']
          : ['#22C55E', '#86EFAC', neutralBg, '#FCA5A5', '#EF4444'],
      },
    },
    series: [
      {
        type: 'heatmap',
        data: props.data,
        label: {
          show: true,
          color: theme.value.textStyle.color,
          formatter: (params: any) => {
            const val = params.value[2]
            return val.toFixed(1)
          },
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowColor: 'rgba(0, 0, 0, 0.5)',
          },
        },
      },
    ],
  }
})
</script>

<template>
  <div class="w-full h-[400px]">
    <VChart :option="option" autoresize />
  </div>
</template>
