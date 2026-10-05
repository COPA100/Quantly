import { Link, NavLink, Outlet, useParams } from 'react-router-dom'
import AnalysisPipeline from '../../components/AnalysisPipeline'
import { buttonVariants } from '../../lib/ui'
import Spinner from '../../components/Spinner'
import { errorMessage } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { useAnalytics, usePortfolio, usePortfolioStatus } from '../../lib/portfolio-hooks'
import type { PortfolioData } from './context'
import KeyFigures from './KeyFigures'

const TABS = [
  { to: '', label: 'Overview', end: true },
  { to: 'risk', label: 'Risk' },
  { to: 'stress', label: 'Stress tests' },
  { to: 'optimize', label: 'Optimization' },
  { to: 'factors', label: 'Factors' },
  { to: 'holdings', label: 'Holdings' },
]

const tabClass = ({ isActive }: { isActive: boolean }) =>
  `relative -mb-px whitespace-nowrap border-b-2 px-1 pb-3 pt-1 text-sm font-medium transition-colors ${
    isActive ? 'border-ink text-ink' : 'border-transparent text-muted hover:text-ink'
  }`

function displayName(filename: string): string {
  return filename.replace(/\.csv$/i, '')
}

export default function PortfolioLayout() {
  const { id } = useParams()
  const portfolioId = Number(id)
  const status = usePortfolioStatus(portfolioId)
  const portfolio = usePortfolio(portfolioId)
  // the live status is the source of truth; fall back to the snapshot
  const liveStatus = status.data?.status ?? portfolio.data?.status ?? 'pending'
  const complete = liveStatus === 'complete'
  const analytics = useAnalytics(portfolioId, complete)

  if (portfolio.isPending) {
    return <Spinner />
  }
  if (portfolio.isError) {
    return <p className="text-loss">{errorMessage(portfolio.error)}</p>
  }

  const detail = portfolio.data
  const context: PortfolioData | null =
    complete && analytics.data ? { analytics: analytics.data, detail } : null

  return (
    <div>
      <Link to="/" className="text-sm text-muted transition-colors hover:text-ink">
        Portfolios
      </Link>
      <div className="mt-3 flex flex-wrap items-end justify-between gap-x-8 gap-y-4">
        <div className="min-w-0">
          <h1 className="display-xl truncate text-ink">{displayName(detail.original_filename)}</h1>
          <p className="mt-2 text-sm text-muted">
            {detail.holdings.length} holdings, uploaded {formatDate(detail.created_at)}
          </p>
        </div>
        <AnalysisPipeline status={liveStatus} attempts={status.data?.job?.attempts} />
      </div>

      {liveStatus === 'failed' && (
        <div className="mt-10 max-w-xl rounded-[var(--radius-panel)] border border-hairline bg-surface p-6">
          <p className="text-ink">The analysis could not finish.</p>
          <p className="mt-1 text-sm text-body">
            Check that the file is a positions export with symbol, quantity and cost basis columns,
            then upload it again.
          </p>
          <Link to="/upload" className={`${buttonVariants.secondary} mt-4`}>
            Upload again
          </Link>
        </div>
      )}

      {!complete && liveStatus !== 'failed' && (
        <p className="mt-10 max-w-xl text-body">
          Pricing your holdings and running the analysis. This page fills in on its own when it is
          done, usually within a minute.
        </p>
      )}

      {complete && !context && (
        <div className="mt-10">
          <Spinner />
        </div>
      )}

      {context && (
        <>
          <div className="mt-8">
            <KeyFigures analytics={context.analytics} />
          </div>
          <nav
            aria-label="Analysis sections"
            className="mt-8 flex gap-7 overflow-x-auto border-b border-hairline"
          >
            {TABS.map((tab) => (
              <NavLink key={tab.label} to={tab.to} end={tab.end} className={tabClass}>
                {tab.label}
              </NavLink>
            ))}
          </nav>
          <div className="pt-10">
            <Outlet context={context} />
          </div>
        </>
      )}
    </div>
  )
}
