import { formatPercent } from '../../lib/format'
import { metric } from '../../lib/metrics'
import type { Analytics } from '../../lib/types'
import Panel from '../Panel'

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

// what a positive loading means, in plain terms
const MEANING: [string, string][] = [
  ['Market', 'Moves with the stock market as a whole. 1.0 means one for one.'],
  ['Size', 'Positive leans to small companies, negative to large ones.'],
  ['Value', 'Positive leans to cheap stocks, negative to growth stocks.'],
  ['Profitability', 'Positive leans to companies with strong, steady profits.'],
  ['Investment', 'Positive leans to companies that invest conservatively.'],
  ['Momentum', 'Positive leans to stocks that have recently gone up.'],
]

function LoadingRow({ row, scale }: { row: FactorLoading; scale: number }) {
  // bars and whiskers sit on a symmetric axis with zero in the middle
  const pos = (v: number) => 50 + (Math.max(-scale, Math.min(scale, v)) / scale) * 50
  const barLeft = Math.min(50, pos(row.beta))
  const barWidth = Math.abs(pos(row.beta) - 50)
  const significant = Math.abs(row.t_stat) >= 2
  return (
    <li className="grid grid-cols-[10.5rem_1fr_3.5rem] items-center gap-4 py-2.5">
      <span className="text-sm text-ink">{LABELS[row.factor] ?? row.factor}</span>
      <div
        className="relative h-5"
        role="img"
        aria-label={`${LABELS[row.factor] ?? row.factor} beta ${row.beta.toFixed(2)}, 95% interval ${row.ci_low.toFixed(2)} to ${row.ci_high.toFixed(2)}`}
      >
        <div className="absolute inset-y-0 left-1/2 w-px bg-hairline-strong" />
        <div
          className={`absolute top-1 h-3 rounded-sm ${significant ? 'bg-ink' : 'bg-hairline-strong'}`}
          style={{ left: `${barLeft}%`, width: `${barWidth}%` }}
        />
        <div
          className="absolute top-1/2 h-px bg-muted"
          style={{ left: `${pos(row.ci_low)}%`, width: `${pos(row.ci_high) - pos(row.ci_low)}%` }}
        />
        <div className="absolute top-1.5 h-2 w-px bg-muted" style={{ left: `${pos(row.ci_low)}%` }} />
        <div className="absolute top-1.5 h-2 w-px bg-muted" style={{ left: `${pos(row.ci_high)}%` }} />
      </div>
      <span className={`num text-right text-sm ${significant ? 'text-ink' : 'text-muted'}`}>
        {row.beta.toFixed(2)}
      </span>
    </li>
  )
}

export default function FactorSection({ analytics }: { analytics: Analytics }) {
  const result = metric<FactorResult>(analytics, 'factors')
  if (!result || !result.available || result.loadings.length === 0) return null

  const reach = Math.max(...result.loadings.map((l) => Math.max(Math.abs(l.ci_low), Math.abs(l.ci_high))))
  const scale = Math.max(0.5, Math.ceil(reach * 4) / 4)

  return (
    <Panel title="What drives your returns" lede={result.insight} surface={false}>
      <div className="grid gap-6 lg:grid-cols-12">
        <div className="rounded-[var(--radius-panel)] border border-hairline bg-surface lg:col-span-7">
          <ul className="px-5 py-3">
            {result.loadings.map((row) => (
              <LoadingRow key={row.factor} row={row} scale={scale} />
            ))}
          </ul>
          <p className="border-t border-hairline px-5 py-3 text-[13px] text-muted">
            Bars are loadings, whiskers the 95% interval. Dark bars are significant (|t| of 2 or more).
          </p>
          <dl className="grid grid-cols-3 border-t border-hairline">
            <div className="px-5 py-4">
              <dt className="text-[13px] text-muted">Alpha a year</dt>
              <dd className="num mt-1 text-xl leading-none text-ink">
                {formatPercent(result.alpha_annual)}
                <span className="ml-2 text-[12px] text-muted">t {result.alpha_t.toFixed(1)}</span>
              </dd>
            </div>
            <div className="border-l border-hairline px-5 py-4">
              <dt className="text-[13px] text-muted">R squared</dt>
              <dd className="num mt-1 text-xl leading-none text-ink">{result.r_squared.toFixed(2)}</dd>
            </div>
            <div className="border-l border-hairline px-5 py-4">
              <dt className="text-[13px] text-muted">Days used</dt>
              <dd className="num mt-1 text-xl leading-none text-ink">{result.n_obs}</dd>
            </div>
          </dl>
        </div>
        <aside className="lg:col-span-5">
          <h3 className="text-[15px] font-medium text-ink">Reading the loadings</h3>
          <p className="mt-1 text-sm text-body">
            A regression of your daily returns on the Fama-French five factors plus momentum, from
            Ken French&apos;s data library.
          </p>
          <dl className="mt-4 divide-y divide-hairline border-y border-hairline">
            {MEANING.map(([name, text]) => (
              <div key={name} className="grid grid-cols-[7.5rem_1fr] gap-3 py-2.5 text-sm">
                <dt className="text-ink">{name}</dt>
                <dd className="text-body">{text}</dd>
              </div>
            ))}
          </dl>
        </aside>
      </div>
    </Panel>
  )
}
