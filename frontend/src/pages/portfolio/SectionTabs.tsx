import SectionBoundary from '../../components/SectionBoundary'
import FactorSection from '../../components/sections/FactorSection'
import FrontierSection from '../../components/sections/FrontierSection'
import StressSection from '../../components/sections/StressSection'
import { metric } from '../../lib/metrics'
import { usePortfolioData } from './context'
import Unavailable from './Unavailable'

export function StressTab() {
  const { analytics } = usePortfolioData()
  const stress = metric<{ scenarios?: unknown[] }>(analytics, 'stress')
  if (!stress?.scenarios?.length) {
    return <Unavailable analytics={analytics} metricKey="stress" what="stress tests" />
  }
  return (
    <SectionBoundary name="stress tests">
      <StressSection analytics={analytics} />
    </SectionBoundary>
  )
}

export function OptimizeTab() {
  const { analytics } = usePortfolioData()
  const frontier = metric<{ points?: unknown[] }>(analytics, 'frontier')
  if (!frontier?.points?.length) {
    return <Unavailable analytics={analytics} metricKey="frontier" what="efficient frontier" />
  }
  return (
    <SectionBoundary name="efficient frontier">
      <FrontierSection analytics={analytics} />
    </SectionBoundary>
  )
}

export function FactorsTab() {
  const { analytics } = usePortfolioData()
  const factors = metric<{ available?: boolean }>(analytics, 'factors')
  if (!factors?.available) {
    return <Unavailable analytics={analytics} metricKey="factors" what="factor model" />
  }
  return (
    <SectionBoundary name="factor model">
      <FactorSection analytics={analytics} />
    </SectionBoundary>
  )
}
