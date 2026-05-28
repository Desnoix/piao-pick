<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import {
  NInput,
  NButton,
  NSpace,
  NForm,
  NFormItem,
  NSpin,
  NAlert,
  NSelect,
  NSlider,
  NInputNumber,
  NSwitch,
  NCollapse,
  NCollapseItem,
  NTag,
  NCode,
  NDivider,
  NBadge,
  NTooltip,
  NDrawer,
  NDrawerContent,
  useMessage,
  useDialog,
} from 'naive-ui'
import { useRouter } from 'vue-router'
import yaml from 'js-yaml'
import { getStrategy, updateStrategy, createStrategy } from '../api/strategies'
import { getFactorCoverage, type FactorCoverageData } from '../api/factorCoverage'
import FactorCoverageCard from '../components/strategy/FactorCoverageCard.vue'
import type {
  StrategyDetail,
  StrategyConfig,
  StrategyCategory,
  FactorWeight,
  FilterRule,
} from '../types/strategy'
import { FACTOR_LABELS, FACTOR_CATEGORIES } from '../utils/constants'
import { validateYaml, type ValidationResult } from '../utils/yamlValidator'

const props = defineProps<{
  id: string
}>()

const router = useRouter()
const message = useMessage()
const dialog = useDialog()

const loading = ref(false)
const saving = ref(false)
const strategy = ref<StrategyDetail | null>(null)
const isNew = ref(false)
const rawMode = ref(false)
const yamlValidation = ref<ValidationResult>({ valid: true, errors: [] })
const showValidationDrawer = ref(false)
let validateTimer: ReturnType<typeof setTimeout> | null = null

function scheduleValidation() {
  if (validateTimer) clearTimeout(validateTimer)
  validateTimer = setTimeout(() => {
    yamlValidation.value = validateYaml(rawConfig.value)
  }, 300)
}

// Factor coverage data (loaded per-strategy)
const factorCoverage = ref<FactorCoverageData | null>(null)

const name = ref('')
const displayName = ref('')
const description = ref('')
const category = ref<StrategyCategory | ''>('')
const version = ref('1.0')

const universe = ref({
  exclude_st: true,
  exclude_new_listing_days: 60,
  exclude_suspended: true,
  exclude_bse: true,
  min_market_cap: 0,
  min_daily_amount: 0,
})

const factors = ref<FactorWeight[]>([])
const filters = ref<FilterRule[]>([])
const output = ref({
  max_stocks: 30,
  sort_by: 'composite_score',
  sort_order: 'desc' as 'asc' | 'desc',
})

const rawConfig = ref('')

const categoryOptions = [
  { label: '价值', value: 'value' },
  { label: '动量', value: 'momentum' },
  { label: '质量', value: 'quality' },
  { label: '成长', value: 'growth' },
  { label: '混合', value: 'blended' },
]

const sortOptions = [
  { label: '综合得分', value: 'composite_score' },
  { label: '因子暴露', value: 'factor_exposure' },
  { label: '市值', value: 'market_cap' },
]

const filterTypeOptions = [
  { label: '百分位优选', value: 'percentile_top' },
  { label: '行业分散', value: 'industry_diversify' },
  { label: '最小市值', value: 'market_cap_min' },
]

const allFactorIds = computed(() => {
  const ids = new Set<string>()
  Object.values(FACTOR_CATEGORIES).forEach((cat) => {
    cat.forEach((id) => ids.add(id))
  })
  factors.value.forEach((f) => ids.add(f.id))
  return Array.from(ids)
})

const totalWeight = computed(() => {
  return factors.value.filter((f) => f.enabled).reduce((sum, f) => sum + f.weight, 0)
})

const weightNormalized = computed(() => {
  return Math.abs(totalWeight.value - 100) < 0.01
})

const enabledFactorCount = computed(() => {
  return factors.value.filter((f) => f.enabled).length
})

