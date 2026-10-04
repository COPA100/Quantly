import { apiFetch, ApiError, authedFetch } from './api'
import { parseSse } from './sse'
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

// streams status updates over server-sent events. fetch rather than
// EventSource, so the bearer header is reused instead of a token in the url.
// resolves when the server closes the stream, rejects on any failure.
export async function streamPortfolioStatus(
  id: number,
  onStatus: (status: PortfolioStatusRead) => void,
  signal: AbortSignal,
): Promise<void> {
  const res = await authedFetch(`/portfolios/${id}/events`, {
    headers: { Accept: 'text/event-stream' },
    signal,
  })
  if (!res.ok || !res.body) {
    throw new ApiError(res.status, res.statusText)
  }
  for await (const message of parseSse(res.body)) {
    if (message.event === 'status') {
      onStatus(JSON.parse(message.data) as PortfolioStatusRead)
    }
  }
}
