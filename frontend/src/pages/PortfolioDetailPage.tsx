import { Link, useParams } from 'react-router-dom'
import AnalysisProgress from '../components/AnalysisProgress'
import CorrelationHeatmap from '../components/CorrelationHeatmap'
import EquityChart from '../components/EquityChart'
import HoldingsTable from '../components/HoldingsTable'
import PortfolioOverview from '../components/PortfolioOverview'
import RiskInsights from '../components/RiskInsights'
import Section from '../components/Section'
import Spinner from '../components/Spinner'
import StatusBadge from '../components/StatusBadge'
import { errorMessage } from '../lib/api'
import { useAnalytics, usePortfolio, usePortfolioStatus } from '../lib/portfolio-hooks'
import { isTerminalStatus } from '../lib/types'

export default function PortfolioDetailPage() {
  const { id } = useParams()
  const portfolioId = Number(id)
  const status = usePortfolioStatus(portfolioId)
  const portfolio = usePortfolio(portfolioId)
  // the polled status is the live source of truth; fall back to the snapshot
  const liveStatus = status.data?.status ?? portfolio.data?.status ?? 'pending'
  const complete = liveStatus === 'complete'
  const analytics = useAnalytics(portfolioId, complete)

  if (portfolio.isPending) {
    return <p className="text-sm text-slate-500">Loading…</p>
  }
  if (portfolio.isError) {
    return <p className="text-sm text-red-600">{errorMessage(portfolio.error)}</p>
  }

  const detail = portfolio.data

  return (
    <div className="space-y-8">
      <div>
        <Link to="/" className="text-sm text-slate-500 hover:text-slate-900">
          ← Portfolios
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold text-slate-900">{detail.original_filename}</h1>
          <StatusBadge status={liveStatus} />
        </div>
      </div>

      {!isTerminalStatus(liveStatus) && <AnalysisProgress status={liveStatus} />}
      {liveStatus === 'failed' && <AnalysisProgress status="failed" />}

      {complete && analytics.isPending && (
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <Spinner />
          Loading analytics…
        </div>
      )}
      {complete && analytics.data && (
        <>
          <PortfolioOverview analytics={analytics.data} />
          {analytics.data.equity_curve && analytics.data.equity_curve.dates.length > 1 && (
            <Section title="Performance">
              <div className="rounded-xl border border-slate-200 bg-white p-4">
                <EquityChart
                  dates={analytics.data.equity_curve.dates}
                  values={analytics.data.equity_curve.values}
                />
              </div>
            </Section>
          )}
          <RiskInsights analytics={analytics.data} />
          {analytics.data.correlation && analytics.data.correlation.tickers.length >= 2 && (
            <Section title="Correlation">
              {analytics.data.insights?.correlation && (
                <p className="mb-3 text-sm text-slate-600">
                  {analytics.data.insights.correlation}
                </p>
              )}
              <CorrelationHeatmap correlation={analytics.data.correlation} />
            </Section>
          )}
        </>
      )}

      {complete && (
        <Section title="Holdings">
          <HoldingsTable holdings={detail.holdings} />
        </Section>
      )}
    </div>
  )
}
