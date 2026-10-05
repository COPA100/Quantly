import { useOutletContext } from 'react-router-dom'
import type { Analytics, PortfolioDetail } from '../../lib/types'

export interface PortfolioData {
  analytics: Analytics
  detail: PortfolioDetail
}

export function usePortfolioData(): PortfolioData {
  return useOutletContext<PortfolioData>()
}
