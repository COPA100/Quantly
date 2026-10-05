import CorrelationHeatmap from '../../components/CorrelationHeatmap'
import Panel from '../../components/Panel'
import SectionBoundary from '../../components/SectionBoundary'
import RiskContributionSection from '../../components/sections/RiskContributionSection'
import VarSection from '../../components/sections/VarSection'
import { formatPercent } from '../../lib/format'
import type { Analytics } from '../../lib/types'
import { usePortfolioData } from './context'

interface Measure {
  name: string
  value: string
  text?: string
  negative?: boolean
}

function measures(a: Analytics): Measure[] {
  const i = a.insights ?? {}
  const out: Measure[] = []
  if (a.volatility) {
    out.push({ name: 'Volatility', value: formatPercent(a.volatility.annualized), text: i.volatility })
  }
  if (a.drawdown) {
    out.push({
      name: 'Worst drop',
      value: formatPercent(a.drawdown.max_drawdown),
      text: i.drawdown,
      negative: true,
    })
  }
  if (a.sharpe) out.push({ name: 'Sharpe ratio', value: a.sharpe.ratio.toFixed(2), text: i.sharpe })
  if (a.sortino) out.push({ name: 'Sortino ratio', value: a.sortino.ratio.toFixed(2), text: i.sortino })
  if (a.beta) out.push({ name: 'Beta', value: a.beta.beta.toFixed(2), text: i.beta })
  if (a.var) {
    const { var: v, cvar, horizon_days, confidence } = a.var
    const pct = Math.round(confidence * 100)
    out.push({
      name: `Value at risk, ${horizon_days} days`,
      value: formatPercent(v),
      negative: true,
      text: `In ${pct}% of months you would not expect to lose more than this. When you do, the average loss is ${formatPercent(cvar)}.`,
    })
  }
  return out
}

export default function RiskTab() {
  const { analytics } = usePortfolioData()
  const rows = measures(analytics)
  const correlation = analytics.correlation

  return (
    <div className="space-y-14">
      <div className="grid gap-6 lg:grid-cols-12">
        {rows.length > 0 && (
          <Panel title="Risk measures" className="lg:col-span-5">
            <dl>
              {rows.map((m) => (
                <div key={m.name} className="border-b border-hairline-soft px-5 py-4 last:border-0">
                  <div className="flex items-baseline justify-between gap-4">
                    <dt className="text-[15px] text-ink">{m.name}</dt>
                    <dd className={`num text-lg ${m.negative ? 'text-loss' : 'text-ink'}`}>{m.value}</dd>
                  </div>
                  {m.text && <p className="mt-1 text-sm text-body">{m.text}</p>}
                </div>
              ))}
            </dl>
          </Panel>
        )}
        <div className="lg:col-span-7">
          <SectionBoundary name="value at risk">
            <VarSection analytics={analytics} />
          </SectionBoundary>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-12">
        {correlation && correlation.tickers.length >= 2 && (
          <Panel
            title="How your holdings move together"
            lede={analytics.insights?.correlation}
            className="lg:col-span-7"
          >
            <CorrelationHeatmap correlation={correlation} />
          </Panel>
        )}
        <div className="lg:col-span-5">
          <SectionBoundary name="risk contribution">
            <RiskContributionSection analytics={analytics} />
          </SectionBoundary>
        </div>
      </div>
    </div>
  )
}
