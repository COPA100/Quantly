import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { Analytics } from '../../lib/types'
import RiskContributionSection from './RiskContributionSection'

afterEach(cleanup)

describe('RiskContributionSection', () => {
  it('renders a capital bar and a risk bar per holding', () => {
    const analytics: Analytics = {
      risk_contribution: {
        holdings: [
          { ticker: 'AAPL', weight: 0.09, pct_risk: 0.18, rc: 0.03, marginal_var: 0.04 },
          { ticker: 'BND', weight: 0.91, pct_risk: 0.82, rc: 0.1, marginal_var: 0.01 },
        ],
        insight: 'AAPL is 9% of your money but 18% of your risk.',
      },
    }
    render(<RiskContributionSection analytics={analytics} />)
    expect(screen.getByText('AAPL is 9% of your money but 18% of your risk.')).toBeTruthy()
    expect(screen.getByText('AAPL')).toBeTruthy()
    expect(screen.getByLabelText('AAPL capital 9%')).toBeTruthy()
    expect(screen.getByLabelText('AAPL risk 18%')).toBeTruthy()
    expect(screen.getByLabelText('BND risk 82%')).toBeTruthy()
  })

  it('renders nothing when missing, errored or empty', () => {
    for (const analytics of [
      {},
      { risk_contribution: { error: 'boom' } },
      { risk_contribution: { holdings: [], insight: '' } },
    ] as Analytics[]) {
      const { container } = render(<RiskContributionSection analytics={analytics} />)
      expect(container.innerHTML).toBe('')
      cleanup()
    }
  })
})
