import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import {
  getAnalytics,
  getPortfolio,
  getPortfolioStatus,
  streamPortfolioStatus,
} from './portfolio-api'
import { isTerminalStatus } from './types'

const POLL_INTERVAL_MS = 1500

// live status for a portfolio. updates arrive over a server-sent stream; if the
// stream can't be opened or drops before a terminal state, this falls back to
// polling the status endpoint until the analysis finishes.
export function usePortfolioStatus(id: number) {
  const queryClient = useQueryClient()
  const [streamFailed, setStreamFailed] = useState(false)
  const valid = Number.isFinite(id)

  useEffect(() => {
    if (!valid) return
    const controller = new AbortController()
    let finished = false
    setStreamFailed(false)

    streamPortfolioStatus(
      id,
      (status) => {
        queryClient.setQueryData(['portfolio-status', id], status)
        if (isTerminalStatus(status.status)) {
          finished = true
          void queryClient.invalidateQueries({ queryKey: ['portfolio', id] })
          void queryClient.invalidateQueries({ queryKey: ['analytics', id] })
          // the sidebar list shows each portfolio's status
          void queryClient.invalidateQueries({ queryKey: ['portfolios'] })
        }
      },
      controller.signal,
    ).then(
      () => {
        if (!finished) setStreamFailed(true)
      },
      () => {
        if (!controller.signal.aborted) setStreamFailed(true)
      },
    )

    return () => controller.abort()
  }, [id, valid, queryClient])

  return useQuery({
    queryKey: ['portfolio-status', id],
    queryFn: () => getPortfolioStatus(id),
    enabled: valid,
    // the stream keeps the cache fresh, so only poll once it has failed
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status && isTerminalStatus(status)) return false
      return streamFailed ? POLL_INTERVAL_MS : false
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
