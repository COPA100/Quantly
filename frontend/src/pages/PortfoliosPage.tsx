import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { buttonClass } from '../components/Button'
import StatusBadge from '../components/StatusBadge'
import { errorMessage } from '../lib/api'
import { formatDate } from '../lib/format'
import { listPortfolios } from '../lib/portfolio-api'

export default function PortfoliosPage() {
  const query = useQuery({ queryKey: ['portfolios'], queryFn: listPortfolios })

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Portfolios</h1>
        <Link to="/upload" className={buttonClass}>
          Upload
        </Link>
      </div>

      <div className="mt-6">
        {query.isPending && <p className="text-sm text-slate-500">Loading…</p>}

        {query.isError && <p className="text-sm text-red-600">{errorMessage(query.error)}</p>}

        {query.data?.length === 0 && (
          <div className="rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center">
            <p className="text-sm text-slate-600">No portfolios yet.</p>
            <Link
              to="/upload"
              className="mt-2 inline-block text-sm font-medium text-indigo-600 hover:underline"
            >
              Upload your first one
            </Link>
          </div>
        )}

        {query.data && query.data.length > 0 && (
          <ul className="divide-y divide-slate-200 overflow-hidden rounded-xl border border-slate-200 bg-white">
            {query.data.map((portfolio) => (
              <li key={portfolio.id}>
                <Link
                  to={`/portfolios/${portfolio.id}`}
                  className="flex items-center justify-between px-4 py-3 hover:bg-slate-50"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-900">
                      {portfolio.original_filename}
                    </p>
                    <p className="text-xs text-slate-500">{formatDate(portfolio.created_at)}</p>
                  </div>
                  <StatusBadge status={portfolio.status} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
