import { describe, expect, it } from 'vitest'
import { type Tone, toneTextColor } from './tone'

describe('toneTextColor', () => {
  it('has a distinct class for every tone', () => {
    const tones: Tone[] = ['positive', 'negative', 'neutral']
    const classes = tones.map((t) => toneTextColor[t])
    expect(new Set(classes).size).toBe(tones.length)
    classes.forEach((c) => expect(c).toMatch(/^text-/))
  })

  it('maps positive to green and negative to red', () => {
    expect(toneTextColor.positive).toContain('emerald')
    expect(toneTextColor.negative).toContain('red')
  })
})
