import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { Analytics } from '../../lib/types'
import FactorSection from './FactorSection'

afterEach(cleanup)

const loadings = ['mkt_rf', 'smb', 'hml', 'rmw', 'cma', 'mom'].map((factor, i) => ({
  factor,
  beta: 1 - i * 0.3,
  t_stat: 5 - i,
  ci_low: 0.8 - i * 0.3,
  ci_high: 1.2 - i * 0.3,
}))

describe('FactorSection', () => {
  it('renders loadings, alpha, r squared and the insight', () => {
    const analytics: Analytics = {
      factors: {
        available: true,
        loadings,
        alpha_annual: 0.021,
        alpha_t: 1.1,
        r_squared: 0.83,
        n_obs: 900,
        start: '2022-01-03',
        end: '2025-06-30',
        insight: 'Tilted toward small caps; alpha is not statistically different from zero.',
      },
    }
    render(<FactorSection analytics={analytics} />)
    expect(screen.getByText(/Tilted toward small caps/)).toBeTruthy()
    expect(screen.getByText('Market')).toBeTruthy()
    expect(screen.getByText('Momentum')).toBeTruthy()
    expect(screen.getByText('2.1%')).toBeTruthy()
    expect(screen.getByText('0.83')).toBeTruthy()
    expect(screen.getAllByRole('img')).toHaveLength(6)
  })

  it('renders nothing when unavailable, missing or errored', () => {
    for (const analytics of [
      { factors: { available: false, reason: 'too few days' } },
      {},
      { factors: { error: 'boom' } },
    ] as Analytics[]) {
      const { container } = render(<FactorSection analytics={analytics} />)
      expect(container.innerHTML).toBe('')
      cleanup()
    }
  })
})
