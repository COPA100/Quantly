import type { Analytics } from '../../lib/types'
import CorrelationHeatmap from '../CorrelationHeatmap'
import Section from '../Section'

export default function CorrelationSection({ analytics }: { analytics: Analytics }) {
  const correlation = analytics.correlation
  if (!correlation || correlation.tickers.length < 2) return null
  return (
    <Section title="Correlation">
      {analytics.insights?.correlation && (
        <p className="mb-3 text-sm text-slate-600">{analytics.insights.correlation}</p>
      )}
      <CorrelationHeatmap correlation={correlation} />
    </Section>
  )
}
