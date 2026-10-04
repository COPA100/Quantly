import type { ComponentType } from 'react'
import PortfolioOverview from './components/PortfolioOverview'
import RiskInsights from './components/RiskInsights'
import CorrelationSection from './components/sections/CorrelationSection'
import PerformanceSection from './components/sections/PerformanceSection'
import StressSection from './components/sections/StressSection'
import VarSection from './components/sections/VarSection'
import type { Analytics } from './lib/types'

export interface AnalyticsSection {
  // stable id, also the error boundary's label
  key: string
  // renders null when its metrics are missing or failed
  component: ComponentType<{ analytics: Analytics }>
}

// render order of the analytics on a portfolio page. to add a section, write a
// component that takes `analytics` and append it here.
export const SECTIONS: AnalyticsSection[] = [
  { key: 'overview', component: PortfolioOverview },
  { key: 'performance', component: PerformanceSection },
  { key: 'risk', component: RiskInsights },
  { key: 'correlation', component: CorrelationSection },
  { key: 'stress', component: StressSection },
  { key: 'var_suite', component: VarSection },
]
