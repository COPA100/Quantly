import { apiFetch } from './api'
import type { PortfolioAccepted } from './types'

export function uploadPortfolio(file: File): Promise<PortfolioAccepted> {
  const form = new FormData()
  form.append('file', file)
  return apiFetch<PortfolioAccepted>('/portfolios', { method: 'POST', body: form })
}
