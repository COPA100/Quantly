import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { Analytics } from '../../lib/types'
import FrontierSection from './FrontierSection'

afterEach(cleanup)

const portfolio = (vol: number, ret: number, a: number) => ({
  vol,
  ret,
  weights: { AAA: a, BBB: 1 - a },
})

const fixture: Analytics = {
  frontier: {
    points: [
      { vol: 0.1, ret: 0.05 },
      { vol: 0.15, ret: 0.08 },
      { vol: 0.2, ret: 0.1 },
    ],
    current: portfolio(0.16, 0.06, 0.7),
    min_variance: portfolio(0.1, 0.05, 0.3),
    max_sharpe: portfolio(0.15, 0.08, 0.5),
    risk_parity: portfolio(0.12, 0.06, 0.4),
    insight: 'At your current risk, an in-sample optimal mix would have returned 2.0% more a year.',
  },
}

describe('FrontierSection', () => {
  it('renders the insight, legend and weights table', () => {
    render(<FrontierSection analytics={fixture} />)
    expect(screen.getByText(/2.0% more a year/)).toBeTruthy()
    expect(screen.getByRole('img', { name: /efficient frontier/i })).toBeTruthy()
    // once in the legend, once as a table column
    expect(screen.getAllByText('Max Sharpe')).toHaveLength(2)
    expect(screen.getByText('Volatility (annualized)')).toBeTruthy()
    // AAA is 70% of the current mix, BBB is 70% of min variance
    expect(screen.getAllByText('70.0%')).toHaveLength(2)
  })

  it('renders nothing without data', () => {
    const { container } = render(<FrontierSection analytics={{}} />)
    expect(container.innerHTML).toBe('')
  })

  it('renders nothing for a failed or empty frontier', () => {
    const failed = render(<FrontierSection analytics={{ frontier: { error: 'boom' } }} />)
    expect(failed.container.innerHTML).toBe('')
    cleanup()
    const empty = render(
      <FrontierSection analytics={{ frontier: { points: [], current: null, insight: 'too short' } }} />,
    )
    expect(empty.container.innerHTML).toBe('')
  })
})
