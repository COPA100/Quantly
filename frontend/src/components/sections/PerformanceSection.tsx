import { lazy, Suspense } from 'react'
import type { Analytics } from '../../lib/types'
import Section from '../Section'
import Spinner from '../Spinner'

// the charting library is heavy; load it only when a detail page needs it
const EquityChart = lazy(() => import('../EquityChart'))

export default function PerformanceSection({ analytics }: { analytics: Analytics }) {
  const curve = analytics.equity_curve
  if (!curve || curve.dates.length <= 1) return null
  return (
    <Section title="Performance">
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <Suspense
          fallback={
            <div className="flex h-[280px] items-center justify-center">
              <Spinner />
            </div>
          }
        >
          <EquityChart dates={curve.dates} values={curve.values} />
        </Suspense>
      </div>
    </Section>
  )
}
