<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useChartTheme } from '../../composables/use-chart-theme'

use([PieChart, TooltipComponent, LegendComponent, CanvasRenderer])

const { theme } = useChartTheme()

const props = defineProps<{
  data: Array<{ name: string; value: number }>
}>()

const option = computed(() => {
  return {
    animation: true,
    animationDuration: 600,
    animationEasing: 'cubicOut' as const,
    color: theme.value.color,
    tooltip: {
      trigger: 'item',
      backgroundColor: theme.value.tooltip.backgroundColor,
      borderColor: theme.value.tooltip.borderColor,
      textStyle: theme.value.tooltip.textStyle,
      formatter: '{b}: {c} ({d}%)',
    },
    legend: {
      orient: 'vertical',
      left: 'left',
      type: 'scroll',
      textStyle: { color: theme.value.legend.textStyle.color },
    },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['60%', '50%'],
        data: props.data,
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)',
          },
        },
        label: {
          color: theme.value.textStyle.color,
          formatter: '{b}\n{d}%',
        },
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
