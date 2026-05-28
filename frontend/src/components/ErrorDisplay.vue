<script setup lang="ts">
import { ref, h } from 'vue'
import { NButton, NTag } from 'naive-ui'
import { PhWarningOctagon, PhArrowsClockwise, PhHouse, PhBug } from '@phosphor-icons/vue'

const props = defineProps<{
  error: Error
  info: string
}>()

const showDetail = ref(false)
const isDev = import.meta.env.DEV

function handleRefresh() {
  window.location.reload()
}

function handleGoHome() {
  window.location.href = '/'
}
</script>

<template>
  <div class="error-boundary">
    <div class="error-boundary__card">
      <!-- Icon -->
      <div class="error-boundary__icon-wrap">
        <PhWarningOctagon :size="40" weight="fill" class="error-boundary__icon" />
      </div>

      <!-- Title + message -->
      <h2 class="error-boundary__title">页面出错了</h2>
      <p class="error-boundary__desc">
        应用遇到了意外错误，请尝试刷新页面。如果问题持续出现，请联系开发者。
      </p>

      <!-- Error message badge -->
      <NTag type="error" size="medium" :bordered="false" round class="error-boundary__tag">
        {{ error.message || '未知错误' }}
      </NTag>

      <!-- Actions -->
      <div class="error-boundary__actions">
        <NButton type="primary" :render-icon="() => h(PhArrowsClockwise)" @click="handleRefresh">
          刷新页面
        </NButton>
        <NButton quaternary :render-icon="() => h(PhHouse)" @click="handleGoHome">返回主页</NButton>
      </div>

      <!-- Dev-only detail toggle -->
      <div v-if="isDev" class="error-boundary__dev">
        <button class="error-boundary__detail-toggle" @click="showDetail = !showDetail">
          <PhBug :size="14" />
          {{ showDetail ? '隐藏详情' : '查看错误详情' }}
        </button>

        <Transition name="detail-slide">
          <div v-if="showDetail" class="error-boundary__detail">
            <div class="error-boundary__detail-row">
              <span class="error-boundary__detail-label">来源</span>
              <span class="error-boundary__detail-value">{{ info }}</span>
            </div>
            <div class="error-boundary__detail-row">
              <span class="error-boundary__detail-label">类型</span>
              <span class="error-boundary__detail-value">{{ error.name }}</span>
            </div>
            <pre class="error-boundary__detail-stack">{{ error.stack }}</pre>
          </div>
        </Transition>
      </div>
    </div>
  </div>
</template>

<style scoped>
.error-boundary {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: calc(100dvh - 52px - 48px);
}

.error-boundary__card {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  max-width: 480px;
  padding: 48px 40px;
  border-radius: 16px;
  background: var(--color-surface-elevated);
  border: 1px solid var(--color-border);
}

.error-boundary__icon-wrap {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: rgba(239, 68, 68, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
}

.error-boundary__icon {
  color: #ef4444;
}

.error-boundary__title {
  margin: 0 0 8px;
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.error-boundary__desc {
  margin: 0 0 20px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--color-text-secondary);
  max-width: 360px;
}

.error-boundary__tag {
  margin-bottom: 24px;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
}

.error-boundary__actions {
  display: flex;
  gap: 12px;
}

/* Dev-only detail section */
.error-boundary__dev {
  width: 100%;
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px dashed var(--color-border);
}

.error-boundary__detail-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
  font-size: 13px;
  font-family: inherit;
  transition: color 0.15s;
}

.error-boundary__detail-toggle:hover {
  color: var(--color-text-secondary);
}

.error-boundary__detail {
  margin-top: 12px;
  text-align: left;
  width: 100%;
}

.error-boundary__detail-row {
  display: flex;
  gap: 12px;
  margin-bottom: 8px;
  font-size: 13px;
}

.error-boundary__detail-label {
  flex-shrink: 0;
  width: 40px;
  color: var(--color-text-muted);
}

.error-boundary__detail-value {
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  word-break: break-all;
}

.error-boundary__detail-stack {
  margin: 12px 0 0;
  padding: 12px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.15);
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.6;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
}

/* Transition */
.detail-slide-enter-active,
.detail-slide-leave-active {
  transition:
    opacity 0.2s ease,
    max-height 0.2s ease;
  overflow: hidden;
}

.detail-slide-enter-from,
.detail-slide-leave-to {
  opacity: 0;
  max-height: 0;
}

.detail-slide-enter-to,
.detail-slide-leave-from {
  opacity: 1;
  max-height: 400px;
}
</style>
