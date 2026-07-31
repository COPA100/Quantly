import { Fragment } from 'react'
import type { Correlation } from '../lib/types'

// diverging RdBu scale: blue pole (negative), neutral slate midpoint, red pole
// (positive). two hues + a gray midpoint, no rainbow — and red/blue stays
// distinguishable under the common colour-vision deficiencies.
const RED = [220, 38, 38]
const BLUE = [37, 99, 235]
const NEUTRAL = [241, 245, 249]

function lerp(from: number[], to: number[], t: number): string {
  const channel = (i: number) => Math.round(from[i] + (to[i] - from[i]) * t)
  return `rgb(${channel(0)}, ${channel(1)}, ${channel(2)})`
}

function cellColor(value: number): string {
  return value >= 0 ? lerp(NEUTRAL, RED, Math.min(value, 1)) : lerp(NEUTRAL, BLUE, Math.min(-value, 1))
}

function textColor(value: number): string {
  // flip to white ink once the fill gets dark enough to need it
  return Math.abs(value) > 0.6 ? '#ffffff' : '#0f172a'
}

export default function CorrelationHeatmap({ correlation }: { correlation: Correlation }) {
  const { tickers, matrix } = correlation
  const n = tickers.length
  if (n < 2) return null

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white p-4">
      <div
        className="inline-grid gap-1"
        style={{ gridTemplateColumns: `auto repeat(${n}, minmax(2.5rem, 1fr))` }}
      >
        <div />
        {tickers.map((ticker) => (
          <div key={`head-${ticker}`} className="px-1 text-center text-xs font-medium text-slate-500">
            {ticker}
          </div>
        ))}

        {matrix.map((row, i) => (
          <Fragment key={`row-${tickers[i]}`}>
            <div className="self-center pr-2 text-right text-xs font-medium text-slate-500">
              {tickers[i]}
            </div>
            {row.map((value, j) => (
              <div
                key={`cell-${tickers[i]}-${tickers[j]}`}
                title={`${tickers[i]} vs ${tickers[j]}: ${value.toFixed(2)}`}
                className="flex aspect-square items-center justify-center rounded text-[11px] tabular-nums"
                style={{ backgroundColor: cellColor(value), color: textColor(value) }}
              >
                {value.toFixed(2)}
              </div>
            ))}
          </Fragment>
        ))}
      </div>

      <div className="mt-4 flex items-center gap-2 text-xs text-slate-500">
        <span className="tabular-nums">−1</span>
        <div
          className="h-2 w-40 rounded"
          style={{
            background: 'linear-gradient(to right, rgb(37,99,235), rgb(241,245,249), rgb(220,38,38))',
          }}
        />
        <span className="tabular-nums">+1</span>
        <span className="ml-2">moves opposite → moves together</span>
      </div>
    </div>
  )
}
