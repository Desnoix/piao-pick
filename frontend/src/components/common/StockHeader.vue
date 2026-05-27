<script setup lang="ts">
/**
 * Stock header: name, code, industry badge, price + pct change.
 * 股票头部: 名称、代码、行业标签、价格与涨跌幅。
 */
import { formatPrice, formatPct, getPctColor } from '../../utils/format'

defineProps<{
  name: string
  ts_code: string
  close?: number | null
  pct_change?: number | null
  industry?: string | null
}>()
</script>

<template>
  <div class="flex items-center gap-6 flex-wrap">
    <!-- Name + code -->
    <div class="flex items-baseline gap-3">
      <h1 class="text-2xl font-bold leading-tight text-[var(--color-text-primary)]">
        {{ name }}
      </h1>
      <span class="text-sm data-mono text-[var(--color-text-muted)]">
        {{ ts_code }}
      </span>
    </div>

    <!-- Industry badge -->
    <span
      v-if="industry"
      class="inline-flex items-center px-3 py-1 rounded-md text-xs font-medium border"
      style="
        background-color: var(--color-surface-inset);
        color: var(--color-text-secondary);
        border-color: var(--color-border);
      "
    >
      {{ industry }}
    </span>

    <!-- Price + pct change (right-aligned) -->
    <div
      v-if="close !== null && close !== undefined"
      class="ml-auto flex items-baseline gap-4"
    >
      <div class="text-2xl font-bold data-mono text-[var(--color-text-primary)]">
        {{ formatPrice(close) }}
      </div>
      <div
        class="text-lg data-mono font-semibold"
        :class="getPctColor(pct_change)"
      >
        {{ formatPct(pct_change) }}
      </div>
    </div>
  </div>
</template>
