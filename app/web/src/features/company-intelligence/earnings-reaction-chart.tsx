import { useEffect, useMemo, useRef, useState } from "react"
import {
  ColorType,
  createChart,
  createSeriesMarkers,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
  type Time,
} from "lightweight-charts"

import { Badge } from "@/components/ui/badge"
import { chartKeyboardIndex } from "@/lib/chart-keyboard"
import type { EarningsEventAnalysis, EarningsReactionPathPoint } from "@/lib/types"

function percent(value: number | null) {
  return value === null ? "—" : `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`
}

export function EarningsReactionChart({ analysis }: { analysis: EarningsEventAnalysis }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [hoverIndex, setHoverIndex] = useState<number | null>(null)
  const [keyboardIndex, setKeyboardIndex] = useState<number | null>(null)
  const points = analysis.reaction.path
  const anchorIndex = useMemo(
    () => Math.max(points.findIndex((point) => point.relativeSession === 0), 0),
    [points],
  )

  useEffect(() => {
    setHoverIndex(null)
    setKeyboardIndex(null)
  }, [analysis.event.eventId])

  useEffect(() => {
    if (!containerRef.current || !points.length) return
    const chart = createChart(containerRef.current, {
      autoSize: true,
      height: 510,
      layout: {
        background: { type: ColorType.Solid, color: "#0b1411" },
        textColor: "#789087",
        fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
      },
      grid: { vertLines: { color: "#16221e" }, horzLines: { color: "#22302a" } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#293832" },
      timeScale: { borderColor: "#293832", rightOffset: 2 },
    })
    const price = chart.addSeries(LineSeries, {
      title: analysis.event.ticker,
      color: "#b6f559",
      lineWidth: 2,
      priceLineVisible: false,
    }, 0)
    price.setData(points.map((point) => ({ time: point.sessionDate as Time, value: point.close })))
    if (analysis.reaction.anchorSession) {
      createSeriesMarkers(price, [{
        time: analysis.reaction.anchorSession as Time,
        position: "belowBar",
        color: "#f8bd5e",
        shape: "arrowUp",
        text: "Earnings Anchor",
      }])
    }
    const volume = chart.addSeries(HistogramSeries, {
      title: "Volume",
      color: "#64d5c766",
      priceFormat: { type: "volume" },
      priceLineVisible: false,
      lastValueVisible: false,
    }, 1)
    volume.setData(points.filter((point) => point.volume !== null).map((point) => ({
      time: point.sessionDate as Time,
      value: point.volume || 0,
      color: point.relativeSession === 0 ? "#f8bd5e" : "#64d5c766",
    })))
    const reaction = chart.addSeries(LineSeries, {
      title: "Stock Reaction",
      color: "#64d5c7",
      lineWidth: 2,
      priceLineVisible: false,
      priceFormat: { type: "custom", formatter: (value: number) => `${value.toFixed(1)}%` },
    }, 2)
    reaction.setData(points.map((point) => ({ time: point.sessionDate as Time, value: point.cumulativeReturn })))
    const adjusted = chart.addSeries(LineSeries, {
      title: `${analysis.reaction.benchmarkTicker}-Adjusted`,
      color: "#a78bfa",
      lineWidth: 2,
      priceLineVisible: false,
      priceFormat: { type: "custom", formatter: (value: number) => `${value.toFixed(1)}%` },
    }, 2)
    adjusted.setData(points.filter((point) => point.benchmarkAdjustedReturn !== null).map((point) => ({
      time: point.sessionDate as Time,
      value: point.benchmarkAdjustedReturn || 0,
    })))
    chart.panes()[0]?.setHeight(300)
    chart.panes()[1]?.setHeight(70)
    chart.panes()[2]?.setHeight(120)
    chart.timeScale().fitContent()
    chart.subscribeCrosshairMove((parameter) => {
      const index = points.findIndex((point) => point.sessionDate === String(parameter.time || ""))
      setHoverIndex(index >= 0 ? index : null)
      if (index >= 0) setKeyboardIndex(null)
    })
    return () => chart.remove()
  }, [analysis.event.ticker, analysis.reaction.anchorSession, analysis.reaction.benchmarkTicker, points])

  if (!points.length) return <div className="grid h-80 place-items-center px-6 text-center text-sm text-muted-foreground">Reaction chart unavailable because the event lacks sufficient aligned price history.</div>
  const selectedIndex = keyboardIndex ?? hoverIndex ?? anchorIndex
  const selected: EarningsReactionPathPoint = points[selectedIndex] || points[anchorIndex]
  const moveSelection = (key: string) => {
    const next = chartKeyboardIndex(key, keyboardIndex ?? anchorIndex, points.length)
    if (next !== null) setKeyboardIndex(next)
    return next !== null
  }
  return <div className="overflow-hidden rounded-lg border bg-[#0b1411]">
    <div aria-hidden="true" className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b bg-background/85 px-3 py-2 font-mono text-[10px]">
      <Badge variant="outline">{selected.sessionDate}</Badge>
      <span>{analysis.event.ticker} ${selected.close.toFixed(2)}</span>
      <span className="text-chart-2">Reaction {percent(selected.cumulativeReturn)}</span>
      <span className="text-chart-4">Adjusted {percent(selected.benchmarkAdjustedReturn)}</span>
      <span className="text-muted-foreground">Session {selected.relativeSession >= 0 ? "+" : ""}{selected.relativeSession}</span>
    </div>
    <div
      ref={containerRef}
      role="group"
      tabIndex={0}
      aria-label={`${analysis.event.ticker} price, volume, and earnings reaction chart`}
      aria-describedby="earnings-chart-help earnings-chart-current-value"
      aria-keyshortcuts="ArrowLeft ArrowRight Home End"
      className="h-[510px] w-full focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary"
      onKeyDown={(event) => { if (moveSelection(event.key)) event.preventDefault() }}
    />
    <p id="earnings-chart-help" className="sr-only">Use Left and Right Arrow to inspect adjacent trading sessions. Home selects the first session and End selects the last.</p>
    <p id="earnings-chart-current-value" aria-live="polite" className="sr-only">{selected.sessionDate}. Close ${selected.close.toFixed(2)}. Stock reaction {percent(selected.cumulativeReturn)}. Benchmark-adjusted reaction {percent(selected.benchmarkAdjustedReturn)}.</p>
  </div>
}
