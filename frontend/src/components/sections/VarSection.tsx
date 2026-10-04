import { useState } from 'react'
import { formatPercent } from '../../lib/format'
import { metric } from '../../lib/metrics'
import type { Analytics } from '../../lib/types'
import Section from '../Section'

interface Estimate {
  var: number
  es: number
}

type MethodKey = 'historical' | 'parametric' | 'cornish_fisher' | 'monte_carlo'
type Cell = Record<MethodKey, Estimate>

interface Backtest {
  dates: string[]
  returns: number[]
  var: number[]
  exception_indices: number[]
  n: number
  exceptions: number
  expected: number
  kupiec: { lr: number; p: number }
  christoffersen: { lr: number; p: number }
  verdict: string
}

export interface VarSuite {
  methods: Record<string, Record<string, Cell>>
  backtest: Backtest | null
  backtest_reason?: string
  insight: string
}

const METHOD_LABELS: [MethodKey, string][] = [
  ['historical', 'Historical'],
  ['parametric', 'Normal'],
  ['cornish_fisher', 'Cornish-Fisher'],
  ['monte_carlo', 'Monte Carlo'],
]

const HORIZONS = ['1d', '21d']
const CONFIDENCES = ['0.95', '0.99']

function MethodTable({ cells }: { cells: Record<string, Cell> }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <table className="w-full text-sm">
        <thead className="text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-2 font-medium">Method</th>
            {CONFIDENCES.map((c) => (
              <th key={c} className="px-4 py-2 text-right font-medium">
                {Math.round(Number(c) * 100)}% VaR / ES
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {METHOD_LABELS.map(([key, label]) => (
            <tr key={key} className="border-t border-slate-100">
              <td className="px-4 py-2 text-slate-700">{label}</td>
              {CONFIDENCES.map((c) => {
                const e = cells[c]?.[key]
                return (
                  <td key={c} className="px-4 py-2 text-right tabular-nums text-slate-900">
                    {e ? `${formatPercent(e.var, 2)} / ${formatPercent(e.es, 2)}` : '-'}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const W = 640
const H = 220
const PAD = { left: 44, right: 8, top: 8, bottom: 20 }

function BacktestChart({ bt }: { bt: Backtest }) {
  const n = bt.returns.length
  if (n === 0) return null
  const breaches = new Set(bt.exception_indices)
  const lo = Math.min(...bt.returns, ...bt.var.map((v) => -v))
  const hi = Math.max(...bt.returns, 0)
  const span = hi - lo || 1
  const x = (i: number) => PAD.left + ((i + 0.5) / n) * (W - PAD.left - PAD.right)
  const y = (v: number) => PAD.top + ((hi - v) / span) * (H - PAD.top - PAD.bottom)
  const barW = Math.max(((W - PAD.left - PAD.right) / n) * 0.7, 0.8)
  const line = bt.var.map((v, i) => `${x(i).toFixed(1)},${y(-v).toFixed(1)}`).join(' ')

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="Daily returns against the one-day 95% VaR forecast, breaches in red"
      className="w-full rounded-xl border border-slate-200 bg-white"
    >
      {[hi, 0, lo].map((tick) => (
        <g key={tick}>
          <line x1={PAD.left} x2={W - PAD.right} y1={y(tick)} y2={y(tick)} stroke="#e2e8f0" />
          <text x={PAD.left - 6} y={y(tick) + 3} textAnchor="end" fontSize="10" fill="#64748b">
            {formatPercent(tick, 1)}
          </text>
        </g>
      ))}
      {bt.returns.map((r, i) => (
        <rect
          key={i}
          data-breach={breaches.has(i) ? 'true' : undefined}
          x={x(i) - barW / 2}
          y={Math.min(y(r), y(0))}
          width={barW}
          height={Math.max(Math.abs(y(r) - y(0)), 0.5)}
          fill={breaches.has(i) ? '#dc2626' : '#94a3b8'}
        />
      ))}
      <polyline points={line} fill="none" stroke="#2563eb" strokeWidth="1.5" />
      <text x={PAD.left} y={H - 6} fontSize="10" fill="#64748b">
        {bt.dates[0]}
      </text>
      <text x={W - PAD.right} y={H - 6} textAnchor="end" fontSize="10" fill="#64748b">
        {bt.dates[n - 1]}
      </text>
    </svg>
  )
}

function BacktestPanel({ suite }: { suite: VarSuite }) {
  const bt = suite.backtest
  if (!bt) {
    return (
      <p className="text-sm text-slate-500">{suite.backtest_reason ?? 'Backtest unavailable.'}</p>
    )
  }
  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-600">{bt.verdict}</p>
      <BacktestChart bt={bt} />
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-slate-500">
        <span className="flex items-center gap-1">
          <span className="inline-block h-0.5 w-4 bg-blue-600" /> 1-day 95% VaR
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2 w-2 bg-red-600" />
          {`breach (${bt.exceptions} of ${bt.n}, ${bt.expected.toFixed(0)} expected)`}
        </span>
        <span>Kupiec p = {bt.kupiec.p.toFixed(2)}</span>
        <span>Christoffersen p = {bt.christoffersen.p.toFixed(2)}</span>
      </div>
    </div>
  )
}

export default function VarSection({ analytics }: { analytics: Analytics }) {
  const suite = metric<VarSuite>(analytics, 'var_suite')
  const [horizon, setHorizon] = useState('1d')
  if (!suite?.methods) return null
  const cells = suite.methods[horizon] ?? suite.methods[HORIZONS[0]]

  return (
    <Section title="Value at risk methods">
      <p className="mb-3 text-sm text-slate-600">{suite.insight}</p>
      <div className="mb-2 inline-flex rounded-lg border border-slate-200 bg-white p-0.5 text-xs">
        {HORIZONS.map((h) => (
          <button
            key={h}
            type="button"
            aria-pressed={h === horizon}
            onClick={() => setHorizon(h)}
            className={`rounded-md px-3 py-1 font-medium ${
              h === horizon ? 'bg-slate-900 text-white' : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            {h === '1d' ? '1 day' : '21 days'}
          </button>
        ))}
      </div>
      {cells && <MethodTable cells={cells} />}
      <h3 className="mb-2 mt-6 text-xs font-semibold uppercase tracking-wide text-slate-500">
        Backtest, last two years
      </h3>
      <BacktestPanel suite={suite} />
    </Section>
  )
}
