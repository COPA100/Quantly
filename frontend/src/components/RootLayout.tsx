import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../lib/auth-context'

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `text-sm font-medium transition ${isActive ? 'text-slate-900' : 'text-slate-500 hover:text-slate-900'}`

export default function RootLayout() {
  const { logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-6">
            <Link to="/" className="text-lg font-semibold tracking-tight text-slate-900">
              Quantly
            </Link>
            <nav className="flex items-center gap-4">
              <NavLink to="/" end className={navLinkClass}>
                Portfolios
              </NavLink>
              <NavLink to="/upload" className={navLinkClass}>
                Upload
              </NavLink>
            </nav>
          </div>
          <button
            type="button"
            onClick={handleLogout}
            className="text-sm font-medium text-slate-500 hover:text-slate-900"
          >
            Log out
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  )
}
