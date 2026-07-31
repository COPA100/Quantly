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