const yamlPreview = computed(() => {
  try {
    const config = buildConfigObject()
    return yaml.dump(config, { lineWidth: 120, noRefs: true })
  } catch {
    return '# YAML 生成失败'
  }
})

function getFactorLabel(id: string): string {
  return FACTOR_LABELS[id] || id
}

function getFactorCategory(factorId: string): string {
  for (const [cat, ids] of Object.entries(FACTOR_CATEGORIES)) {
    if ((ids as readonly string[]).includes(factorId)) {
      const catLabels: Record<string, string> = {
        value: '价值',
        momentum: '动量',
        quality: '质量',
        size: '规模',
      }
      return catLabels[cat] || cat
    }
  }
  return '其他'
}

function parseYamlConfig(yamlStr: string) {
  try {
    const parsed = yaml.load(yamlStr) as Record<string, unknown>
    if (!parsed || typeof parsed !== 'object') {
      throw new Error('无效的 YAML 配置')
    }

    if (parsed.name) name.value = String(parsed.name)
    if (parsed.display_name) displayName.value = String(parsed.display_name)
    if (parsed.description) description.value = String(parsed.description)
    if (parsed.category) category.value = parsed.category as StrategyCategory
    if (parsed.version) version.value = String(parsed.version)

    if (parsed.universe && typeof parsed.universe === 'object') {
      const u = parsed.universe as Record<string, unknown>
      universe.value.exclude_st = Boolean(u.exclude_st ?? true)
      universe.value.exclude_new_listing_days = Number(u.exclude_new_listing_days ?? 60)
      universe.value.exclude_suspended = Boolean(u.exclude_suspended ?? true)
      universe.value.exclude_bse = Boolean(u.exclude_bse ?? true)
      universe.value.min_market_cap = Number(u.min_market_cap ?? 0)
      universe.value.min_daily_amount = Number(u.min_daily_amount ?? 0)
    }

    if (Array.isArray(parsed.factors)) {
      const parsedFactorMap = new Map<string, FactorWeight>()
      parsed.factors.forEach((f: Record<string, unknown>) => {
        if (f.id) {
          parsedFactorMap.set(String(f.id), {
            id: String(f.id),
            weight: Number(f.weight ?? 0),
            direction: (f.direction as 'positive' | 'negative') || 'positive',
            enabled: true,
          })
        }
      })

      const merged: FactorWeight[] = []
      const seen = new Set<string>()

      parsedFactorMap.forEach((f) => {
        merged.push(f)
        seen.add(f.id)
      })

      allFactorIds.value.forEach((id) => {
        if (!seen.has(id)) {
          merged.push({ id, weight: 0, direction: 'positive', enabled: false })
        }
      })

      factors.value = merged
    } else {
      initDefaultFactors()
    }

    if (Array.isArray(parsed.filters)) {
      filters.value = parsed.filters.map((f: Record<string, unknown>) => ({
        type: String(f.type || ''),
        value: f.value !== undefined ? Number(f.value) : undefined,
        max_per_industry: f.max_per_industry !== undefined ? Number(f.max_per_industry) : undefined,
      }))
    }

    if (parsed.output && typeof parsed.output === 'object') {
      const o = parsed.output as Record<string, unknown>
      output.value.max_stocks = Number(o.max_stocks ?? 30)
      output.value.sort_by = String(o.sort_by ?? 'composite_score')
      output.value.sort_order = (o.sort_order as 'asc' | 'desc') || 'desc'
    }

    yamlValidation.value = { valid: true, errors: [] }
  } catch (e: unknown) {
    const err = e as Error
    message.error(`YAML 解析失败: ${err.message}`)
    rawMode.value = true
  }
}

function initDefaultFactors() {
  const defaults: FactorWeight[] = allFactorIds.value.map((id) => ({
    id,
    weight: 0,
    direction: 'positive',
    enabled: false,
  }))
  factors.value = defaults
}

