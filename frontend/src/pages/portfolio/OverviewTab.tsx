import { lazy, Suspense } from 'react'
import { Link } from 'react-router-dom'
import AllocationList from '../../components/AllocationList'
import Panel from '../../components/Panel'
import Spinner from '../../components/Spinner'
import { metric } from '../../lib/metrics'
import type { Analytics } from '../../lib/types'
import { usePortfolioData } from './context'

// the charting library is heavy; load it only when the overview needs it
const EquityChart = lazy(() => import('../../components/EquityChart'))

interface Finding {
  area: string
  text: string
  to: string
  link: string
}

function insightOf(analytics: Analytics, key: string): string | undefined {
  return metric<{ insight?: string }>(analytics, key)?.insight || undefined
}

function findings(analytics: Analytics): Finding[] {
  const out: Finding[] = []
  const add = (area: string, text: string | undefined, to: string, link: string) => {
    if (text) out.push({ area, text, to, link })
  }
  add('Risk', insightOf(analytics, 'risk_contribution'), 'risk', 'See where the risk comes from')
  add('Diversification', analytics.insights?.correlation, 'risk', 'See the correlation matrix')
  add('Stress tests', insightOf(analytics, 'stress'), 'stress', 'Open stress tests')
  add('Optimization', insightOf(analytics, 'frontier'), 'optimize', 'Compare other mixes')
  const factors = metric<{ available: boolean; insight?: string }>(analytics, 'factors')
  add('Factors', factors?.available ? factors.insight : undefined, 'factors', 'See factor loadings')
  return out
}

export default function OverviewTab() {
  const { analytics } = usePortfolioData()
  const curve = analytics.equity_curve
  const positions = analytics.allocation?.positions ?? []
  const items = findings(analytics)

  return (
    <div className="space-y-14">
      <div className="grid gap-6 lg:grid-cols-12">
        {curve && curve.dates.length > 1 && (
          <Panel
            title="Value over time"
            lede="Market value of today's holdings on every trading day of the last five years."
            className="lg:col-span-8"
          >
            <div className="p-4">
              <Suspense
                fallback={
                  <div className="flex h-[340px] items-center justify-center">
                    <Spinner />
                  </div>
                }
              >
                <EquityChart dates={curve.dates} values={curve.values} />
              </Suspense>
            </div>
          </Panel>
        )}
        {positions.length > 0 && (
          <Panel title="Allocation" lede={analytics.insights?.concentration} className="lg:col-span-4">
            <AllocationList positions={positions} />
          </Panel>
        )}
      </div>

      {items.length > 0 && (
        <section>
          <h2 className="display-md text-ink">What stands out</h2>
          <ul className="mt-4 grid gap-x-10 md:grid-cols-2">
            {items.map((f) => (
              <li key={f.area} className="border-t border-hairline py-5">
                <p className="text-[13px] text-muted">{f.area}</p>
                <p className="mt-1.5 max-w-[60ch] text-[17px] leading-snug text-ink">{f.text}</p>
                <Link
                  to={f.to}
                  className="mt-2 inline-block text-sm font-medium text-ink underline decoration-hairline-strong underline-offset-4 transition-colors hover:decoration-ink"
                >
                  {f.link}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
