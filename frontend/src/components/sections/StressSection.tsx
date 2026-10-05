import { useState } from 'react'
import { formatPercent } from '../../lib/format'
import { metric } from '../../lib/metrics'
import { toneOf, toneTextColor } from '../../lib/tone'
import type { Analytics } from '../../lib/types'
import Panel from '../Panel'

export interface StressScenario {
  name: string
  start: string
  end: string
  portfolio_return: number
  benchmark_return: number
  worst: { ticker: string; return: number } | null
  proxied_weight: number
  holdings: { ticker: string; weight: number; return: number; method: 'replayed' | 'proxied' }[]
}

export interface StressResult {
  scenarios: StressScenario[]
  insight: string
}

function sentence(name: string): string {
  return name.charAt(0).toUpperCase() + name.slice(1)
}

function Bar({ value, scale, className }: { value: number; scale: number; className: string }) {
  const width = scale > 0 ? (Math.abs(value) / scale) * 100 : 0
  return (
    <div className="h-2 flex-1 rounded-full bg-hairline-soft">
      <div className={`h-2 rounded-full ${className}`} style={{ width: `${width}%` }} />
    </div>
  )
}

function Detail({ s }: { s: StressScenario }) {
  const holdings = [...s.holdings].sort((a, b) => a.return - b.return)
  return (
    <div className="p-6">
      <h3 className="display-md text-ink">{sentence(s.name)}</h3>
      <p className="num mt-1 text-[13px] text-muted">
        {s.start} to {s.end}
      </p>
      <dl className="mt-5 grid grid-cols-2 gap-4 border-y border-hairline py-4">
        <div>
          <dt className="text-[13px] text-muted">Your portfolio</dt>
          <dd className={`num mt-1 text-[26px] leading-none ${toneTextColor[toneOf(s.portfolio_return)]}`}>
            {formatPercent(s.portfolio_return)}
          </dd>
        </div>
        <div>
          <dt className="text-[13px] text-muted">S&amp;P 500</dt>
          <dd className="num mt-1 text-[26px] leading-none text-body">
            {formatPercent(s.benchmark_return)}
          </dd>
        </div>
      </dl>
      {s.proxied_weight > 0 && (
        <p className="mt-3 text-[13px] text-muted">
          {formatPercent(s.proxied_weight, 0)} of the book estimated from beta
        </p>
      )}
      <table className="mt-4 w-full text-sm">
        <thead>
          <tr className="text-left text-[13px] text-muted">
            <th scope="col" className="pb-2 font-normal">Holding</th>
            <th scope="col" className="pb-2 text-right font-normal">Weight</th>
            <th scope="col" className="pb-2 text-right font-normal">Return</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h) => (
            <tr key={h.ticker} className="border-t border-hairline-soft">
              <td className="py-2">
                <span className="num text-ink">{h.ticker}</span>
                {h.method === 'proxied' && <span className="ml-2 text-[12px] text-muted">estimated</span>}
              </td>
              <td className="num py-2 text-right text-body">{formatPercent(h.weight)}</td>
              <td className={`num py-2 text-right ${toneTextColor[toneOf(h.return)]}`}>
                {formatPercent(h.return)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function StressSection({ analytics }: { analytics: Analytics }) {
  const stress = metric<StressResult>(analytics, 'stress')
  const scenarios = stress?.scenarios ?? []
  const worst = scenarios.reduce(
    (w, s, i) => (s.portfolio_return < scenarios[w].portfolio_return ? i : w),
    0,
  )
  const [selected, setSelected] = useState<number | null>(null)
  if (!stress || scenarios.length === 0) return null
  const active = selected ?? worst
  // one scale for every bar so scenarios compare by eye
  const scale = Math.max(
    ...scenarios.flatMap((s) => [Math.abs(s.portfolio_return), Math.abs(s.benchmark_return)]),
  )

  return (
    <Panel title="Stress tests" lede={stress.insight} surface={false}>
      <div className="grid gap-6 lg:grid-cols-12">
        <div className="rounded-[var(--radius-panel)] border border-hairline bg-surface lg:col-span-7">
          <div className="flex gap-5 border-b border-hairline px-5 py-3 text-[13px] text-muted">
            <span className="flex items-center gap-2">
              <span className="h-2 w-4 rounded-full bg-ink" /> Your portfolio
            </span>
            <span className="flex items-center gap-2">
              <span className="h-2 w-4 rounded-full bg-hairline-strong" /> S&amp;P 500
            </span>
          </div>
          <ul>
            {scenarios.map((s, i) => (
              <li key={s.name} className="border-b border-hairline-soft last:border-0">
                <button
                  type="button"
                  aria-pressed={i === active}
                  onClick={() => setSelected(i)}
                  className={`block w-full px-5 py-4 text-left transition-colors ${
                    i === active ? 'bg-canvas-soft' : 'hover:bg-canvas-soft'
                  }`}
                >
                  <span className="flex items-baseline justify-between gap-3">
                    <span className={`text-[15px] ${i === active ? 'font-medium text-ink' : 'text-ink'}`}>
                      {sentence(s.name)}
                    </span>
                    <span className="num text-[12px] text-muted">{s.start.slice(0, 4)}</span>
                  </span>
                  <span className="mt-2.5 flex items-center gap-3">
                    <Bar value={s.portfolio_return} scale={scale} className="bg-ink" />
                    <span className={`num w-16 text-right text-[13px] ${toneTextColor[toneOf(s.portfolio_return)]}`}>
                      {formatPercent(s.portfolio_return)}
                    </span>
                  </span>
                  <span className="mt-1.5 flex items-center gap-3">
                    <Bar value={s.benchmark_return} scale={scale} className="bg-hairline-strong" />
                    <span className="num w-16 text-right text-[13px] text-muted">
                      {formatPercent(s.benchmark_return)}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
        <div className="self-start rounded-[var(--radius-panel)] border border-hairline bg-surface lg:sticky lg:top-24 lg:col-span-5">
          <Detail s={scenarios[active]} />
        </div>
      </div>
    </Panel>
  )
}