function buildConfigObject(): StrategyConfig {
  const activeFactors: FactorWeight[] = factors.value
    .filter((f) => f.enabled)
    .map((f) => ({
      id: f.id,
      weight: f.weight,
      direction: f.direction,
      enabled: f.enabled,
    }))

  const configFilters: FilterRule[] = filters.value
    .filter((f) => f.type)
    .map((f) => {
      const rule: FilterRule = { type: f.type }
      if (f.value !== undefined) rule.value = f.value
      if (f.max_per_industry !== undefined) rule.max_per_industry = f.max_per_industry
      return rule
    })

  return {
    name: name.value,
    display_name: displayName.value,
    description: description.value,
    category: category.value || 'blended',
    version: version.value,
    default_active: true,
    default_priority: 50,
    universe: { ...universe.value },
    factors: activeFactors,
    filters: configFilters,
    output: { ...output.value },
  }
}

function serializeConfig(): string {
  const config = buildConfigObject()
  return yaml.dump(config, { lineWidth: 120, noRefs: true })
}

function normalizeWeights() {
  const enabled = factors.value.filter((f) => f.enabled)
  if (enabled.length === 0) return
  const total = enabled.reduce((sum, f) => sum + f.weight, 0)
  if (total === 0) {
    const equalWeight = Math.round(100 / enabled.length)
    enabled.forEach((f) => {
      f.weight = equalWeight
    })
    const diff = 100 - equalWeight * enabled.length
    if (diff > 0 && enabled.length > 0) {
      enabled[0].weight += diff
    }
    return
  }
  const scale = 100 / total
  enabled.forEach((f) => {
    f.weight = Math.round(f.weight * scale)
  })
  const newTotal = enabled.reduce((sum, f) => sum + f.weight, 0)
  if (newTotal !== 100 && enabled.length > 0) {
    enabled[0].weight += 100 - newTotal
  }
}

function addFilter() {
  filters.value.push({ type: 'percentile_top', value: 30 })
}

function removeFilter(index: number) {
  filters.value.splice(index, 1)
}

function toggleFactor(factorId: string, enabled: boolean) {
  const f = factors.value.find((x) => x.id === factorId)
  if (f) {
    f.enabled = enabled
    if (enabled && f.weight === 0) {
      f.weight = 10
    }
  }
}

function updateWeight(factorId: string, weight: number | null) {
  const f = factors.value.find((x) => x.id === factorId)
  if (f && weight !== null) {
    f.weight = weight
  }
}

function updateDirection(factorId: string, direction: 'positive' | 'negative') {
  const f = factors.value.find((x) => x.id === factorId)
  if (f) {
    f.direction = direction
  }
}

async function loadCoverage(strategyName: string) {
  try {
    factorCoverage.value = await getFactorCoverage(strategyName)
  } catch {
    factorCoverage.value = null
  }
}

async function load() {
  if (props.id === 'new') {
    isNew.value = true
    initDefaultFactors()
    filters.value = [{ type: 'percentile_top', value: 30 }]
    return
  }
  loading.value = true
  try {
    strategy.value = await getStrategy(props.id, { silent: true })
    name.value = strategy.value.name || ''
    displayName.value = strategy.value.display_name || ''
    description.value = strategy.value.description || ''
    category.value = (strategy.value.category as StrategyCategory) || ''
    rawConfig.value = strategy.value.config || ''

    if (!rawMode.value) {
      parseYamlConfig(strategy.value.config || '')
    }

    // Load factor coverage
    if (strategy.value.name) {
      await loadCoverage(strategy.value.name)
    }
  } catch (e: unknown) {
    const err = e as { response?: { status?: number; data?: { detail?: string } } }
    message.error(err?.response?.data?.detail || '加载失败')
    if (err?.response?.status === 404) {
      router.push('/strategy/list')
    }
  } finally {
    loading.value = false
  }
}

function handleReset() {
  dialog.warning({
    title: '确认重置',
    content: '确定要重置为上次保存的配置吗? 未保存的更改将丢失。',
    positiveText: '重置',
    negativeText: '取消',
    onPositiveClick: () => {
      if (strategy.value?.config) {
        parseYamlConfig(strategy.value.config)
        rawConfig.value = strategy.value.config
        message.info('已重置')
      }
    },
  })
}

