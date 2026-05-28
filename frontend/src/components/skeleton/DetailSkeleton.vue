<script setup lang="ts">
/**
 * Detail skeleton: simulates stock code, score, and factor field rows (label + bar + value).
 * 详情页骨架: 模拟股票代码、评分、因子字段行 (标签 + 进度条 + 数值)。
 */
import { NSkeleton } from 'naive-ui'

defineProps<{
  /** 字段行数 / Number of field rows, default 8 */
  rows?: number
}>()
</script>

<template>
  <div class="detail-skeleton">
    <!-- Stock code placeholder -->
    <NSkeleton width="100px" height="22px" :sharp="false" class="mb-3" />
    <NSkeleton width="60px" height="14px" :sharp="false" class="mb-5" />

    <!-- Large score placeholder -->
    <NSkeleton width="80px" height="32px" :sharp="false" class="mb-6" />

    <!-- Factor rows: label + bar + value -->
    <div v-for="r in rows ?? 8" :key="r" class="detail-skeleton__row">
      <NSkeleton width="56px" height="12px" :sharp="false" />
      <NSkeleton height="4px" class="flex-1" :sharp="false" />
      <NSkeleton width="24px" height="12px" :sharp="false" />
    </div>
  </div>
</template>

<style scoped>
.detail-skeleton {
  display: flex;
  flex-direction: column;
  padding: 20px;
}

.detail-skeleton__row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px solid var(--color-glass-highlight);
}

.detail-skeleton__row:last-child {
  border-bottom: none;
}
</style>
