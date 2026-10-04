import { describe, expect, it } from 'vitest'
import { formatCurrency, formatDate, formatPercent } from './format'

describe('formatPercent', () => {
  it('converts a fraction to a percent with one digit by default', () => {
    expect(formatPercent(0.1234)).toBe('12.3%')
  })

  it('respects the digits argument', () => {
    expect(formatPercent(0.1234, 0)).toBe('12%')
    expect(formatPercent(0.1234, 3)).toBe('12.340%')
  })

  it('keeps the sign on negatives', () => {
    expect(formatPercent(-0.05)).toBe('-5.0%')
  })

  it('handles zero', () => {
    expect(formatPercent(0)).toBe('0.0%')
  })
})

describe('formatCurrency', () => {
  it('formats as usd with grouping and cents', () => {
    const out = formatCurrency(1234567.5)
    expect(out).toContain('1,234,567.50')
    expect(out).toContain('$')
  })

  it('formats negatives', () => {
    expect(formatCurrency(-12)).toMatch(/-.*12\.00|\(.*12\.00\)/)
  })
})

describe('formatDate', () => {
  it('renders year, short month and day', () => {
    const out = formatDate('2024-03-15T12:00:00Z')
    expect(out).toContain('2024')
    expect(out).toContain('15')
    expect(out).toMatch(/Mar/)
  })
})