async function save() {
  if (!name.value.trim()) {
    message.warning('请填写策略标识')
    return
  }

  if (rawMode.value) {
    const result = validateYaml(rawConfig.value)
    yamlValidation.value = result
    if (!result.valid) {
      showValidationDrawer.value = true
      message.error('YAML 校验未通过, 请查看错误列表')
      return
    }
  }

  saving.value = true
  try {
    const configStr = rawMode.value ? rawConfig.value : serializeConfig()

    if (isNew.value) {
      await createStrategy({
        name: name.value,
        display_name: displayName.value || undefined,
        description: description.value || undefined,
        category: category.value || undefined,
        config: configStr,
      })
      message.success('已创建')
    } else {
      await updateStrategy(props.id, {
        display_name: displayName.value || undefined,
        description: description.value || undefined,
        category: category.value || undefined,
        config: configStr,
      })
      message.success('已保存')
    }
    router.push('/strategy/list')
  } catch (e: unknown) {
    // 忽略请求取消错误（来自 client.ts 的请求去重机制）
    if ((e as any)?.code === 'ERR_CANCELED' || (e as any)?.name === 'CanceledError') return
    const err = e as { response?: { data?: { detail?: string } }; message?: string }
    message.error(err?.response?.data?.detail || err?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

function toggleRawMode() {
  if (!rawMode.value) {
    rawConfig.value = serializeConfig()
    rawMode.value = true
    scheduleValidation()
  } else {
    const result = validateYaml(rawConfig.value)
    yamlValidation.value = result
    if (!result.valid) {
      showValidationDrawer.value = true
      message.error('YAML 存在错误, 请修正后再切换')
      return
    }
    parseYamlConfig(rawConfig.value)
    rawMode.value = false
  }
}

onMounted(load)

watch(
  [factors, universe, filters, output],
  () => {
    if (!rawMode.value) {
      rawConfig.value = serializeConfig()
    }
  },
  { deep: true }
)

watch(rawConfig, () => {
  if (rawMode.value) scheduleValidation()
})
</script>

<template>
  <NSpin :show="loading">
    <div class="strategy-edit flex max-w-[1200px] flex-col gap-6">
      <!-- Action bar -->
      <div class="action-bar">
        <div class="action-bar__left">
          <NButton size="small" ghost @click="router.push('/strategy/list')">取消</NButton>
          <NButton v-if="!isNew" size="small" ghost @click="handleReset">重置</NButton>
        </div>
        <div class="action-bar__right">
          <button
            class="mode-toggle"
            :class="{ 'mode-toggle--raw': rawMode }"
            @click="toggleRawMode"
          >
            <span class="mode-toggle__dot" />
            <span class="mode-toggle__label">{{ rawMode ? '可视化编辑' : 'YAML 模式' }}</span>
          </button>
          <NButton type="primary" :loading="saving" @click="save">保存策略</NButton>
        </div>
      </div>

      <!-- Raw YAML Mode -->
      <template v-if="rawMode">
        <div class="glass-panel flex flex-col gap-4 p-6">
          <NForm v-if="isNew" label-placement="left" label-width="100">
            <NFormItem label="标识">
              <NInput v-model:value="name" placeholder="策略唯一标识 (英文)" />
            </NFormItem>
          </NForm>
          <div>
            <div class="mb-2 flex items-center justify-between">
              <span class="section-label">YAML 配置</span>
              <NTag
                v-if="yamlValidation.errors.length > 0"
                size="small"
                :type="yamlValidation.valid ? 'warning' : 'error'"
                :bordered="false"
                class="cursor-pointer"
                @click="showValidationDrawer = true"
              >
                {{
                  yamlValidation.valid
                    ? `${yamlValidation.errors.length} 个警告`
                    : `${yamlValidation.errors.filter((e) => e.severity === 'error').length} 个错误`
                }}
              </NTag>
              <NTag v-else size="small" type="success" :bordered="false">校验通过</NTag>
            </div>
            <NInput
              v-model:value="rawConfig"
              type="textarea"
              :rows="30"
              placeholder="策略 YAML 配置"
              class="yaml-editor font-mono"
              :class="{
                'yaml-editor--error': !yamlValidation.valid,
                'yaml-editor--warn': yamlValidation.valid && yamlValidation.errors.length > 0,
              }"
            />
          </div>
        </div>
      </template>

      <!-- Visual Editor Mode -->
      <template v-else>
        <!-- Basic info -->
        <section class="flex flex-col gap-2">
          <span class="section-label">基本信息</span>
          <div class="grid grid-cols-1 gap-5 md:grid-cols-2">
            <NForm label-placement="left" label-width="80" class="glass-panel p-5">
              <NFormItem v-if="isNew" label="标识">
                <NInput v-model:value="name" placeholder="策略唯一标识 (英文)" />
              </NFormItem>
              <NFormItem label="名称">
                <NInput v-model:value="displayName" placeholder="显示名称" />
              </NFormItem>
              <NFormItem label="类别">
                <NSelect
                  v-model:value="category"
                  :options="categoryOptions"
                  placeholder="选择类别"
                  clearable
                />
              </NFormItem>
            </NForm>
            <NForm label-placement="left" label-width="80" class="glass-panel p-5">
              <NFormItem label="描述">
                <NInput
                  v-model:value="description"
                  type="textarea"
                  :rows="3"
                  placeholder="策略描述"
                />
              </NFormItem>
            </NForm>
          </div>
        </section>

        <!-- Universe filters -->
        <NCollapse :default-expanded-names="['universe']" arrow-placement="left">
          <NCollapseItem name="universe">
            <template #header>
              <div class="collapse-header">
                <span class="collapse-header__label">选股条件</span>
                <span class="collapse-header__title">选股池</span>
              </div>
            </template>
            <div class="glass-panel grid grid-cols-1 gap-5 p-5 md:grid-cols-2">
              <div class="flex flex-col gap-3">
                <div class="universe-row">
                  <span class="universe-row__label">排除 ST 股票</span>
                  <NSwitch v-model:value="universe.exclude_st" />
                </div>
                <div class="universe-row">
                  <span class="universe-row__label">排除停牌股</span>
                  <NSwitch v-model:value="universe.exclude_suspended" />
                </div>
                <div class="universe-row">
                  <span class="universe-row__label">排除北交所</span>
                  <NSwitch v-model:value="universe.exclude_bse" />
                </div>
                <div class="universe-row">
                  <span class="universe-row__label">排除次新股 (上市天数)</span>
                  <NInputNumber
                    v-model:value="universe.exclude_new_listing_days"
                    :min="0"
                    :max="365"
                    size="small"
                    style="width: 120px"
                  />
                </div>
              </div>
              <div class="flex flex-col gap-3">
                <div class="universe-row">
                  <span class="universe-row__label">最小市值 (亿元)</span>
                  <NInputNumber
                    v-model:value="universe.min_market_cap"
                    :min="0"
                    :step="10"
                    size="small"
                    style="width: 160px"
                  />
                </div>
                <div class="universe-row">
                  <span class="universe-row__label">最小日均成交额 (万元)</span>
                  <NInputNumber
                    v-model:value="universe.min_daily_amount"
                    :min="0"
                    :step="100"
                    size="small"
                    style="width: 160px"
                  />
                </div>
              </div>
            </div>
          </NCollapseItem>
        </NCollapse>

        <!-- Factor weights -->
        <NCollapse :default-expanded-names="['factors']" arrow-placement="left">
          <NCollapseItem name="factors">
            <template #header>
              <div class="collapse-header">
                <span class="collapse-header__label">因子配置</span>
                <span class="collapse-header__title">因子权重</span>
                <span
                  class="weight-status"
                  :class="weightNormalized ? 'weight-status--ok' : 'weight-status--warn'"
                >
                  {{ enabledFactorCount }} 项 / {{ totalWeight }}%
                </span>
                <NButton
                  v-if="!weightNormalized && enabledFactorCount > 0"
                  size="tiny"
                  type="primary"
                  ghost
                  @click.stop="normalizeWeights"
                >
                  自动归一
                </NButton>
              </div>
            </template>
            <div class="glass-panel factor-panel">
              <div
                v-if="factors.length === 0"
                class="py-10 text-center text-sm text-[var(--color-text-muted)]"
              >
                暂无可用因子
              </div>
              <div
                v-for="(factor, idx) in factors"
                :key="factor.id"
                class="factor-row"
                :class="{
                  'factor-row--disabled': !factor.enabled,
                  'factor-row--last': idx === factors.length - 1,
                }"
              >
                <NSwitch
                  :value="factor.enabled"
                  size="small"
                  @update:value="(val: boolean) => toggleFactor(factor.id, val)"
                />
                <div class="factor-row__info">
                  <div class="factor-row__name">{{ getFactorLabel(factor.id) }}</div>
                  <NTag size="tiny" :bordered="false">{{ getFactorCategory(factor.id) }}</NTag>
                </div>
                <NTooltip>
                  <template #trigger>
                    <NTag
                      size="tiny"
                      :type="factor.direction === 'positive' ? 'error' : 'success'"
                      :bordered="false"
                      class="cursor-pointer"
                      @click="
                        updateDirection(
                          factor.id,
                          factor.direction === 'positive' ? 'negative' : 'positive'
                        )
                      "
                    >
                      {{ factor.direction === 'positive' ? '正向' : '负向' }}
                    </NTag>
                  </template>
                  点击切换因子方向
                </NTooltip>
                <NSlider
                  :value="factor.weight"
                  :min="0"
                  :max="100"
                  :step="5"
                  :disabled="!factor.enabled"
                  class="min-w-[100px] flex-1"
                  @update:value="(val: number) => updateWeight(factor.id, val)"
                />
                <NInputNumber
                  :value="factor.weight"
                  :min="0"
                  :max="100"
                  :step="5"
                  :disabled="!factor.enabled"
                  size="small"
                  style="width: 80px"
                  @update:value="(val: number | null) => updateWeight(factor.id, val)"
                />
              </div>
            </div>
          </NCollapseItem>
        </NCollapse>

        <!-- Factor coverage alert -->
        <FactorCoverageCard
          v-if="factorCoverage && factorCoverage.stub_factors.length > 0"
          :data="factorCoverage"
        />

        <!-- Filter rules -->
        <NCollapse :default-expanded-names="['filters']" arrow-placement="left">
          <NCollapseItem name="filters">
            <template #header>
              <div class="collapse-header">
                <span class="collapse-header__label">筛选条件</span>
                <span class="collapse-header__title">过滤规则</span>
              </div>
            </template>
            <div class="glass-panel filter-panel p-5">
              <div
                v-for="(filter, index) in filters"
                :key="index"
                class="filter-row"
                :class="{ 'filter-row--last': index === filters.length - 1 }"
              >
                <NSelect
                  v-model:value="filter.type"
                  :options="filterTypeOptions"
                  size="small"
                  style="width: 160px"
                />
                <template v-if="filter.type === 'percentile_top'">
                  <span class="filter-row__text">保留前</span>
                  <NInputNumber
                    v-model:value="filter.value"
                    :min="1"
                    :max="200"
                    size="small"
                    style="width: 100px"
                  />
                  <span class="filter-row__unit">只</span>
                </template>
                <template v-else-if="filter.type === 'industry_diversify'">
                  <span class="filter-row__text">每行业最多</span>
                  <NInputNumber
                    v-model:value="filter.max_per_industry"
                    :min="1"
                    :max="30"
                    size="small"
                    style="width: 100px"
                  />
                  <span class="filter-row__unit">只</span>
                </template>
                <template v-else-if="filter.type === 'market_cap_min'">
                  <span class="filter-row__text">最小市值</span>
                  <NInputNumber
                    v-model:value="filter.value"
                    :min="0"
                    :step="10"
                    size="small"
                    style="width: 140px"
                  />
                  <span class="filter-row__unit">亿元</span>
                </template>
                <NButton size="small" type="error" ghost @click="removeFilter(index)">删除</NButton>
              </div>
              <NButton size="small" dashed @click="addFilter">添加过滤规则</NButton>
            </div>
          </NCollapseItem>
        </NCollapse>

        <!-- Output settings -->
        <NCollapse :default-expanded-names="['output']" arrow-placement="left">
          <NCollapseItem name="output">
            <template #header>
              <div class="collapse-header">
                <span class="collapse-header__label">结果配置</span>
                <span class="collapse-header__title">输出设置</span>
              </div>
            </template>
            <div class="glass-panel grid grid-cols-1 gap-5 p-5 md:grid-cols-3">
              <div>
                <span class="field-label">最大股票数</span>
                <NInputNumber
                  v-model:value="output.max_stocks"
                  :min="1"
                  :max="500"
                  size="small"
                  class="w-full"
                />
              </div>
              <div>
                <span class="field-label">排序依据</span>
                <NSelect v-model:value="output.sort_by" :options="sortOptions" size="small" />
              </div>
              <div>
                <span class="field-label">排序方向</span>
                <NSpace align="center" :size="8">
                  <NTag
                    size="small"
                    :type="output.sort_order === 'desc' ? 'error' : 'default'"
                    :bordered="false"
                    class="cursor-pointer"
                    @click="output.sort_order = 'desc'"
                  >
                    降序
                  </NTag>
                  <NTag
                    size="small"
                    :type="output.sort_order === 'asc' ? 'success' : 'default'"
                    :bordered="false"
                    class="cursor-pointer"
                    @click="output.sort_order = 'asc'"
                  >
                    升序
                  </NTag>
                </NSpace>
              </div>
            </div>
          </NCollapseItem>
        </NCollapse>

        <!-- YAML live preview -->
        <section class="flex flex-col gap-2">
          <span class="section-label">实时预览</span>
          <div class="glass-panel yaml-preview">
            <pre class="yaml-preview__code">{{ yamlPreview }}</pre>
          </div>
        </section>
      </template>
    </div>

    <!-- YAML Validation Drawer -->
    <NDrawer v-model:show="showValidationDrawer" :width="420" placement="right">
      <NDrawerContent title="YAML 校验结果" :native-scrollbar="false">
        <div class="flex flex-col gap-3">
          <div
            v-for="(e, idx) in yamlValidation.errors"
            :key="idx"
            class="validation-item"
            :class="`validation-item--${e.severity}`"
          >
            <div class="validation-item__header">
              <NTag
                size="tiny"
                :type="e.severity === 'error' ? 'error' : 'warning'"
                :bordered="false"
              >
                {{ e.severity === 'error' ? '错误' : '警告' }}
              </NTag>
              <span v-if="e.line" class="validation-item__loc">
                第 {{ e.line }} 行
                <template v-if="e.column">, 第 {{ e.column }} 列</template>
              </span>
              <span v-if="e.field" class="validation-item__loc">{{ e.field }}</span>
            </div>
            <div class="validation-item__msg">{{ e.message }}</div>
          </div>
          <div v-if="yamlValidation.errors.length === 0" class="py-8 text-center">
            <NTag type="success" size="large" :bordered="false">全部校验通过</NTag>
          </div>
        </div>
      </NDrawerContent>
    </NDrawer>
  </NSpin>
</template>

<style scoped>
/* === Section labels === */
.section-label {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.06em;
  color: var(--color-text-muted);
}

.field-label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-secondary);
  margin-bottom: 6px;
}

