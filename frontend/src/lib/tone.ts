export type Tone = 'positive' | 'negative' | 'neutral'

export const toneTextColor: Record<Tone, string> = {
  positive: 'text-emerald-600',
  negative: 'text-red-600',
  neutral: 'text-slate-900',
}
