import { useQuery } from '@tanstack/react-query'
import { getAnalytics, getPortfolio, getPortfolioStatus } from './portfolio-api'
import { isTerminalStatus } from './types'

// polls the status endpoint until the analysis reaches a terminal state
export function usePortfolioStatus(id: number) {
  return useQuery({
    queryKey: ['portfolio-status', id],
    queryFn: () => getPortfolioStatus(id),
    enabled: Number.isFinite(id),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status && isTerminalStatus(status) ? false : 1500
    },
  })
}

export function usePortfolio(id: number) {
  return useQuery({
    queryKey: ['portfolio', id],
    queryFn: () => getPortfolio(id),
    enabled: Number.isFinite(id),
  })
}

// only fetched once the analysis is complete
export function useAnalytics(id: number, enabled: boolean) {
  return useQuery({
    queryKey: ['analytics', id],
    queryFn: () => getAnalytics(id),
    enabled: enabled && Number.isFinite(id),
  })
}
