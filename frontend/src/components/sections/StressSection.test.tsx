import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import StressSection from './StressSection'

afterEach(cleanup)

const stress = {
  insight: 'In the COVID crash this portfolio would have lost about 22%, vs -20% for the S&P 500.',
  scenarios: [
    {
      name: 'COVID crash',
      start: '2020-02-19',
      end: '2020-03-23',
      portfolio_return: -0.22,
      benchmark_return: -0.2,
      worst: { ticker: 'AAA', return: -0.3 },
      proxied_weight: 0.4,
      holdings: [],
    },
    {
      name: '2022 rate shock',
      start: '2022-01-03',
      end: '2022-10-12',
      portfolio_return: -0.1,
      benchmark_return: -0.15,
      worst: null,
      proxied_weight: 0,
      holdings: [],
    },
  ],
}

describe('StressSection', () => {
  it('opens on the worst scenario, with its proxy note', () => {
    render(<StressSection analytics={{ stress }} />)
    expect(screen.getByText(/lost about 22%/)).toBeTruthy()
    // listed once and shown in the detail panel
    expect(screen.getAllByText('COVID crash')).toHaveLength(2)
    expect(screen.getByRole('heading', { name: 'COVID crash' })).toBeTruthy()
    expect(screen.getByRole('button', { name: /COVID crash/, pressed: true })).toBeTruthy()
    expect(screen.getAllByText('-22.0%').length).toBeGreaterThan(0)
    expect(screen.getByText('40% of the book estimated from beta')).toBeTruthy()
  })

  it('shows the scenario you pick', () => {
    render(<StressSection analytics={{ stress }} />)
    fireEvent.click(screen.getByRole('button', { name: /2022 rate shock/ }))
    expect(screen.getByRole('heading', { name: '2022 rate shock' })).toBeTruthy()
    // nothing in that scenario was estimated
    expect(screen.queryByText(/estimated from beta/)).toBeNull()
  })

  it('renders nothing when missing, errored or empty', () => {
    for (const analytics of [
      {},
      { stress: { error: 'boom' } },
      { stress: { scenarios: [], insight: '' } },
    ]) {
      const { container } = render(<StressSection analytics={analytics} />)
      expect(container.innerHTML).toBe('')
      cleanup()
    }
  })
})
