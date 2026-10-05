import { useQuery } from '@tanstack/react-query'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth-context'
import { formatDate } from '../lib/format'
import { listPortfolios } from '../lib/portfolio-api'
import { buttonVariants } from '../lib/ui'
import Wordmark from './Wordmark'

// the job stage as a dot, same colours as the pipeline pills
const STAGE_DOT: Record<string, string> = {
  pending: 'bg-stage-queue',
  processing: 'bg-stage-analyze',
  complete: 'bg-stage-done',
  failed: 'bg-loss',
}

function PortfolioSwitcher() {
  const query = useQuery({ queryKey: ['portfolios'], queryFn: listPortfolios })
  const portfolios = query.data ?? []

  return (
    <nav aria-label="Portfolios" className="min-h-0 flex-1 overflow-y-auto px-3">
      <NavLink
        to="/"
        end
        className={({ isActive }) =>
          `mb-1 flex items-center justify-between rounded-[var(--radius-control)] px-3 py-2 text-[13px] transition-colors ${
            isActive ? 'bg-surface text-ink ring-1 ring-hairline' : 'text-muted hover:text-ink'
          }`
        }
      >
        All portfolios
        {portfolios.length > 0 && <span className="num text-[12px]">{portfolios.length}</span>}
      </NavLink>
      <ul className="mt-1 space-y-0.5">
        {portfolios.map((p) => (
          <li key={p.id}>
            <NavLink
              to={`/portfolios/${p.id}`}
              className={({ isActive }) =>
                `group grid grid-cols-[0.5rem_1fr] items-center gap-x-3 rounded-[var(--radius-control)] px-3 py-2.5 transition-colors ${
                  isActive ? 'bg-surface ring-1 ring-hairline' : 'hover:bg-surface/60'
                }`
              }
            >
              <span
                aria-hidden
                className={`h-2 w-2 rounded-full ${STAGE_DOT[p.status] ?? 'bg-hairline-strong'}`}
              />
              <span className="truncate text-[14px] text-ink">{p.original_filename.replace(/\.csv$/i, '')}</span>
              <span />
              <span className="num text-[11px] text-muted">{formatDate(p.created_at)}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}

export default function RootLayout() {
  const { logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen lg:pl-[264px]">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-[264px] flex-col border-r border-hairline bg-canvas-soft lg:flex">
        <div className="flex h-20 items-center px-6">
          <Wordmark />
        </div>
        <div className="px-4 pb-6">
          <Link to="/upload" className={`${buttonVariants.primary} w-full`}>
            Upload portfolio
          </Link>
        </div>
        <PortfolioSwitcher />
        <div className="border-t border-hairline px-6 py-4">
          <button
            type="button"
            onClick={handleLogout}
            className="text-sm text-muted transition-colors hover:text-ink"
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* phones and tablets: a slim bar, the switcher lives on the list page */}
      <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-3 border-b border-hairline bg-canvas/95 px-5 backdrop-blur lg:hidden">
        <Wordmark />
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={handleLogout}
            className="whitespace-nowrap text-sm text-muted transition-colors hover:text-ink"
          >
            Sign out
          </button>
          <Link to="/upload" className={`${buttonVariants.primary} h-9 px-4`}>
            Upload
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-[1240px] px-5 pb-24 pt-8 sm:px-10 lg:pt-14">
        <Outlet />
      </main>
    </div>
  )
}
