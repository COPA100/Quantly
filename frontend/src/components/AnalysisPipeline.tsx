import { pillClass } from '../lib/ui'

interface Stage {
  key: string
  label: string
  reached: string
}

const STAGES: Stage[] = [
  { key: 'upload', label: 'Uploaded', reached: 'bg-stage-upload text-ink' },
  { key: 'queue', label: 'Queued', reached: 'bg-stage-queue text-ink' },
  { key: 'analyze', label: 'Analyzing', reached: 'bg-stage-analyze text-ink' },
  { key: 'done', label: 'Done', reached: 'bg-stage-done text-white' },
]

// how far along the job is, by portfolio status
const PROGRESS: Record<string, number> = { pending: 1, processing: 2, complete: 3 }

interface Props {
  status: string
  attempts?: number
}

export default function AnalysisPipeline({ status, attempts = 0 }: Props) {
  const failed = status === 'failed'
  const at = failed ? 2 : (PROGRESS[status] ?? 0)

  return (
    <ol className="flex flex-wrap items-center gap-1.5" aria-label="Analysis progress">
      {STAGES.map((stage, i) => {
        const isFailure = failed && i === 3
        const reached = i <= at && !isFailure
        const active = i === at && !failed && status !== 'complete'
        const label = isFailure ? 'Failed' : stage.label
        return (
          <li key={stage.key} className="flex items-center gap-1.5">
            {i > 0 && (
              <span
                aria-hidden
                className={`h-px w-4 ${i <= at || isFailure ? 'bg-hairline-strong' : 'bg-hairline'}`}
              />
            )}
            <span
              aria-current={active ? 'step' : undefined}
              className={`${pillClass} ${
                isFailure
                  ? 'bg-loss text-white'
                  : reached
                    ? stage.reached
                    : 'border border-hairline text-muted-soft'
              }`}
            >
              {active && (
                <span aria-hidden className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
              )}
              {label}
            </span>
          </li>
        )
      })}
      {attempts > 1 && !failed && status !== 'complete' && (
        <li className="ml-1 text-sm text-muted">attempt {attempts}</li>
      )}
    </ol>
  )
}
