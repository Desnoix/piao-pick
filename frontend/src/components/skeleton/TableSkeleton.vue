<script setup lang="ts">
/**
 * Table skeleton: simulates header + N data rows with pulsing blocks.
 * 表格骨架: 模拟表头 + N 行数据行的脉动占位。
 */
import { NSkeleton } from 'naive-ui'

defineProps<{
  /** 列数 / Number of columns, default 6 */
  columns?: number
  /** 行数 / Number of rows, default 8 */
  rows?: number
}>()
</script>

<template>
  <div class="table-skeleton">
    <!-- Header: darker bars -->
    <div class="table-skeleton__head">
      <NSkeleton
        v-for="c in columns ?? 6"
        :key="'h' + c"
        width="80px"
        height="12px"
        :sharp="false"
      />
    </div>

    <!-- Data rows -->
    <div v-for="r in rows ?? 8" :key="'r' + r" class="table-skeleton__row">
      <NSkeleton
        v-for="c in columns ?? 6"
        :key="c"
        text
        :style="{ width: `${60 + ((c * 17) % 60)}px` }"
        height="14px"
        :sharp="false"
      />
    </div>
  </div>
</template>

<style scoped>
.table-skeleton {
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 12px 16px;
}

.table-skeleton__head {
  display: flex;
  gap: 24px;
  padding: 8px 0 12px;
  border-bottom: 1px solid var(--color-border);
}

.table-skeleton__row {
  display: flex;
  gap: 24px;
  padding: 10px 0;
  border-bottom: 1px solid var(--color-glass-highlight);
}

.table-skeleton__row:last-child {
  border-bottom: none;
}
</style>
