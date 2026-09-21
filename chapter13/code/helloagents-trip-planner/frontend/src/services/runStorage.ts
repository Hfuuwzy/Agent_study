// 终态运行信封的 sessionStorage 存取：读取防御式校验，不据缺失推断成功。

import type { TerminalRunStatus, TripPlan, TripRunResult } from '@/types'

export const TRIP_RUN_RESULT_KEY = 'tripRunResult'

const TERMINAL_STATUSES: readonly TerminalRunStatus[] = ['success', 'degraded', 'failed']

function isTerminalStatus(value: unknown): value is TerminalRunStatus {
  return typeof value === 'string' && (TERMINAL_STATUSES as readonly string[]).includes(value)
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string')
}

function hasStringFields(value: unknown, fields: readonly string[]): boolean {
  if (typeof value !== 'object' || value === null) return false
  const record = value as Record<string, unknown>
  return fields.every((field) => typeof record[field] === 'string')
}

function isTripPlan(value: unknown): value is TripPlan {
  if (typeof value !== 'object' || value === null) return false
  const record = value as Record<string, unknown>
  return (
    hasStringFields(value, ['city', 'start_date', 'end_date', 'overall_suggestions']) &&
    Array.isArray(record.days)
  )
}

export function isTripRunResult(value: unknown): value is TripRunResult {
  if (typeof value !== 'object' || value === null) return false
  const record = value as Record<string, unknown>
  return (
    typeof record.run_id === 'string' &&
    isTerminalStatus(record.status) &&
    isStringArray(record.warnings) &&
    (record.result === null || record.result === undefined || isTripPlan(record.result)) &&
    (record.error === null || record.error === undefined || typeof record.error === 'string')
  )
}

/** 防御式读取：存储不可用 / 缺少 / 结构非法一律返回 null，不推断成成功。 */
export function loadTripRunResult(): TripRunResult | null {
  let raw: string | null = null
  try {
    raw = sessionStorage.getItem(TRIP_RUN_RESULT_KEY)
  } catch {
    return null
  }
  if (!raw) return null
  try {
    const parsed: unknown = JSON.parse(raw)
    return isTripRunResult(parsed) ? parsed : null
  } catch {
    return null
  }
}

/** 写入完整终态信封；存储不可用（配额/隐私模式等）时抛错，由调用方如实处理。 */
export function saveTripRunResult(envelope: TripRunResult): void {
  sessionStorage.setItem(TRIP_RUN_RESULT_KEY, JSON.stringify(envelope))
}

/** 清除终态信封，防止残留的旧 run 结果后续被误读为本次运行。 */
export function clearTripRunResult(): void {
  try {
    sessionStorage.removeItem(TRIP_RUN_RESULT_KEY)
  } catch {
    // 存储不可用时无需再清理
  }
}