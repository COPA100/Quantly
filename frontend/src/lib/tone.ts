export type Tone = 'positive' | 'negative' | 'neutral'

export const toneTextColor: Record<Tone, string> = {
  positive: 'text-gain',
  negative: 'text-loss',
  neutral: 'text-ink',
}

export function toneOf(value: number): Tone {
  return value > 0 ? 'positive' : value < 0 ? 'negative' : 'neutral'
}
