import type { Analytics } from './types'

// an analyzer that failed on the worker writes this in place of its result
export interface MetricError {
  error: string
}

export function isMetricError(value: unknown): value is MetricError {
  return (
    typeof value === 'object' &&
    value !== null &&
    'error' in value &&
    typeof (value as MetricError).error === 'string'
  )
}

// a metric's value, or undefined when it is missing or failed. new analyzers
// declare their result type next to their component and read it through this.
export function metric<T>(analytics: Analytics, key: string): T | undefined {
  const value = analytics[key]
  if (value === undefined || value === null || isMetricError(value)) return undefined
  return value as T
}