/* === Action bar === */
.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}

.action-bar__left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.action-bar__right {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* Mode toggle button */
.mode-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 6px;
  border: 1px solid var(--color-border);
  background: transparent;
  cursor: pointer;
  font-size: 13px;
  font-family: inherit;
  color: var(--color-text-secondary);
  transition:
    border-color 0.15s ease,
    color 0.15s ease,
    background-color 0.15s ease;
}

.mode-toggle:hover {
  border-color: var(--color-accent);
  color: var(--color-text-primary);
}

.mode-toggle--raw {
  border-color: var(--color-accent);
  background: var(--color-accent-muted);
  color: var(--color-accent);
}

.mode-toggle__dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--color-border-muted);
  transition: background-color 0.15s ease;
}

.mode-toggle--raw .mode-toggle__dot {
  background: var(--color-accent);
}

.mode-toggle__label {
  line-height: 1;
}

/* === Collapse header pattern === */
.collapse-header {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}

.collapse-header__label {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.06em;
  color: var(--color-text-muted);
}

.collapse-header__title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-text-primary);
}

/* Weight status badge in factor header */
.weight-status {
  font-size: 12px;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  padding: 2px 8px;
  border-radius: 4px;
}

.weight-status--ok {
  color: var(--color-success);
  background: rgba(34, 197, 94, 0.1);
}

