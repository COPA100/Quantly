import { formatPercent } from '../../lib/format'
import { metric } from '../../lib/metrics'
import type { Analytics } from '../../lib/types'
import Panel from '../Panel'

export interface RiskHolding {
  ticker: string
  weight: number
  pct_risk: number
  rc: number
  marginal_var: number
}

export interface RiskContributionResult {
  holdings: RiskHolding[]
  insight: string
}

function Bar({ label, fraction, max, className }: { label: string; fraction: number; max: number; className: string }) {
  return (
    <div className="h-2 rounded-full bg-hairline-soft">
      <div
        role="img"
        aria-label={`${label} ${formatPercent(fraction, 0)}`}
        className={`h-2 rounded-full ${className}`}
        style={{ width: `${Math.min(100, (Math.max(fraction, 0) / max) * 100)}%` }}
      />
    </div>
  )
}

export default function RiskContributionSection({ analytics }: { analytics: Analytics }) {
  const result = metric<RiskContributionResult>(analytics, 'risk_contribution')
  if (!result || result.holdings.length === 0) return null

  const max = Math.max(...result.holdings.flatMap((h) => [h.weight, h.pct_risk]))
  return (
    <Panel title="Where the risk comes from" lede={result.insight}>
      <div className="flex gap-5 border-b border-hairline px-5 py-3 text-[13px] text-muted">
        <span className="flex items-center gap-2">
          <span className="h-2 w-4 rounded-full bg-hairline-strong" /> Share of money
        </span>
        <span className="flex items-center gap-2">
          <span className="h-2 w-4 rounded-full bg-ink" /> Share of risk
        </span>
      </div>
      <ul className="px-5 py-3">
        {result.holdings.map((h) => (
          <li key={h.ticker} className="grid grid-cols-[3.5rem_1fr_5.5rem] items-center gap-3 py-1.5">
            <span className="num text-[13px] text-ink">{h.ticker}</span>
            <div className="space-y-1">
              <Bar label={`${h.ticker} capital`} fraction={h.weight} max={max} className="bg-hairline-strong" />
              <Bar label={`${h.ticker} risk`} fraction={h.pct_risk} max={max} className="bg-ink" />
            </div>
            <span className="num text-right text-[12px] text-muted">
              {formatPercent(h.weight, 0)} / <span className="text-ink">{formatPercent(h.pct_risk, 0)}</span>
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  )
}
