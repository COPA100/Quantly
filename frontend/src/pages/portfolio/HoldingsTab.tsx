import type { RiskContributionResult } from '../../components/sections/RiskContributionSection'
import { formatCurrency, formatPercent } from '../../lib/format'
import { metric } from '../../lib/metrics'
import { usePortfolioData } from './context'

export default function HoldingsTab() {
  const { analytics, detail } = usePortfolioData()
  const weights = new Map(
    (analytics.allocation?.positions ?? []).map((p) => [p.ticker.toUpperCase(), p.pct_allocation]),
  )
  const risk = new Map(
    (metric<RiskContributionResult>(analytics, 'risk_contribution')?.holdings ?? []).map((h) => [
      h.ticker,
      h,
    ]),
  )
  const rows = [...detail.holdings].sort(
    (a, b) => (weights.get(b.ticker.toUpperCase()) ?? 0) - (weights.get(a.ticker.toUpperCase()) ?? 0),
  )

  return (
    <div className="overflow-x-auto rounded-[var(--radius-panel)] border border-hairline bg-surface">
      <table className="w-full min-w-[720px] text-sm">
        <thead>
          <tr className="text-left text-[13px] text-muted">
            <th scope="col" className="px-5 py-3 font-normal">Holding</th>
            <th scope="col" className="px-5 py-3 text-right font-normal">Shares</th>
            <th scope="col" className="px-5 py-3 text-right font-normal">Cost basis</th>
            <th scope="col" className="px-5 py-3 text-right font-normal">Share of money</th>
            <th scope="col" className="px-5 py-3 text-right font-normal">Share of risk</th>
            <th scope="col" className="px-5 py-3 text-right font-normal">Marginal 1-day VaR</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((h) => {
            const t = h.ticker.toUpperCase()
            const r = risk.get(t)
            const w = weights.get(t)
            return (
              <tr key={h.id} className="border-t border-hairline-soft">
                <td className="num px-5 py-3 text-ink">{t}</td>
                <td className="num px-5 py-3 text-right text-body">
                  {Number(h.shares).toLocaleString(undefined, { maximumFractionDigits: 4 })}
                </td>
                <td className="num px-5 py-3 text-right text-body">
                  {h.cost_basis == null ? '-' : formatCurrency(Number(h.cost_basis))}
                </td>
                <td className="num px-5 py-3 text-right text-ink">{w == null ? '-' : formatPercent(w)}</td>
                <td className="num px-5 py-3 text-right text-ink">{r ? formatPercent(r.pct_risk) : '-'}</td>
                <td className="num px-5 py-3 text-right text-body">
                  {r ? formatPercent(r.marginal_var, 2) : '-'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
