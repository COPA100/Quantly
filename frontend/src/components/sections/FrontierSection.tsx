import { formatPercent } from '../../lib/format'
import { MARKERS, type FrontierResult } from '../../lib/frontier'
import { metric } from '../../lib/metrics'
import type { Analytics } from '../../lib/types'
import FrontierChart from '../FrontierChart'
import Section from '../Section'

export default function FrontierSection({ analytics }: { analytics: Analytics }) {
  const frontier = metric<FrontierResult>(analytics, 'frontier')
  if (!frontier || !frontier.points?.length) return null

  const columns = MARKERS.flatMap((m) => {
    const p = frontier[m.key]
    return p ? [{ ...m, weights: p.weights }] : []
  })
  const tickers = Object.keys(frontier.current?.weights ?? columns[0]?.weights ?? {}).sort(
    (a, b) => (frontier.current?.weights[b] ?? 0) - (frontier.current?.weights[a] ?? 0) || a.localeCompare(b),
  )

  return (
    <Section title="Efficient frontier">
      <p className="mb-3 text-sm text-slate-600">{frontier.insight}</p>
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <FrontierChart frontier={frontier} />
      </div>
      <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="px-4 py-2 font-medium">Weight</th>
              {columns.map((c) => (
                <th key={c.key} className="px-4 py-2 text-right font-medium">
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tickers.map((t) => (
              <tr key={t} className="border-b border-slate-100 last:border-0">
                <td className="px-4 py-2 font-medium text-slate-900">{t}</td>
                {columns.map((c) => (
                  <td key={c.key} className="px-4 py-2 text-right tabular-nums text-slate-700">
                    {formatPercent(c.weights[t] ?? 0)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Section>
  )
}
