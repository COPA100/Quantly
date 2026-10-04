import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import StatTile from './StatTile'

afterEach(cleanup)

describe('StatTile', () => {
  it('renders label and value with neutral tone by default', () => {
    render(<StatTile label="Sharpe" value="1.20" />)
    expect(screen.getByText('Sharpe')).toBeTruthy()
    expect(screen.getByText('1.20').className).toContain('text-slate-900')
  })

  it('colours value and sub by tone', () => {
    render(<StatTile label="Return" value="+5%" sub="vs spy" tone="negative" />)
    expect(screen.getByText('+5%').className).toContain('text-red-600')
    expect(screen.getByText('vs spy').className).toContain('text-red-600')
  })

  it('omits the sub line when not given', () => {
    const { container } = render(<StatTile label="x" value="y" />)
    expect(container.querySelectorAll('p')).toHaveLength(2)
  })
})
