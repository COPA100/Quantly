import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { buttonVariants } from '../lib/ui'
import Spinner from '../components/Spinner'
import StatusBadge from '../components/StatusBadge'
import { errorMessage } from '../lib/api'
import { formatDate } from '../lib/format'
import { listPortfolios } from '../lib/portfolio-api'

export default function PortfoliosPage() {
  const query = useQuery({ queryKey: ['portfolios'], queryFn: listPortfolios })
  const portfolios = query.data ?? []

  return (
    <div>
      <h1 className="display-xl text-ink">Portfolios</h1>
      <p className="mt-2 max-w-[60ch] text-body">
        Each upload is a snapshot of your holdings, analyzed against up to twenty years of daily
        prices.
      </p>

      <div className="mt-10">
        {query.isPending && <Spinner />}

        {query.isError && <p className="text-loss">{errorMessage(query.error)}</p>}

        {query.isSuccess && portfolios.length === 0 && (
          <div className="max-w-xl rounded-[var(--radius-panel)] border border-hairline bg-surface p-8">
            <h2 className="display-md text-ink">Start with a positions export</h2>
            <p className="mt-2 text-body">
              Download your holdings as a CSV from your brokerage and upload it here. The analysis
              takes about a minute.
            </p>
            <Link to="/upload" className={`${buttonVariants.primary} mt-6`}>
              Upload portfolio
            </Link>
          </div>
        )}

        {portfolios.length > 0 && (
          <div className="overflow-hidden rounded-[var(--radius-panel)] border border-hairline bg-surface">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[13px] text-muted">
                  <th scope="col" className="px-5 py-3 font-normal">Portfolio</th>
                  <th scope="col" className="hidden px-5 py-3 font-normal sm:table-cell">Uploaded</th>
                  <th scope="col" className="px-5 py-3 text-right font-normal">Analysis</th>
                </tr>
              </thead>
              <tbody>
                {portfolios.map((portfolio) => (
                  <tr key={portfolio.id} className="group border-t border-hairline-soft">
                    <td className="px-5 py-0">
                      <Link
                        to={`/portfolios/${portfolio.id}`}
                        className="block py-4 text-[15px] text-ink group-hover:underline group-hover:decoration-hairline-strong group-hover:underline-offset-4"
                      >
                        {portfolio.original_filename.replace(/\.csv$/i, '')}
                      </Link>
                    </td>
                    <td className="num hidden px-5 py-4 text-[13px] text-muted sm:table-cell">
                      {formatDate(portfolio.created_at)}
                    </td>
                    <td className="px-5 py-4 text-right">
                      <StatusBadge status={portfolio.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
