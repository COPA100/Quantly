import { useQuery } from '@tanstack/react-query'
import { getPortfolioStatus } from './portfolio-api'
import { isTerminalStatus } from './types'

// polls the status endpoint until the analysis reaches a terminal state
export function usePortfolioStatus(id: number) {
  return useQuery({
    queryKey: ['portfolio-status', id],
    queryFn: () => getPortfolioStatus(id),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status && isTerminalStatus(status) ? false : 1500
    },
  })
}
