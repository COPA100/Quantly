import { formatPercent } from '../../lib/format'
import { MARKERS, type FrontierResult } from '../../lib/frontier'
import { metric } from '../../lib/metrics'
import type { Analytics } from '../../lib/types'
import FrontierChart from '../FrontierChart'
import Panel from '../Panel'

export default function FrontierSection({ analytics }: { analytics: Analytics }) {
  const frontier = metric<FrontierResult>(analytics, 'frontier')
  if (!frontier || !frontier.points?.length) return null

  const columns = MARKERS.flatMap((m) => {
    const p = frontier[m.key]
    return p ? [{ ...m, weights: p.weights, vol: p.vol, ret: p.ret }] : []
  })
  const tickers = Object.keys(frontier.current?.weights ?? columns[0]?.weights ?? {}).sort(
    (a, b) =>
      (frontier.current?.weights[b] ?? 0) - (frontier.current?.weights[a] ?? 0) || a.localeCompare(b),
  )

  return (
    <Panel title="Efficient frontier" lede={frontier.insight} surface={false}>
      <div className="grid gap-6 lg:grid-cols-12">
        <div className="flex flex-col justify-center rounded-[var(--radius-panel)] border border-hairline bg-surface p-5 lg:col-span-7">
          <FrontierChart frontier={frontier} />
        </div>
        <div className="overflow-x-auto rounded-[var(--radius-panel)] border border-hairline bg-surface lg:col-span-5">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[13px] text-muted">
                <th scope="col" className="px-4 py-3 font-normal">Holding</th>
                {columns.map((c) => (
                  <th key={c.key} scope="col" className="px-3 py-3 text-right font-normal">
                    {c.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tickers.map((t) => (
                <tr key={t} className="border-t border-hairline-soft">
                  <td className="num px-4 py-2 text-ink">{t}</td>
                  {columns.map((c) => {
                    const w = c.weights[t] ?? 0
                    return (
                      <td key={c.key} className={`num px-3 py-2 text-right ${w < 0.0005 ? 'text-muted-soft' : 'text-ink'}`}>
                        {formatPercent(w)}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t border-hairline text-[13px]">
                <td className="whitespace-nowrap px-4 py-2 text-muted">Return, risk</td>
                {columns.map((c) => (
                  <td key={c.key} className="num whitespace-nowrap px-3 py-2 text-right text-body">
                    {formatPercent(c.ret, 0)} / {formatPercent(c.vol, 0)}
                  </td>
                ))}
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </Panel>
  )
}
