import { formatPercent } from '../lib/format'
import type { Tone } from '../lib/tone'
import type { Analytics } from '../lib/types'
import InsightCard from './InsightCard'
import Section from './Section'

interface Card {
  title: string
  value: string
  tone?: Tone
  description?: string
}

function buildCards(analytics: Analytics): Card[] {
  const insights = analytics.insights ?? {}
  const cards: Card[] = []

  if (analytics.returns) {
    const annual = analytics.returns.annualized
    cards.push({
      title: 'Annualized return',
      value: formatPercent(annual),
      tone: annual >= 0 ? 'positive' : 'negative',
    })
  }
  if (analytics.volatility) {
    cards.push({
      title: 'Volatility',
      value: formatPercent(analytics.volatility.annualized),
      description: insights.volatility,
    })
  }
  if (analytics.sharpe) {
    cards.push({
      title: 'Sharpe ratio',
      value: analytics.sharpe.ratio.toFixed(2),
      description: insights.sharpe,
    })
  }
  if (analytics.sortino) {
    cards.push({
      title: 'Sortino ratio',
      value: analytics.sortino.ratio.toFixed(2),
      description: insights.sortino,
    })
  }
  if (analytics.drawdown) {
    cards.push({
      title: 'Max drawdown',
      value: formatPercent(analytics.drawdown.max_drawdown),
      tone: 'negative',
      description: insights.drawdown,
    })
  }
  if (analytics.beta) {
    cards.push({
      title: 'Beta',
      value: analytics.beta.beta.toFixed(2),
      description: insights.beta,
    })
  }
  if (analytics.var) {
    const { var: value, cvar, horizon_days, confidence } = analytics.var
    const pct = Math.round(confidence * 100)
    cards.push({
      title: `Value at risk (${horizon_days}d, ${pct}%)`,
      value: formatPercent(value),
      tone: 'negative',
      description:
        `Over ~${horizon_days} trading days you would not expect to lose more than this ` +
        `${pct}% of the time. Average loss beyond it is ${formatPercent(cvar)}.`,
    })
  }
  return cards
}

export default function RiskInsights({ analytics }: { analytics: Analytics }) {
  const cards = buildCards(analytics)
  if (cards.length === 0) return null

  return (
    <Section title="Risk & performance">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map((card) => (
          <InsightCard key={card.title} {...card} />
        ))}
      </div>
    </Section>
  )
}
