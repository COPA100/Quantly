import { isMetricError } from '../../lib/metrics'
import type { Analytics } from '../../lib/types'

// shown in place of a section the analysis could not produce
export default function Unavailable({
  analytics,
  metricKey,
  what,
}: {
  analytics: Analytics
  metricKey: string
  what: string
}) {
  const value = analytics[metricKey] as { reason?: string; insight?: string } | undefined
  let reason = `There is not enough data for ${what} on this portfolio yet.`
  if (value && !isMetricError(value)) {
    if (typeof value.reason === 'string') reason = value.reason
    else if (typeof value.insight === 'string' && value.insight) reason = value.insight
  }
  return (
    <div className="max-w-xl">
      <h2 className="display-md text-ink">No {what} for this portfolio</h2>
      <p className="mt-2 text-body">{reason}</p>
    </div>
  )
}
