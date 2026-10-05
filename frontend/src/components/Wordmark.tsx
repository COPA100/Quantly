import { useId } from 'react'
import { Link } from 'react-router-dom'

// a return distribution with its loss tail shaded: the thing quantly measures
export function LogoMark({ size = 30 }: { size?: number }) {
  const clip = useId()
  const curve = 'M2 25 C8 25 10.5 7 16 7 C21.5 7 24 25 30 25'
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <defs>
        <clipPath id={clip}>
          <rect x="0" y="0" width="12" height="32" />
        </clipPath>
      </defs>
      <path d={`${curve} Z`} fill="var(--color-primary)" clipPath={`url(#${clip})`} />
      <path d={curve} fill="none" stroke="var(--color-ink)" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M2 25 H30" stroke="var(--color-ink)" strokeWidth="2.6" strokeLinecap="round" />
    </svg>
  )
}

export default function Wordmark({ to = '/' }: { to?: string }) {
  return (
    <Link to={to} aria-label="Quantly home" className="inline-flex items-center gap-2 text-ink">
      <LogoMark />
      <span className="text-[20px] font-medium leading-none tracking-[-0.035em]">quantly</span>
    </Link>
  )
}
