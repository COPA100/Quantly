import { Fragment } from 'react'
import type { Correlation } from '../lib/types'

// positive correlation darkens toward ink (holdings that move together are
// concentrated risk); negative tints toward green (they offset each other)
const INK = [38, 37, 30]
const GAIN = [31, 138, 101]
const BASE = [250, 250, 247]

function lerp(from: number[], to: number[], t: number): string {
  const channel = (i: number) => Math.round(from[i] + (to[i] - from[i]) * t)
  return `rgb(${channel(0)}, ${channel(1)}, ${channel(2)})`
}

function cellColor(value: number): string {
  const t = Math.min(Math.abs(value), 1)
  return value >= 0 ? lerp(BASE, INK, t * 0.92) : lerp(BASE, GAIN, t)
}

function textColor(value: number): string {
  // flip to light ink once the fill gets dark enough to need it
  return Math.abs(value) > 0.42 ? '#fafaf7' : '#26251e'
}

export default function CorrelationHeatmap({ correlation }: { correlation: Correlation }) {
  const { tickers, matrix } = correlation
  const n = tickers.length
  if (n < 2) return null

  return (
    <div className="p-5">
      <div className="overflow-x-auto">
        <div
          className="grid min-w-max gap-[3px]"
          style={{ gridTemplateColumns: `3.5rem repeat(${n}, minmax(2.6rem, 1fr))` }}
        >
          <div />
          {tickers.map((ticker) => (
            <div key={`head-${ticker}`} className="num pb-1 text-center text-[11px] text-muted">
              {ticker}
            </div>
          ))}

          {matrix.map((row, i) => (
            <Fragment key={`row-${tickers[i]}`}>
              <div className="num self-center pr-2 text-right text-[11px] text-muted">{tickers[i]}</div>
              {row.map((value, j) => (
                <div
                  key={`cell-${tickers[i]}-${tickers[j]}`}
                  title={`${tickers[i]} and ${tickers[j]}: ${value.toFixed(2)}`}
                  className="num flex aspect-square items-center justify-center rounded-[4px] text-[11px]"
                  style={
                    i === j
                      ? { backgroundColor: 'transparent', boxShadow: 'inset 0 0 0 1px #e6e5e0' }
                      : { backgroundColor: cellColor(value), color: textColor(value) }
                  }
                >
                  {i === j ? '' : value.toFixed(2)}
                </div>
              ))}
            </Fragment>
          ))}
        </div>
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-3 text-[13px] text-muted">
        <span className="num">-1</span>
        <div
          className="h-2 w-40 rounded-full"
          style={{
            background: `linear-gradient(to right, ${lerp(BASE, GAIN, 1)}, rgb(${BASE.join(',')}), ${lerp(BASE, INK, 0.92)})`,
          }}
        />
        <span className="num">+1</span>
        <span>offset each other, to move together</span>
      </div>
    </div>
  )
}
