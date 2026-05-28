/**
 * YAML 策略配置四层校验核心
 * Four-layer YAML strategy validation core
 *
 * 层 1: YAML 语法 (js-yaml parse)
 * 层 2: 结构 Schema (必填字段 + 类型)
 * 层 3: 业务逻辑 (权重和、因子 ID 去重)
 * 层 4: 后端 API 校验 (由后端 strategies.py 负责)
 */

import yaml from 'js-yaml'
import { FACTOR_CATEGORIES } from './constants'
import type { StrategyCategory } from '../types/strategy'

// ── 类型 ──

export interface ValidationError {
  layer: 1 | 2 | 3
  severity: 'error' | 'warning'
  message: string
  line?: number
  column?: number
  field?: string
}

export interface ValidationResult {
  valid: boolean
  errors: ValidationError[]
  parsed?: Record<string, unknown>
}

// ── 常量 ──

const VALID_CATEGORIES: StrategyCategory[] = ['value', 'momentum', 'quality', 'growth', 'blended']
const VALID_DIRECTIONS = ['positive', 'negative']
const VALID_FILTER_TYPES = ['percentile_top', 'industry_diversify', 'market_cap_min']
const VALID_SORT_BY = ['composite_score', 'factor_exposure', 'market_cap']
const KNOWN_FACTOR_IDS = new Set<string>(Object.values(FACTOR_CATEGORIES).flat())

// ── 工具 ──

function err(
  layer: 1 | 2 | 3,
  severity: 'error' | 'warning',
  message: string,
  extra?: Partial<ValidationError>
): ValidationError {
  return { layer, severity, message, ...extra }
}

// ── 层 1: 语法 ──

function validateSyntax(raw: string): {
  errors: ValidationError[]
  parsed: Record<string, unknown> | null
} {
  if (!raw.trim()) {
    return { errors: [err(1, 'error', 'YAML 内容为空')], parsed: null }
  }
  try {
    const parsed = yaml.load(raw)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return { errors: [err(1, 'error', 'YAML 根节点必须是映射')], parsed: null }
    }
    return { errors: [], parsed: parsed as Record<string, unknown> }
  } catch (e: unknown) {
    const msg = (e as { message?: string }).message || ''
    const m = msg.match(/\((\d+):(\d+)\)/)
    return {
      errors: [
        err(1, 'error', msg.split('(')[0]?.trim() || 'YAML 语法错误', {
          line: m ? +m[1] : undefined,
          column: m ? +m[2] : undefined,
        }),
      ],
      parsed: null,
    }
  }
}

// ── 层 2: 结构 ──

