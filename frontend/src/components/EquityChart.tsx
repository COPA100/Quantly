import { AreaSeries, createChart, type Time } from 'lightweight-charts'
import { useEffect, useRef } from 'react'

interface Props {
  dates: string[]
  values: number[]
}

export default function EquityChart({ dates, values }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const chart = createChart(el, {
      height: 280,
      autoSize: true,
      layout: {
        background: { color: 'transparent' },
        textColor: '#64748b',
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: '#f1f5f9' },
        horzLines: { color: '#f1f5f9' },
      },
      rightPriceScale: { borderColor: '#e2e8f0' },
      timeScale: { borderColor: '#e2e8f0' },
    })

    const series = chart.addSeries(AreaSeries, {
      lineColor: '#6366f1',
      topColor: 'rgba(99, 102, 241, 0.3)',
      bottomColor: 'rgba(99, 102, 241, 0.02)',
      lineWidth: 2,
      priceLineVisible: false,
    })
    series.setData(dates.map((time, i) => ({ time: time as Time, value: values[i] })))
    chart.timeScale().fitContent()

    return () => chart.remove()
  }, [dates, values])

  return <div ref={containerRef} className="w-full" />
}
