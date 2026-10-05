export interface FrontierPortfolio {
  vol: number
  ret: number
  weights: Record<string, number>
}

// the `frontier` analytics key. the portfolios are null (and points empty)
// when the book is too small or too short to optimize.
export interface FrontierResult {
  points: { vol: number; ret: number }[]
  current: FrontierPortfolio | null
  min_variance: FrontierPortfolio | null
  max_sharpe: FrontierPortfolio | null
  risk_parity: FrontierPortfolio | null
  insight: string
}

export interface FrontierMarker {
  key: 'current' | 'min_variance' | 'max_sharpe' | 'risk_parity'
  label: string
  color: string
  shape: 'circle' | 'square' | 'diamond' | 'triangle'
}

// shape carries identity, so the palette can stay in warm neutrals. the
// current portfolio is the only solid ink mark.
export const MARKERS: FrontierMarker[] = [
  { key: 'current', label: 'Your portfolio', color: '#26251e', shape: 'circle' },
  { key: 'min_variance', label: 'Min variance', color: '#807d72', shape: 'square' },
  { key: 'max_sharpe', label: 'Max Sharpe', color: '#807d72', shape: 'diamond' },
  { key: 'risk_parity', label: 'Risk parity', color: '#807d72', shape: 'triangle' },
]
