type Tone = 'positive' | 'negative' | 'neutral'

const toneColor: Record<Tone, string> = {
  positive: 'text-emerald-600',
  negative: 'text-red-600',
  neutral: 'text-slate-900',
}

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
      <p className={`mt-1 text-2xl font-semibold tabular-nums ${toneColor[tone]}`}>{value}</p>
      {sub && <p className={`mt-0.5 text-sm tabular-nums ${toneColor[tone]}`}>{sub}</p>}
    </div>
  )
}
