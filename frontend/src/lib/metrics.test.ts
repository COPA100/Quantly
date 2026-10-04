import { describe, expect, it } from 'vitest'
import { isMetricError, metric } from './metrics'
import type { Analytics } from './types'

describe('metric', () => {
  const analytics: Analytics = {
    beta: { beta: 1.2 },
    frontier: { error: 'optimizer did not converge' },
  }

  it('returns a present metric', () => {
    expect(metric<{ beta: number }>(analytics, 'beta')).toEqual({ beta: 1.2 })
  })

  it('hides missing and failed metrics', () => {
    expect(metric(analytics, 'stress')).toBeUndefined()
    expect(metric(analytics, 'frontier')).toBeUndefined()
  })
})

describe('isMetricError', () => {
  it('recognizes only error blobs', () => {
    expect(isMetricError({ error: 'x' })).toBe(true)
    expect(isMetricError({ error: 1 })).toBe(false)
    expect(isMetricError(null)).toBe(false)
    expect(isMetricError({ beta: 1 })).toBe(false)
  })
})
