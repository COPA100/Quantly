import { useState } from 'react'
import { formatPercent } from '../../lib/format'
import { metric } from '../../lib/metrics'
import type { Analytics } from '../../lib/types'
import Panel from '../Panel'

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
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-[13px] text-muted">
          <th scope="col" className="px-5 py-3 font-normal">Method</th>
          {CONFIDENCES.map((c) => (
            <th key={c} scope="col" className="px-5 py-3 text-right font-normal">
              {Math.round(Number(c) * 100)}% VaR / ES
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {METHOD_LABELS.map(([key, label]) => (
          <tr key={key} className="border-t border-hairline-soft">
            <td className="px-5 py-3 text-ink">{label}</td>
            {CONFIDENCES.map((c) => {
              const e = cells[c]?.[key]
              return (
                <td key={c} className="num px-5 py-3 text-right text-ink">
                  {e ? `${formatPercent(e.var, 2)} / ${formatPercent(e.es, 2)}` : '-'}
                </td>
              )
            })}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

const W = 760
const H = 240
const PAD = { left: 48, right: 8, top: 10, bottom: 22 }

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
      aria-label="Daily returns against the one-day 95% VaR forecast, breaches marked"
      className="w-full"
    >
      {[hi, 0, lo].map((tick) => (
        <g key={tick}>
          <line x1={PAD.left} x2={W - PAD.right} y1={y(tick)} y2={y(tick)} stroke="#efeee8" />
          <text x={PAD.left - 8} y={y(tick) + 3} textAnchor="end" className="fill-muted font-mono text-[12px]">
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
          fill={breaches.has(i) ? '#cf2d56' : '#cfcdc4'}
        />
      ))}
      <polyline points={line} fill="none" stroke="#26251e" strokeWidth="1.5" />
      <text x={PAD.left} y={H - 5} className="fill-muted font-mono text-[12px]">
        {bt.dates[0]}
      </text>
      <text x={W - PAD.right} y={H - 5} textAnchor="end" className="fill-muted font-mono text-[12px]">
        {bt.dates[n - 1]}
      </text>
    </svg>
  )
}

function BacktestPanel({ suite }: { suite: VarSuite }) {
  const bt = suite.backtest
  if (!bt) {
    return <p className="text-sm text-body">{suite.backtest_reason ?? 'Backtest unavailable.'}</p>
  }
  return (
    <div>
      <p className="max-w-[68ch] text-[15px] text-body">{bt.verdict}</p>
      <div className="mt-4">
        <BacktestChart bt={bt} />
      </div>
      <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-[13px] text-muted">
        <span className="flex items-center gap-2">
          <span className="inline-block h-0.5 w-4 bg-ink" /> 1-day 95% VaR
        </span>
        <span className="flex items-center gap-2">
          <span className="inline-block h-2 w-2 bg-loss" />
          {`breach (${bt.exceptions} of ${bt.n}, ${bt.expected.toFixed(0)} expected)`}
        </span>
        <span className="num">Kupiec p = {bt.kupiec.p.toFixed(2)}</span>
        <span className="num">Christoffersen p = {bt.christoffersen.p.toFixed(2)}</span>
      </div>
    </div>
  )
}

export default function VarSection({ analytics }: { analytics: Analytics }) {
  const suite = metric<VarSuite>(analytics, 'var_suite')
  const [horizon, setHorizon] = useState('1d')
  if (!suite?.methods) return null
  const cells = suite.methods[horizon] ?? suite.methods[HORIZONS[0]]

  const toggle = (
    <div className="inline-flex rounded-[var(--radius-control)] border border-hairline bg-surface p-0.5 text-[13px]">
      {HORIZONS.map((h) => (
        <button
          key={h}
          type="button"
          aria-pressed={h === horizon}
          onClick={() => setHorizon(h)}
          className={`rounded-md px-3 py-1.5 font-medium transition-colors ${
            h === horizon ? 'bg-ink text-canvas' : 'text-muted hover:text-ink'
          }`}
        >
          {h === '1d' ? '1 day' : '21 days'}
        </button>
      ))}
    </div>
  )

  return (
    <Panel title="Value at risk" lede={suite.insight} actions={toggle}>
      {cells && <MethodTable cells={cells} />}
      <div className="border-t border-hairline p-5">
        <h3 className="text-[15px] font-medium text-ink">Did the forecast hold up?</h3>
        <p className="mb-3 text-[13px] text-muted">Backtest over the last two years</p>
        <BacktestPanel suite={suite} />
      </div>
    </Panel>
  )
}