.weight-status--warn {
  color: var(--color-warning);
  background: rgba(245, 158, 11, 0.1);
}

/* === Universe rows === */
.universe-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 0;
  border-bottom: 1px solid var(--color-border);
}

.universe-row:last-child {
  border-bottom: none;
}

.universe-row__label {
  font-size: 13px;
  color: var(--color-text-secondary);
}

/* === Factor panel + rows === */
.factor-panel {
  padding: 4px 0;
}

.factor-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--color-border);
  transition:
    background-color 0.12s ease,
    opacity 0.2s ease;
}

.factor-row:hover {
  background: var(--color-glass-highlight);
}

.factor-row--last {
  border-bottom: none;
}

.factor-row--disabled {
  opacity: 0.35;
}

.factor-row__info {
  width: 120px;
  flex-shrink: 0;
}

.factor-row__name {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-primary);
  line-height: 1.3;
}

/* === Filter rows === */
.filter-panel {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid var(--color-border);
}

.filter-row--last {
  border-bottom: none;
  padding-bottom: 12px;
}

.filter-row__text {
  font-size: 13px;
  color: var(--color-text-secondary);
  white-space: nowrap;
}

.filter-row__unit {
  font-size: 12px;
  color: var(--color-text-muted);
}

/* === YAML preview === */
.yaml-preview {
  overflow: hidden;
}

