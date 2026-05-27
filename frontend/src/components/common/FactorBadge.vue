<script setup lang="ts">
/**
 * Factor badge: compact inline badge with label, mini bar, and value.
 * 因子徽章: 紧凑行内徽章, 包含标签、迷你进度条和数值。
 */
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

/** Use new token system for fill colors */
const fillColor = computed(() => {
  if (percentage.value >= 70) return 'var(--color-accent)'
  if (percentage.value >= 40) return 'var(--color-primary)'
  if (percentage.value >= 20) return 'var(--color-warning)'
  return 'var(--color-error)'
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
    <span class="text-xs text-[var(--color-text-secondary)]">
      {{ label }}
    </span>
    <div
      class="w-16 h-1.5 rounded-full overflow-hidden bg-[var(--color-border)]"
    >
      <div
        class="h-full rounded-full transition-all duration-300"
        :style="{ width: percentage + '%', backgroundColor: fillColor }"
      />
    </div>
    <span class="data-mono text-xs font-medium text-[var(--color-text-primary)]">
      {{ value.toFixed(1) }}
    </span>
  </div>
</template>
