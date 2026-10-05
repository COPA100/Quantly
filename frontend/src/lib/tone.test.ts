import { describe, expect, it } from 'vitest'
import { type Tone, toneOf, toneTextColor } from './tone'

describe('toneTextColor', () => {
  it('has a distinct class for every tone', () => {
    const tones: Tone[] = ['positive', 'negative', 'neutral']
    const classes = tones.map((t) => toneTextColor[t])
    expect(new Set(classes).size).toBe(tones.length)
    classes.forEach((c) => expect(c).toMatch(/^text-/))
  })

  it('maps positive to the gain colour and negative to the loss colour', () => {
    expect(toneTextColor.positive).toBe('text-gain')
    expect(toneTextColor.negative).toBe('text-loss')
  })

  it('reads the tone from the sign', () => {
    expect(toneOf(0.1)).toBe('positive')
    expect(toneOf(-0.1)).toBe('negative')
    expect(toneOf(0)).toBe('neutral')
  })
})
