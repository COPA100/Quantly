import { Link } from 'react-router-dom'

export default function Wordmark({ to = '/' }: { to?: string }) {
  return (
    <Link to={to} className="inline-flex items-center gap-2 text-[17px] font-medium tracking-[-0.02em] text-ink">
      <svg width="22" height="22" viewBox="0 0 32 32" aria-hidden="true">
        <rect width="32" height="32" rx="7" fill="var(--color-primary)" />
        <path
          d="M9 21.5 14 15l4 3.5 5.5-8"
          fill="none"
          stroke="white"
          strokeWidth="2.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      Quantly
    </Link>
  )
}
