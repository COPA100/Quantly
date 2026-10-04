import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { Analytics } from '../../lib/types'
import VarSection from './VarSection'
import type { VarSuite } from './VarSection'

afterEach(cleanup)

const est = (v: number) => ({ var: v, es: v * 1.3 })
const cell = (v: number) => ({
  historical: est(v),
  parametric: est(v * 1.01),
  cornish_fisher: est(v * 1.02),
  monte_carlo: est(v * 0.99),
})

const suite: VarSuite = {
  methods: {
    '1d': { '0.95': cell(0.02), '0.99': cell(0.03) },
    '21d': { '0.95': cell(0.08), '0.99': cell(0.12) },
  },
  insight: 'Returns are close to normal, so the methods agree.',
  backtest: {
    dates: ['2025-01-01', '2025-01-02', '2025-01-03', '2025-01-04'],
    returns: [0.01, -0.03, 0.002, -0.001],
    var: [0.02, 0.02, 0.02, 0.02],
    exception_indices: [1],
    n: 4,
    exceptions: 1,
    expected: 0.2,
    kupiec: { lr: 1.2, p: 0.27 },
    christoffersen: { lr: 0, p: 1 },
    verdict: 'VaR was well calibrated: 1 breaches vs 0 expected (p=0.27).',
  },
}

describe('VarSection', () => {
  it('renders the comparison table, verdict and highlights breaches', () => {
    const { container } = render(<VarSection analytics={{ var_suite: suite } as Analytics} />)
    expect(screen.getByText('Cornish-Fisher')).toBeTruthy()
    expect(screen.getByText('2.00% / 2.60%')).toBeTruthy()
    expect(screen.getByText(/well calibrated/)).toBeTruthy()
    expect(container.querySelectorAll('rect[data-breach="true"]')).toHaveLength(1)
  })

  it('switches to the 21 day table', () => {
    render(<VarSection analytics={{ var_suite: suite } as Analytics} />)
    fireEvent.click(screen.getByText('21 days'))
    expect(screen.getByText('8.00% / 10.40%')).toBeTruthy()
  })

  it('shows the reason when the backtest is missing', () => {
    const noBt = { ...suite, backtest: null, backtest_reason: 'Not enough history.' }
    render(<VarSection analytics={{ var_suite: noBt } as Analytics} />)
    expect(screen.getByText('Not enough history.')).toBeTruthy()
  })

  it('renders nothing when the metric is missing or failed', () => {
    const missing = render(<VarSection analytics={{}} />)
    expect(missing.container.innerHTML).toBe('')
    const failed = render(<VarSection analytics={{ var_suite: { error: 'boom' } }} />)
    expect(failed.container.innerHTML).toBe('')
  })
})
