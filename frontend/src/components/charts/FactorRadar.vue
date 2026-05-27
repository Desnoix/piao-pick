<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { RadarChart } from 'echarts/charts'
import { TooltipComponent, RadarComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { FACTOR_LABELS } from '../../utils/constants'

use([RadarChart, TooltipComponent, RadarComponent, CanvasRenderer])

const props = defineProps<{
  factors: Record<string, number>
}>()

const option = computed(() => {
  const indicators = Object.keys(props.factors).map((key) => ({
    name: FACTOR_LABELS[key] || key,
    max: 100,
  }))
  
  const values = Object.values(props.factors)

  return {
    animation: false,
    tooltip: {},
    radar: {
      indicator: indicators,
      radius: '65%',
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: values,
            areaStyle: { opacity: 0.3 },
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
