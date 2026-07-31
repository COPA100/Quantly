import { formatPercent } from '../lib/format'
import type { Allocation } from '../lib/types'

// ranked single-hue bars: identity comes from the direct ticker label, length
// honestly encodes each position's share of the book
export default function AllocationBars({ positions }: { positions: Allocation[] }) {
  const sorted = [...positions].sort((a, b) => b.pct_allocation - a.pct_allocation)

  return (
    <div className="space-y-2 rounded-xl border border-slate-200 bg-white p-4">
      {sorted.map((position) => (
        <div key={position.ticker} className="flex items-center gap-3">
          <span className="w-16 shrink-0 text-sm font-medium text-slate-900">
            {position.ticker}
          </span>
          <div className="h-2.5 flex-1 rounded-full bg-slate-100">
            <div
              className="h-2.5 rounded-full bg-indigo-500"
              style={{ width: `${Math.max(position.pct_allocation * 100, 1)}%` }}
            />
          </div>
          <span className="w-14 shrink-0 text-right text-sm tabular-nums text-slate-500">
            {formatPercent(position.pct_allocation)}
          </span>
        </div>
      ))}
    </div>
  )
}
