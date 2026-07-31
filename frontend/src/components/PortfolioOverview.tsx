import { formatCurrency } from '../lib/format'
import type { Analytics } from '../lib/types'
import AllocationBars from './AllocationBars'
import Section from './Section'
import StatTile from './StatTile'

function signed(value: number, format: (n: number) => string): string {
  return `${value >= 0 ? '+' : ''}${format(value)}`
}

export default function PortfolioOverview({ analytics }: { analytics: Analytics }) {
  const total = analytics.value?.total
  const gainLoss = analytics.gain_loss
  const positions = analytics.allocation?.positions ?? []

  return (
    <>
      <Section title="Overview">
        <div className="grid gap-4 sm:grid-cols-2">
          {total != null && <StatTile label="Total value" value={formatCurrency(total)} />}
          {gainLoss && (
            <StatTile
              label="Gain / loss"
              value={signed(gainLoss.gain_loss, formatCurrency)}
              tone={gainLoss.gain_loss >= 0 ? 'positive' : 'negative'}
              sub={signed(gainLoss.gain_loss_pct, (n) => `${n.toFixed(2)}%`)}
            />
          )}
        </div>
      </Section>

      {positions.length > 0 && (
        <Section title="Allocation">
          <AllocationBars positions={positions} />
        </Section>
      )}
    </>
  )
}
