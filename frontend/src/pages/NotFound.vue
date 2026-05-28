<script setup lang="ts">
import { h } from 'vue'
import { NButton } from 'naive-ui'
import { PhMagnifyingGlass, PhHouse } from '@phosphor-icons/vue'
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="not-found">
    <div class="not-found__card">
      <div class="not-found__icon-wrap">
        <PhMagnifyingGlass :size="40" weight="fill" class="not-found__icon" />
      </div>
      <h2 class="not-found__title">404</h2>
      <p class="not-found__desc">找不到该页面，请检查地址是否正确。</p>
      <NButton type="primary" :render-icon="() => h(PhHouse)" @click="router.push('/')">
        返回主页
      </NButton>
    </div>
  </div>
</template>

<style scoped>
.not-found {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: calc(100dvh - 52px - 48px);
}

.not-found__card {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 48px 40px;
  border-radius: 16px;
  background: var(--color-surface-elevated);
  border: 1px solid var(--color-border);
}

.not-found__icon-wrap {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: rgba(245, 158, 11, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
}

.not-found__icon {
  color: var(--color-warning);
}

.not-found__title {
  margin: 0 0 8px;
  font-size: 48px;
  font-weight: 700;
  color: var(--color-text-primary);
  font-family: var(--font-mono);
}

.not-found__desc {
  margin: 0 0 24px;
  font-size: 14px;
  color: var(--color-text-secondary);
}
</style>