.yaml-preview__code {
  font-size: 12px;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  padding: 16px 20px;
  margin: 0;
  background: var(--color-surface-inset);
  overflow: auto;
  max-height: 400px;
  white-space: pre;
  color: var(--color-text-primary);
  line-height: 1.6;
}

/* === Raw mode YAML editor === */
.yaml-editor :deep(textarea) {
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.6;
}

.yaml-editor--error :deep(textarea) {
  border-color: var(--color-error);
  box-shadow: 0 0 0 1px rgba(239, 68, 68, 0.2);
}

.yaml-editor--warn :deep(textarea) {
  border-color: var(--color-warning);
  box-shadow: 0 0 0 1px rgba(245, 158, 11, 0.2);
}

/* === Validation drawer items === */
.validation-item {
  padding: 10px 12px;
  border-radius: 6px;
  border: 1px solid var(--color-border);
}

.validation-item--error {
  border-color: rgba(239, 68, 68, 0.3);
  background: rgba(239, 68, 68, 0.04);
}

.validation-item--warning {
  border-color: rgba(245, 158, 11, 0.3);
  background: rgba(245, 158, 11, 0.04);
}

.validation-item__header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.validation-item__loc {
  font-size: 12px;
  font-family: var(--font-mono);
  color: var(--color-text-muted);
}

.validation-item__msg {
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.5;
}
</style>
