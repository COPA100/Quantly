import { AreaSeries, createChart, type Time } from 'lightweight-charts'
import { useEffect, useRef } from 'react'

interface Props {
  dates: string[]
  values: number[]
  height?: number
}

export default function EquityChart({ dates, values, height = 340 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return

    const chart = createChart(el, {
      height,
      autoSize: true,
      layout: {
        background: { color: 'transparent' },
        textColor: '#807d72',
        fontFamily: "'JetBrains Mono', ui-monospace, monospace",
        fontSize: 11,
        attributionLogo: false,
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: '#efeee8' },
      },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderColor: '#e6e5e0' },
      // compact dollars on the axis, full dollars on the crosshair label
      localization: {
        priceFormatter: (v: number) =>
          v >= 1e6 ? `$${(v / 1e6).toFixed(2)}M` : `$${Math.round(v / 1e3).toLocaleString()}k`,
      },
      crosshair: {
        vertLine: { color: '#cfcdc4', labelBackgroundColor: '#26251e' },
        horzLine: { color: '#cfcdc4', labelBackgroundColor: '#26251e' },
      },
    })

    const series = chart.addSeries(AreaSeries, {
      lineColor: '#26251e',
      topColor: 'rgba(38, 37, 30, 0.10)',
      bottomColor: 'rgba(38, 37, 30, 0)',
      lineWidth: 2,
      priceLineVisible: false,
    })
    series.setData(dates.map((time, i) => ({ time: time as Time, value: values[i] })))
    chart.timeScale().fitContent()

    return () => chart.remove()
  }, [dates, values, height])

  return <div ref={containerRef} className="w-full" />
}
