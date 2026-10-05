import type { ReactNode } from 'react'

interface Props {
  title: string
  // one plain-language sentence about what the panel shows for this portfolio
  lede?: string
  children: ReactNode
  // controls that sit on the title line, e.g. a horizon toggle
  actions?: ReactNode
  // white surface for charts and tables; plain sits straight on the canvas
  surface?: boolean
  className?: string
}

export default function Panel({ title, lede, children, actions, surface = true, className = '' }: Props) {
  return (
    <section className={`min-w-0 ${className}`}>
      <div className="flex min-h-9 flex-wrap items-center justify-between gap-3">
        <h2 className="display-md text-ink">{title}</h2>
        {actions}
      </div>
      {lede && <p className="mt-1.5 max-w-[68ch] text-[15px] text-body">{lede}</p>}
      <div
        className={
          surface
            ? 'mt-4 rounded-[var(--radius-panel)] border border-hairline bg-surface'
            : 'mt-4'
        }
      >
        {children}
      </div>
    </section>
  )
}
