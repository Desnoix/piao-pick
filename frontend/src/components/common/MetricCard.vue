<script setup lang="ts">
/**
 * Metric card: elevated panel with label, value, and trend indicator bar.
 * 指标卡片: 提升面板带标签、数值和趋势指示条。
 */
import { computed } from 'vue'

const props = defineProps<{
  label: string
  value: string | number
  negative?: boolean
  trend?: 'up' | 'down' | 'neutral'
}>()

const displayValue = computed(() => {
  if (typeof props.value === 'number') {
    return props.value.toFixed(2)
  }
  return props.value
})

const valueColor = computed(() => {
  if (props.negative) return 'var(--color-up)'
  return 'var(--color-text-primary)'
})

/** Trend bar: success for positive, error for negative, accent for neutral */
const trendBarColor = computed(() => {
  if (props.trend === 'up') return 'var(--color-success)'
  if (props.trend === 'down') return 'var(--color-error)'
  if (props.trend === 'neutral') return 'var(--color-accent)'
  return 'transparent'
})
</script>

<template>
  <div class="glass-panel relative overflow-hidden">
    <!-- Trend indicator bar -->
    <div
      class="absolute top-0 right-0 left-0 h-[2px]"
      :style="{ backgroundColor: trendBarColor }"
    />
    <div class="p-4">
      <div class="mb-1.5 text-xs text-[var(--color-text-secondary)]">
        {{ label }}
      </div>
      <div class="data-mono text-2xl font-bold" :style="{ color: valueColor }">
        {{ displayValue }}
      </div>
    </div>
  </div>
</template>
