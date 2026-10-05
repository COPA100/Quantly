import type { ReactNode } from 'react'
import Wordmark from './Wordmark'

interface Props {
  title: string
  subtitle?: string
  children: ReactNode
  footer?: ReactNode
}

const QUESTIONS = [
  'How much could this portfolio fall in a bad month?',
  'Am I paid for the risk I am taking?',
  'Do my holdings actually diversify each other?',
  'What would 2008 have done to it?',
]

export default function AuthLayout({ title, subtitle, children, footer }: Props) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <aside className="hidden flex-col justify-between border-r border-hairline px-12 py-10 lg:flex">
        <Wordmark to="/login" />
        <div>
          <p className="display-xl max-w-[18ch] text-ink">
            The analysis your brokerage screen leaves out.
          </p>
          <ul className="mt-10 max-w-md border-t border-hairline">
            {QUESTIONS.map((q) => (
              <li key={q} className="border-b border-hairline py-3 text-body">
                {q}
              </li>
            ))}
          </ul>
        </div>
        <p className="text-sm text-muted">Upload a positions export. Results in about a minute.</p>
      </aside>

      <div className="flex flex-col px-5 py-10 sm:px-12">
        <div className="lg:hidden">
          <Wordmark to="/login" />
        </div>
        <div className="flex flex-1 items-center justify-center py-12">
          <div className="w-full max-w-sm">
            <h1 className="display-lg text-ink">{title}</h1>
            {subtitle && <p className="mt-2 text-body">{subtitle}</p>}
            <div className="mt-8">{children}</div>
            {footer && <div className="mt-8 text-sm text-muted">{footer}</div>}
          </div>
        </div>
      </div>
    </div>
  )
}
