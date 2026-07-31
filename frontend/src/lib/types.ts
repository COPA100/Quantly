export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface User {
  id: number
  email: string
  created_at: string
}

export interface Portfolio {
  id: number
  original_filename: string
  status: string
  created_at: string
  updated_at: string
}

export interface PortfolioAccepted {
  id: number
  status: string
  job_id: number
}

export interface Job {
  id: number
  status: string
  started_at: string | null
  finished_at: string | null
}

export interface PortfolioStatusRead {
  id: number
  status: string
  job: Job | null
}

export function isTerminalStatus(status: string): boolean {
  return status === 'complete' || status === 'failed'
}

export interface Holding {
  id: number
  ticker: string
  shares: string
  cost_basis: string | null
  purchase_date: string | null
}

export interface PortfolioDetail extends Portfolio {
  holdings: Holding[]
}

export interface Allocation {
  ticker: string
  pct_allocation: number
}

export interface Correlation {
  tickers: string[]
  matrix: number[][]
  average: number
}

// metric_name -> value blob written by the worker; every field is optional
// because the endpoint returns {} until the analysis completes
export interface Analytics {
  value?: { total: number }
  gain_loss?: { gain_loss: number; gain_loss_pct: number }
  allocation?: { positions: Allocation[] }
  volatility?: { annualized: number }
  returns?: { annualized: number }
  sharpe?: { ratio: number }
  sortino?: { ratio: number }
  drawdown?: { max_drawdown: number; duration: number }
  beta?: { beta: number }
  var?: { horizon_days: number; confidence: number; var: number; cvar: number }
  equity_curve?: { dates: string[]; values: number[] }
  correlation?: Correlation
  insights?: Record<string, string>
}
