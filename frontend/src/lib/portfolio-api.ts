import { apiFetch } from './api'
import type {
  Analytics,
  Portfolio,
  PortfolioAccepted,
  PortfolioDetail,
  PortfolioStatusRead,
} from './types'

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

export function getPortfolio(id: number): Promise<PortfolioDetail> {
  return apiFetch<PortfolioDetail>(`/portfolios/${id}`)
}

export function getAnalytics(id: number): Promise<Analytics> {
  return apiFetch<Analytics>(`/portfolios/${id}/analytics`)
}
