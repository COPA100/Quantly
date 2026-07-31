import { formatCurrency } from '../lib/format'
import type { Holding } from '../lib/types'

export default function HoldingsTable({ holdings }: { holdings: Holding[] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-2 font-medium">Ticker</th>
            <th className="px-4 py-2 text-right font-medium">Shares</th>
            <th className="px-4 py-2 text-right font-medium">Cost basis</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {holdings.map((holding) => (
            <tr key={holding.id}>
              <td className="px-4 py-2 font-medium text-slate-900">{holding.ticker}</td>
              <td className="px-4 py-2 text-right tabular-nums text-slate-600">
                {Number(holding.shares).toLocaleString(undefined, { maximumFractionDigits: 4 })}
              </td>
              <td className="px-4 py-2 text-right tabular-nums text-slate-600">
                {holding.cost_basis == null ? '—' : formatCurrency(Number(holding.cost_basis))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
