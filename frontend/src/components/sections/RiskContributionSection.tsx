import { formatPercent } from '../../lib/format'
import { metric } from '../../lib/metrics'
import type { Analytics } from '../../lib/types'
import Section from '../Section'

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
    <div className="flex items-center gap-2">
      <div className="h-2.5 flex-1 rounded-sm bg-slate-100">
        <div
          role="img"
          aria-label={`${label} ${formatPercent(fraction, 0)}`}
          className={`h-2.5 rounded-sm ${className}`}
          style={{ width: `${Math.min(100, (Math.max(fraction, 0) / max) * 100)}%` }}
        />
      </div>
      <span className="w-10 text-right text-xs tabular-nums text-slate-600">{formatPercent(fraction, 0)}</span>
    </div>
  )
}

export default function RiskContributionSection({ analytics }: { analytics: Analytics }) {
  const result = metric<RiskContributionResult>(analytics, 'risk_contribution')
  if (!result || result.holdings.length === 0) return null

  const max = Math.max(...result.holdings.flatMap((h) => [h.weight, h.pct_risk]))
  return (
    <Section title="Risk contribution">
      {result.insight && <p className="mb-3 text-sm text-slate-600">{result.insight}</p>}
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="mb-3 flex gap-4 text-xs text-slate-500">
          <span className="flex items-center gap-1">
            <span className="inline-block h-2.5 w-2.5 rounded-sm bg-slate-400" /> % of capital
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-2.5 w-2.5 rounded-sm bg-blue-600" /> % of risk
          </span>
        </div>
        <ul className="space-y-3">
          {result.holdings.map((h) => (
            <li key={h.ticker} className="grid grid-cols-[4rem_1fr] items-center gap-3 text-sm">
              <span className="font-medium text-slate-900">{h.ticker}</span>
              <div className="space-y-1">
                <Bar label={`${h.ticker} capital`} fraction={h.weight} max={max} className="bg-slate-400" />
                <Bar label={`${h.ticker} risk`} fraction={h.pct_risk} max={max} className="bg-blue-600" />
              </div>
            </li>
          ))}
        </ul>
      </div>
    </Section>
  )
}
