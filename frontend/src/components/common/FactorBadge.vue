<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  label: string
  value: number
  max?: number
}>()

const maxValue = computed(() => props.max ?? 100)

const percentage = computed(() => {
  return Math.min(100, (props.value / maxValue.value) * 100)
})

const fillColor = computed(() => {
  if (percentage.value > 75) return '#22C55E'
  if (percentage.value > 50) return '#3B82F6'
  if (percentage.value > 25) return '#EAB308'
  return '#EF4444'
})
</script>

<template>
  <div
    class="inline-flex items-center gap-2.5 px-3 py-1.5 rounded-md text-sm border"
    style="
      background-color: var(--color-surface-inset);
      border-color: var(--color-border);
    "
  >
    <span
      class="text-xs"
      style="color: var(--color-text-secondary)"
    >
      {{ label }}
    </span>
    <div
      class="w-16 h-1.5 rounded-full overflow-hidden"
      style="background-color: var(--color-border)"
    >
      <div
        class="h-full rounded-full transition-all duration-300"
        :style="{ width: percentage + '%', backgroundColor: fillColor }"
      />
    </div>
    <span
      class="font-mono text-xs font-medium"
      style="color: var(--color-text-primary)"
    >
      {{ value.toFixed(1) }}
    </span>
  </div>
</template>
