import { type Tone, toneTextColor } from '../lib/tone'

interface Props {
  label: string
  value: string
  tone?: Tone
  sub?: string
}

export default function StatTile({ label, value, tone = 'neutral', sub }: Props) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-semibold tabular-nums ${toneTextColor[tone]}`}>{value}</p>
      {sub && <p className={`mt-0.5 text-sm tabular-nums ${toneTextColor[tone]}`}>{sub}</p>}
    </div>
  )
}
