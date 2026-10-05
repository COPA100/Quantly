import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth-context'
import { buttonVariants } from '../lib/ui'
import Wordmark from './Wordmark'

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `text-sm font-medium transition-colors ${isActive ? 'text-ink' : 'text-muted hover:text-ink'}`

export default function RootLayout() {
  const { logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-hairline bg-canvas/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-[1280px] items-center justify-between gap-4 px-5 sm:px-8">
          <div className="flex items-center gap-5 sm:gap-8">
            <Wordmark />
            <nav className="flex items-center gap-6">
              <NavLink to="/" end className={navLinkClass}>
                Portfolios
              </NavLink>
            </nav>
          </div>
          <div className="flex items-center gap-4 sm:gap-5">
            <button
              type="button"
              onClick={handleLogout}
              className="whitespace-nowrap text-sm font-medium text-muted transition-colors hover:text-ink"
            >
              Sign out
            </button>
            <Link to="/upload" className={`${buttonVariants.primary} whitespace-nowrap`}>
              <span className="sm:hidden">Upload</span>
              <span className="hidden sm:inline">Upload portfolio</span>
            </Link>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-[1280px] px-5 pb-24 pt-10 sm:px-8">
        <Outlet />
      </main>
    </div>
  )
}
