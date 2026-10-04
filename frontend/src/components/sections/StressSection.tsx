import { formatPercent } from '../../lib/format'
import { metric } from '../../lib/metrics'
import type { Analytics } from '../../lib/types'
import Section from '../Section'

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

function Bar({ label, value, scale, tone }: { label: string; value: number; scale: number; tone: string }) {
  const width = scale > 0 ? (Math.abs(value) / scale) * 100 : 0
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-16 shrink-0 text-slate-500">{label}</span>
      <div className="h-3 flex-1 rounded bg-slate-100">
        <div className={`h-3 rounded ${tone}`} style={{ width: `${width}%` }} />
      </div>
      <span className="w-14 shrink-0 text-right tabular-nums text-slate-700">
        {formatPercent(value, 1)}
      </span>
    </div>
  )
}

export default function StressSection({ analytics }: { analytics: Analytics }) {
  const stress = metric<StressResult>(analytics, 'stress')
  if (!stress || !stress.scenarios || stress.scenarios.length === 0) return null
  // one scale for every bar so scenarios compare by eye
  const scale = Math.max(
    ...stress.scenarios.flatMap((s) => [Math.abs(s.portfolio_return), Math.abs(s.benchmark_return)]),
  )
  return (
    <Section title="Stress tests">
      {stress.insight && <p className="mb-3 text-sm text-slate-600">{stress.insight}</p>}
      <div className="space-y-4 rounded-xl border border-slate-200 bg-white p-4">
        {stress.scenarios.map((s) => (
          <div key={s.name} className="space-y-1">
            <p className="text-sm font-medium text-slate-900">
              {s.name} <span className="font-normal text-slate-400">{s.start} to {s.end}</span>
            </p>
            <Bar
              label="Portfolio"
              value={s.portfolio_return}
              scale={scale}
              tone={s.portfolio_return < 0 ? 'bg-red-500' : 'bg-emerald-500'}
            />
            <Bar label="S&P 500" value={s.benchmark_return} scale={scale} tone="bg-slate-400" />
            {s.proxied_weight > 0 && (
              <p className="text-xs text-slate-400">
                {formatPercent(s.proxied_weight, 0)} of the book estimated from beta
              </p>
            )}
          </div>
        ))}
      </div>
    </Section>
  )
}
