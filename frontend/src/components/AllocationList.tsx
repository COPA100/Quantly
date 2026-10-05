import { formatPercent } from '../lib/format'
import type { Allocation } from '../lib/types'

// ranked bars: the ticker labels each row directly, length encodes share of the book
export default function AllocationList({ positions }: { positions: Allocation[] }) {
  const sorted = [...positions].sort((a, b) => b.pct_allocation - a.pct_allocation)
  const max = sorted[0]?.pct_allocation || 1

  return (
    <ul className="px-5 py-3">
      {sorted.map((position) => (
        <li key={position.ticker} className="grid grid-cols-[3.5rem_1fr_3.5rem] items-center gap-3 py-1.5">
          <span className="num text-[13px] text-ink">{position.ticker}</span>
          <div className="h-2 rounded-full bg-hairline-soft">
            <div
              className="h-2 rounded-full bg-ink"
              style={{ width: `${Math.max((position.pct_allocation / max) * 100, 1)}%` }}
            />
          </div>
          <span className="num text-right text-[13px] text-body">{formatPercent(position.pct_allocation)}</span>
        </li>
      ))}
    </ul>
  )
}
