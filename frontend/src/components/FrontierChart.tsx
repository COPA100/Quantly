import { formatPercent } from '../lib/format'
import { MARKERS, type FrontierMarker, type FrontierResult } from '../lib/frontier'

const W = 640
const H = 360
const M = { top: 16, right: 20, bottom: 48, left: 60 }
const TICKS = 5

function Shape({ shape, x, y, color }: { shape: FrontierMarker['shape']; x: number; y: number; color: string }) {
  const common = { fill: color, stroke: '#ffffff', strokeWidth: 1.5 }
  switch (shape) {
    case 'square':
      return <rect x={x - 5} y={y - 5} width={10} height={10} {...common} />
    case 'diamond':
      return <polygon points={`${x},${y - 7} ${x + 7},${y} ${x},${y + 7} ${x - 7},${y}`} {...common} />
    case 'triangle':
      return <polygon points={`${x},${y - 7} ${x + 7},${y + 5} ${x - 7},${y + 5}`} {...common} />
    default:
      return <circle cx={x} cy={y} r={6} {...common} />
  }
}

function ticks(lo: number, hi: number): number[] {
  return Array.from({ length: TICKS }, (_, i) => lo + ((hi - lo) * i) / (TICKS - 1))
}

export default function FrontierChart({ frontier }: { frontier: FrontierResult }) {
  const marked = MARKERS.flatMap((m) => {
    const p = frontier[m.key]
    return p ? [{ ...m, vol: p.vol, ret: p.ret }] : []
  })
  const all = [...frontier.points, ...marked]
  const pad = (lo: number, hi: number) => {
    const span = hi - lo || Math.abs(hi) || 0.01
    return [lo - span * 0.08, hi + span * 0.08] as const
  }
  const [x0, x1] = pad(Math.min(...all.map((p) => p.vol)), Math.max(...all.map((p) => p.vol)))
  const [y0, y1] = pad(Math.min(...all.map((p) => p.ret)), Math.max(...all.map((p) => p.ret)))
  const sx = (v: number) => M.left + ((v - x0) / (x1 - x0)) * (W - M.left - M.right)
  const sy = (r: number) => H - M.bottom - ((r - y0) / (y1 - y0)) * (H - M.top - M.bottom)
  const line = frontier.points.map((p) => `${sx(p.vol).toFixed(1)},${sy(p.ret).toFixed(1)}`).join(' ')

  return (
    <figure>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label="Efficient frontier of volatility against expected return"
      >
        {ticks(y0, y1).map((t) => (
          <g key={`y${t}`}>
            <line x1={M.left} x2={W - M.right} y1={sy(t)} y2={sy(t)} stroke="#e2e8f0" />
            <text x={M.left - 8} y={sy(t)} textAnchor="end" dominantBaseline="middle" className="fill-slate-500 text-[11px]">
              {formatPercent(t, 0)}
            </text>
          </g>
        ))}
        {ticks(x0, x1).map((t) => (
          <text key={`x${t}`} x={sx(t)} y={H - M.bottom + 18} textAnchor="middle" className="fill-slate-500 text-[11px]">
            {formatPercent(t, 0)}
          </text>
        ))}
        <text x={(M.left + W - M.right) / 2} y={H - 8} textAnchor="middle" className="fill-slate-600 text-xs">
          Volatility (annualized)
        </text>
        <text
          transform={`translate(14 ${(M.top + H - M.bottom) / 2}) rotate(-90)`}
          textAnchor="middle"
          className="fill-slate-600 text-xs"
        >
          Expected return (annualized)
        </text>
        <polyline points={line} fill="none" stroke="#94a3b8" strokeWidth={2} />
        {marked.map((m) => (
          <Shape key={m.key} shape={m.shape} x={sx(m.vol)} y={sy(m.ret)} color={m.color} />
        ))}
      </svg>
      <figcaption className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-600">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-4 bg-slate-400" />
          Efficient frontier
        </span>
        {marked.map((m) => (
          <span key={m.key} className="inline-flex items-center gap-1.5">
            <svg width="14" height="14" viewBox="-8 -8 16 16" aria-hidden="true">
              <Shape shape={m.shape} x={0} y={0} color={m.color} />
            </svg>
            {m.label}
          </span>
        ))}
      </figcaption>
    </figure>
  )
}
