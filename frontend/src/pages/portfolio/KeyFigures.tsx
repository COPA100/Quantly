import { formatCurrencyShort, formatPercent, formatSigned } from '../../lib/format'
import { toneOf, toneTextColor } from '../../lib/tone'
import type { Analytics } from '../../lib/types'

interface Figure {
  label: string
  value: string
  sub?: string
  tone?: ReturnType<typeof toneOf>
}

function figures(a: Analytics): Figure[] {
  const out: Figure[] = []
  if (a.value) out.push({ label: 'Market value', value: formatCurrencyShort(a.value.total) })
  if (a.gain_loss) {
    const { gain_loss, gain_loss_pct } = a.gain_loss
    out.push({
      label: 'Total gain',
      value: formatSigned(formatCurrencyShort(gain_loss), gain_loss),
      sub: formatSigned(`${gain_loss_pct.toFixed(1)}%`, gain_loss_pct),
      tone: toneOf(gain_loss),
    })
  }
  if (a.returns) {
    out.push({
      label: 'Return a year',
      value: formatSigned(formatPercent(a.returns.annualized), a.returns.annualized),
      tone: toneOf(a.returns.annualized),
    })
  }
  if (a.volatility) out.push({ label: 'Volatility', value: formatPercent(a.volatility.annualized) })
  if (a.sharpe) out.push({ label: 'Sharpe ratio', value: a.sharpe.ratio.toFixed(2) })
  if (a.drawdown) {
    out.push({
      label: 'Worst drop',
      value: formatPercent(a.drawdown.max_drawdown),
      tone: 'negative',
    })
  }
  if (a.beta) out.push({ label: 'Beta to S&P 500', value: a.beta.beta.toFixed(2) })
  return out
}

export default function KeyFigures({ analytics }: { analytics: Analytics }) {
  const items = figures(analytics)
  if (items.length === 0) return null
  return (
    <dl className="grid grid-cols-2 border-y border-hairline sm:grid-cols-4 lg:grid-cols-7">
      {items.map((f, i) => (
        <div
          key={f.label}
          className={`py-5 pr-4 ${i > 0 ? 'lg:border-l lg:border-hairline lg:pl-5' : ''}`}
        >
          <dt className="text-[13px] text-muted">{f.label}</dt>
          <dd className={`num mt-1.5 text-[22px] leading-none ${toneTextColor[f.tone ?? 'neutral']}`}>
            {f.value}
          </dd>
          {f.sub && (
            <dd className={`num mt-1 text-[12px] ${toneTextColor[f.tone ?? 'neutral']}`}>{f.sub}</dd>
          )}
        </div>
      ))}
    </dl>
  )
}
