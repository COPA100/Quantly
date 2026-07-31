import { apiFetch } from './api'
import type { Portfolio, PortfolioAccepted, PortfolioStatusRead } from './types'

export function uploadPortfolio(file: File): Promise<PortfolioAccepted> {
  const form = new FormData()
  form.append('file', file)
  return apiFetch<PortfolioAccepted>('/portfolios', { method: 'POST', body: form })
}

export function listPortfolios(): Promise<Portfolio[]> {
  return apiFetch<Portfolio[]>('/portfolios')
}

export function getPortfolioStatus(id: number): Promise<PortfolioStatusRead> {
  return apiFetch<PortfolioStatusRead>(`/portfolios/${id}/status`)
}
