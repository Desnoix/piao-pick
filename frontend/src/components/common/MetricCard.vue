<script setup lang="ts">
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

const trendBarColor = computed(() => {
  if (props.trend === 'up') return 'var(--color-up)'
  if (props.trend === 'down') return 'var(--color-down)'
  return 'transparent'
})
</script>

<template>
  <div
    class="relative overflow-hidden rounded-lg border transition-colors duration-150"
    style="
      background-color: var(--color-surface-elevated);
      border-color: var(--color-border);
    "
    @mouseenter="($event.currentTarget as HTMLElement).style.borderColor = 'var(--color-border-muted)'"
    @mouseleave="($event.currentTarget as HTMLElement).style.borderColor = 'var(--color-border)'"
  >
    <!-- Trend indicator bar -->
    <div
      class="absolute top-0 left-0 right-0 h-[2px]"
      :style="{ backgroundColor: trendBarColor }"
    />
    <div class="p-4">
      <div
        class="text-xs mb-1.5"
        style="color: var(--color-text-secondary)"
      >
        {{ label }}
      </div>
      <div
        class="text-2xl font-bold font-mono"
        :style="{ color: valueColor }"
      >
        {{ displayValue }}
      </div>
    </div>
  </div>
</template>
