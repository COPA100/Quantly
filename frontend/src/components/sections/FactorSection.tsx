import { formatPercent } from '../../lib/format'
import { metric } from '../../lib/metrics'
import type { Analytics } from '../../lib/types'
import Section from '../Section'

export interface FactorLoading {
  factor: string
  beta: number
  t_stat: number
  ci_low: number
  ci_high: number
}

export type FactorResult =
  | { available: false; reason: string }
  | {
      available: true
      loadings: FactorLoading[]
      alpha_annual: number
      alpha_t: number
      r_squared: number
      n_obs: number
      start: string
      end: string
      insight: string
    }

const LABELS: Record<string, string> = {
  mkt_rf: 'Market',
  smb: 'Size (small minus big)',
  hml: 'Value (high minus low)',
  rmw: 'Profitability',
  cma: 'Investment',
  mom: 'Momentum',
}

function LoadingRow({ row, scale }: { row: FactorLoading; scale: number }) {
  // bars and whiskers are placed on a symmetric axis with zero in the middle
  const pos = (v: number) => 50 + (Math.max(-scale, Math.min(scale, v)) / scale) * 50
  const barLeft = Math.min(50, pos(row.beta))
  const barWidth = Math.abs(pos(row.beta) - 50)
  const significant = Math.abs(row.t_stat) >= 2
  return (
    <li className="grid grid-cols-[9rem_1fr_4rem] items-center gap-3 text-sm">
      <span className="text-slate-600">{LABELS[row.factor] ?? row.factor}</span>
      <div
        className="relative h-5"
        role="img"
        aria-label={`${LABELS[row.factor] ?? row.factor} beta ${row.beta.toFixed(2)}, 95% interval ${row.ci_low.toFixed(2)} to ${row.ci_high.toFixed(2)}`}
      >
        <div className="absolute inset-y-0 left-1/2 w-px bg-slate-300" />
        <div
          className={`absolute top-1 h-3 rounded-sm ${significant ? 'bg-blue-600' : 'bg-slate-300'}`}
          style={{ left: `${barLeft}%`, width: `${barWidth}%` }}
        />
        <div
          className="absolute top-1/2 h-px bg-slate-900"
          style={{ left: `${pos(row.ci_low)}%`, width: `${pos(row.ci_high) - pos(row.ci_low)}%` }}
        />
        <div className="absolute top-1 h-3 w-px bg-slate-900" style={{ left: `${pos(row.ci_low)}%` }} />
        <div className="absolute top-1 h-3 w-px bg-slate-900" style={{ left: `${pos(row.ci_high)}%` }} />
      </div>
      <span className="text-right tabular-nums text-slate-900">{row.beta.toFixed(2)}</span>
    </li>
  )
}

export default function FactorSection({ analytics }: { analytics: Analytics }) {
  const result = metric<FactorResult>(analytics, 'factors')
  if (!result || !result.available || result.loadings.length === 0) return null

  const reach = Math.max(...result.loadings.map((l) => Math.max(Math.abs(l.ci_low), Math.abs(l.ci_high))))
  const scale = Math.max(0.5, Math.ceil(reach * 4) / 4)

  return (
    <Section title="Factor exposure">
      <p className="mb-3 text-sm text-slate-600">{result.insight}</p>
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <ul className="space-y-2">
          {result.loadings.map((row) => (
            <LoadingRow key={row.factor} row={row} scale={scale} />
          ))}
        </ul>
        <p className="mt-2 text-xs text-slate-500">
          Bars are betas, whiskers the 95% interval. Dark bars are significant (|t| of 2 or more).
        </p>
        <dl className="mt-4 grid grid-cols-3 gap-3 border-t border-slate-100 pt-3 text-sm">
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">Alpha (annual)</dt>
            <dd className="font-semibold text-slate-900">
              {formatPercent(result.alpha_annual)}
              <span className="ml-1 text-xs font-normal text-slate-500">t {result.alpha_t.toFixed(1)}</span>
            </dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">R squared</dt>
            <dd className="font-semibold text-slate-900">{result.r_squared.toFixed(2)}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-wide text-slate-500">Days used</dt>
            <dd className="font-semibold text-slate-900">{result.n_obs}</dd>
          </div>
        </dl>
      </div>
    </Section>
  )
}
