import { type Tone, toneTextColor } from '../lib/tone'

interface Props {
  title: string
  value: string
  tone?: Tone
  description?: string
}

export default function InsightCard({ title, value, tone = 'neutral', description }: Props) {
  return (
    <div className="flex flex-col rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{title}</p>
        <p className={`text-lg font-semibold tabular-nums ${toneTextColor[tone]}`}>{value}</p>
      </div>
      {description && (
        <p className="mt-2 text-sm leading-relaxed text-slate-600">{description}</p>
      )}
    </div>
  )
}