function validateStructure(doc: Record<string, unknown>): ValidationError[] {
  const errors: ValidationError[] = []
  const push = (sev: 'error' | 'warning', msg: string, field?: string) =>
    errors.push(err(2, sev, msg, { field }))

  // 必填字符串
  for (const [key, enumVals] of [
    ['name', undefined],
    ['category', VALID_CATEGORIES],
  ] as const) {
    const val = doc[key as string]
    if (val === undefined || val === null) {
      push('error', `缺少必填字段 "${String(key)}"`, String(key))
    } else if (typeof val !== 'string') {
      push('error', `"${String(key)}" 必须是字符串`, String(key))
    } else if (enumVals && !(enumVals as readonly string[]).includes(val)) {
      push(
        'error',
        `"category" 值 "${val}" 无效, 可选: ${(enumVals as readonly string[]).join(', ')}`,
        'category'
      )
    }
  }

  // factors
  if (!doc.factors) {
    push('error', '缺少必填字段 "factors"', 'factors')
  } else if (!Array.isArray(doc.factors)) {
    push('error', '"factors" 必须是数组', 'factors')
  } else {
    ;(doc.factors as unknown[]).forEach((f, i) => {
      const p = `factors[${i}]`
      if (!f || typeof f !== 'object') {
        push('error', `${p} 必须是对象`, p)
        return
      }
      const r = f as Record<string, unknown>
      if (!r.id || typeof r.id !== 'string') {
        push('error', `${p}.id 缺失或不是字符串`, `${p}.id`)
      }
      if (r.weight === undefined) {
        push('error', `${p}.weight 缺失`, `${p}.weight`)
      } else if (typeof r.weight !== 'number') {
        push('error', `${p}.weight 必须是数字 (如 0.2 或 20)`, `${p}.weight`)
      }
      if (r.direction !== undefined && !VALID_DIRECTIONS.includes(r.direction as string)) {
        push('error', `${p}.direction 值 "${r.direction}" 无效`, `${p}.direction`)
      }
    })
  }

  // universe
  if (doc.universe !== undefined && (typeof doc.universe !== 'object' || !doc.universe)) {
    push('error', '"universe" 必须是对象', 'universe')
  }

  // filters
  if (doc.filters !== undefined) {
    if (!Array.isArray(doc.filters)) {
      push('error', '"filters" 必须是数组', 'filters')
    } else {
      ;(doc.filters as unknown[]).forEach((f, i) => {
        const p = `filters[${i}]`
        if (!f || typeof f !== 'object') {
          push('error', `${p} 必须是对象`, p)
          return
        }
        const r = f as Record<string, unknown>
        if (!r.type || typeof r.type !== 'string') {
          push('error', `${p}.type 缺失`, `${p}.type`)
        } else if (!VALID_FILTER_TYPES.includes(r.type as string)) {
          push('warning', `${p}.type "${r.type}" 不在常用类型中`, `${p}.type`)
        }
      })
    }
  }

  // output
  if (doc.output !== undefined) {
    if (typeof doc.output !== 'object' || !doc.output) {
      push('error', '"output" 必须是对象', 'output')
    } else {
      const o = doc.output as Record<string, unknown>
      if (o.max_stocks !== undefined && typeof o.max_stocks !== 'number') {
        push('error', 'output.max_stocks 必须是数字', 'output.max_stocks')
      }
      if (o.sort_by !== undefined && !VALID_SORT_BY.includes(o.sort_by as string)) {
        push('warning', `output.sort_by "${o.sort_by}" 不在常用选项中`, 'output.sort_by')
      }
    }
  }
  return errors
}

// ── 层 3: 业务逻辑 ──

function normalizeWeights(ws: number[]): number[] {
  if (!ws.length) return []
  const mx = Math.max(...ws.map(Math.abs))
  return mx <= 1 ? ws : ws.map((w) => w / 100)
}

function validateBusiness(doc: Record<string, unknown>): ValidationError[] {
  const errors: ValidationError[] = []
  if (!Array.isArray(doc.factors)) return errors
  const push = (sev: 'error' | 'warning', msg: string, field?: string) =>
    errors.push(err(3, sev, msg, { field }))

  const seen = new Set<string>()
  const weights: number[] = []
  ;(doc.factors as Record<string, unknown>[]).forEach((f, i) => {
    const id = f.id as string | undefined
    if (!id) return
    if (seen.has(id)) {
      push('error', `因子 ID "${id}" 重复 (factors[${i}])`, `factors[${i}].id`)
    }
    seen.add(id)
    if (!KNOWN_FACTOR_IDS.has(id)) {
      push('warning', `因子 "${id}" 不在已知列表中`, `factors[${i}].id`)
    }
    if (typeof f.weight === 'number') weights.push(f.weight)
  })

  if (weights.length > 0) {
    const sum = normalizeWeights(weights).reduce((a, b) => a + b, 0)
    if (Math.abs(sum - 1) > 0.02) {
      const d = sum <= 1 ? `${(sum * 100).toFixed(1)}%` : `${sum.toFixed(1)} (百分制)`
      push('warning', `权重之和 = ${d}, 不等于 100%`, 'factors')
    }
  }
  if (doc.output && typeof doc.output === 'object') {
    const ms = (doc.output as Record<string, unknown>).max_stocks
    if (typeof ms === 'number' && (ms < 1 || ms > 500)) {
      push('warning', `max_stocks = ${ms} 超出合理范围 (1~500)`, 'output.max_stocks')
    }
  }
  return errors
}

// ── 入口 ──

export function validateYaml(raw: string): ValidationResult {
  const syn = validateSyntax(raw)
  if (syn.errors.length > 0 || !syn.parsed) {
    return { valid: false, errors: syn.errors }
  }
  const stErrs = validateStructure(syn.parsed)
  const hasHard = stErrs.some((e) => e.severity === 'error')
  const bizErrs = hasHard ? [] : validateBusiness(syn.parsed)
  const all = [...stErrs, ...bizErrs]
  return { valid: !all.some((e) => e.severity === 'error'), errors: all, parsed: syn.parsed }
}
