import { Link, useParams } from 'react-router-dom'
import AnalysisProgress from '../components/AnalysisProgress'
import StatusBadge from '../components/StatusBadge'
import { errorMessage } from '../lib/api'
import { usePortfolioStatus } from '../lib/portfolio-hooks'
import { isTerminalStatus } from '../lib/types'

export default function PortfolioDetailPage() {
  const { id } = useParams()
  const portfolioId = Number(id)
  const status = usePortfolioStatus(portfolioId)

  if (status.isPending) {
    return <p className="text-sm text-slate-500">Loading…</p>
  }
  if (status.isError) {
    return <p className="text-sm text-red-600">{errorMessage(status.error)}</p>
  }

  const data = status.data
  const complete = data.status === 'complete'

  return (
    <div>
      <Link to="/" className="text-sm text-slate-500 hover:text-slate-900">
        ← Portfolios
      </Link>
      <div className="mt-2 flex items-center gap-3">
        <h1 className="text-2xl font-semibold text-slate-900">Portfolio #{data.id}</h1>
        <StatusBadge status={data.status} />
      </div>

      <div className="mt-6">
        {!isTerminalStatus(data.status) && <AnalysisProgress status={data.status} />}
        {data.status === 'failed' && <AnalysisProgress status="failed" />}
        {complete && <p className="text-sm text-slate-600">Analysis ready.</p>}
      </div>
    </div>
  )
}
