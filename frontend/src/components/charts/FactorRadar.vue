<script setup lang="ts">
/**
 * Factor radar chart for displaying multi-factor scores.
 * 因子雷达图组件, 展示多因子评分画像。
 */
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { RadarChart } from 'echarts/charts'
import { TooltipComponent, RadarComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { FACTOR_LABELS } from '../../utils/constants'

use([RadarChart, TooltipComponent, RadarComponent, CanvasRenderer])

/** Theme prop shape matching useChartTheme output */
interface ChartThemeConfig {
  backgroundColor?: string
  textStyle?: { color?: string }
  tooltip?: {
    backgroundColor?: string
    borderColor?: string
    textStyle?: { color?: string; fontSize?: number }
  }
  legend?: { textStyle?: { color?: string } }
  color?: string[]
  [key: string]: any
}

const props = defineProps<{
  factors: Record<string, number>
  theme?: ChartThemeConfig
}>()

const accentColor = '#06B6D4'

const option = computed(() => {
  const indicators = Object.keys(props.factors).map((key) => ({
    name: FACTOR_LABELS[key] || key,
    max: 100,
  }))

  const values = Object.values(props.factors)
  const theme = props.theme

  // Derive colors from theme or fallback
  const textColor = theme?.textStyle?.color ?? '#94A3B8'
  const tooltipConfig = theme?.tooltip ?? {
    backgroundColor: '#1E293B',
    borderColor: '#334155',
    textStyle: { color: '#F1F5F9', fontSize: 12 },
  }

  return {
    backgroundColor: 'transparent',
    animation: true,
    tooltip: {
      ...tooltipConfig,
      trigger: 'item',
    },
    radar: {
      indicator: indicators,
      radius: '65%',
      axisName: {
        color: textColor,
        fontSize: 11,
      },
      splitLine: {
        lineStyle: {
          color: 'rgba(148, 163, 184, 0.12)',
        },
      },
      splitArea: {
        show: true,
        areaStyle: {
          color: ['transparent', 'rgba(30, 41, 59, 0.3)'],
        },
      },
      axisLine: {
        lineStyle: {
          color: 'rgba(148, 163, 184, 0.15)',
        },
      },
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: values,
            name: '因子评分',
            symbol: 'circle',
            symbolSize: 5,
            lineStyle: {
              color: accentColor,
              width: 2,
            },
            areaStyle: {
              color: 'rgba(6, 182, 212, 0.15)',
            },
            itemStyle: {
              color: accentColor,
            },
          },
        ],
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
