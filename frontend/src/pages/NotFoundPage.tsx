import { Link } from 'react-router-dom'
import { buttonVariants } from '../lib/ui'

export default function NotFoundPage() {
  return (
    <div className="max-w-xl">
      <h1 className="display-xl text-ink">This page does not exist</h1>
      <p className="mt-3 text-body">The link may be out of date, or the portfolio was removed.</p>
      <Link to="/" className={`${buttonVariants.secondary} mt-8`}>
        Back to portfolios
      </Link>
    </div>
  )
}
