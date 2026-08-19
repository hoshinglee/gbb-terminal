import { useEffect, useMemo, useRef, useState } from "react"
import {
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  CrosshairMode,
  HistogramSeries,
  type CandlestickData,
  type Time,
} from "lightweight-charts"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { chartKeyboardIndex } from "@/lib/chart-keyboard"
import type { EarningsEventAnalysis, MarketChartPayload, MarketChartPoint } from "@/lib/types"

export type EventMarketPeriod = "3y" | "5y"

function compactVolume(value: number) {
  return Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(value)
}

export function EarningsReactionChart({
  analysis,
  marketChart,
  period,
  onPeriodChange,
  loading = false,
}: {
  analysis: EarningsEventAnalysis
  marketChart: MarketChartPayload | null
  period: EventMarketPeriod
  onPeriodChange: (period: EventMarketPeriod) => void
  loading?: boolean
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [hover, setHover] = useState<{ candle: CandlestickData<Time>; point: MarketChartPoint } | null>(null)
  const [keyboardIndex, setKeyboardIndex] = useState<number | null>(null)
  const points = useMemo(() => marketChart?.intervals.day || [], [marketChart])
  const anchorIndex = useMemo(
    () => analysis.reaction.anchorSession
      ? points.findIndex((point) => analysis.reaction.anchorSession! >= point.periodStart && analysis.reaction.anchorSession! <= point.periodEnd)
      : -1,
    [analysis.reaction.anchorSession, points],
  )

  useEffect(() => {
    setHover(null)
    setKeyboardIndex(null)
  }, [analysis.event.eventId, points])

  useEffect(() => {
    if (!containerRef.current || !points.length) return
    const chart = createChart(containerRef.current, {
      autoSize: true,
      height: 500,
      layout: { background: { type: ColorType.Solid, color: "#0b1411" }, textColor: "#789087", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace" },
      grid: { vertLines: { color: "#16221e" }, horzLines: { color: "#22302a" } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#293832" },
      timeScale: { borderColor: "#293832", rightOffset: 3 },
    })
    const candles = chart.addSeries(CandlestickSeries, { upColor: "#b6f559", downColor: "#ff6a6a", borderVisible: false, wickUpColor: "#b6f559", wickDownColor: "#ff6a6a" }, 0)
    candles.setData(points.map((point) => ({ time: point.date as Time, open: point.open, high: point.high, low: point.low, close: point.close })))
    const volume = chart.addSeries(HistogramSeries, { priceFormat: { type: "volume" }, priceLineVisible: false, lastValueVisible: false }, 1)
    volume.setData(points.map((point) => ({ time: point.date as Time, value: point.volume, color: point.close >= point.open ? "#b6f55970" : "#ff6a6a70" })))
    if (anchorIndex >= 0) {
      createSeriesMarkers(candles, [{
        time: points[anchorIndex].date as Time,
        position: "aboveBar",
        color: "#f8bd5e",
        shape: "arrowDown",
        text: `${analysis.event.fiscalPeriod || "FY"} ${analysis.event.fiscalYear || ""} earnings`,
      }])
    }
    chart.panes()[0]?.setHeight(410)
    chart.panes()[1]?.setHeight(90)
    chart.timeScale().fitContent()
    if (anchorIndex >= 0) {
      chart.timeScale().setVisibleLogicalRange({ from: Math.max(anchorIndex - 70, 0), to: Math.min(anchorIndex + 40, points.length - 1) })
    }
    chart.subscribeCrosshairMove((parameter) => {
      const candle = parameter.seriesData.get(candles)
      const date = parameter.time ? String(parameter.time) : ""
      const point = points.find((candidate) => candidate.date === date)
      setKeyboardIndex(null)
      setHover(candle && point && "open" in candle ? { candle: candle as CandlestickData<Time>, point } : null)
    })
    return () => chart.remove()
  }, [analysis.event.fiscalPeriod, analysis.event.fiscalYear, analysis.event.eventId, anchorIndex, points])

  if (loading) return <Skeleton className="h-[560px] w-full" />
  if (!points.length) return <div className="grid h-72 place-items-center rounded-lg border border-dashed px-6 text-center text-sm text-muted-foreground">Market history is unavailable. Reported facts and event reaction calculations remain available above.</div>
  const selectedIndex = keyboardIndex ?? (hover ? points.indexOf(hover.point) : anchorIndex >= 0 ? anchorIndex : points.length - 1)
  const selectedPoint = points[Math.max(selectedIndex, 0)] || points.at(-1)!
  const selectedCandle = keyboardIndex !== null ? selectedPoint : hover?.candle || selectedPoint
  const moveSelection = (key: string) => {
    const next = chartKeyboardIndex(key, keyboardIndex ?? (anchorIndex >= 0 ? anchorIndex : null), points.length)
    if (next !== null) setKeyboardIndex(next)
    return next !== null
  }
  return <div className="overflow-hidden rounded-lg border bg-[#0b1411]">
    <div className="flex flex-wrap items-center gap-2 border-b bg-background/80 px-3 py-2"><span className="font-mono text-[9px] uppercase tracking-[0.14em] text-muted-foreground">Event Market Window</span><Button size="sm" variant={period === "3y" ? "secondary" : "ghost"} aria-pressed={period === "3y"} onClick={() => onPeriodChange("3y")}>3 Years</Button><Button size="sm" variant={period === "5y" ? "secondary" : "ghost"} aria-pressed={period === "5y"} onClick={() => onPeriodChange("5y")}>5 Years</Button><span className="ml-auto text-[10px] text-muted-foreground">Selected event is marked and centered when market history covers it.</span></div>
    <div aria-hidden="true" className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b bg-background/85 px-3 py-2 font-mono text-[10px]"><Badge variant="outline" className="border-primary/30 text-primary">{analysis.event.ticker}</Badge><span>{selectedPoint.date}</span><span>O {selectedCandle.open.toFixed(2)}</span><span>H {selectedCandle.high.toFixed(2)}</span><span>L {selectedCandle.low.toFixed(2)}</span><span>C {selectedCandle.close.toFixed(2)}</span><span>V {compactVolume(selectedPoint.volume)}</span>{anchorIndex < 0 ? <span className="text-chart-3">Selected event is outside this market window</span> : selectedPoint.date === points[anchorIndex].date ? <span className="text-chart-3">Earnings event</span> : null}</div>
    <div ref={containerRef} role="group" tabIndex={0} aria-label={`${analysis.event.ticker} candlestick and volume chart focused on the selected earnings event`} aria-describedby="earnings-chart-help earnings-chart-current-value" aria-keyshortcuts="ArrowLeft ArrowRight Home End" className="h-[500px] w-full focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary" onKeyDown={(event) => { if (moveSelection(event.key)) event.preventDefault() }} />
    <p id="earnings-chart-help" className="sr-only">Use Left and Right Arrow to inspect adjacent trading sessions. Home selects the first session and End selects the latest.</p>
    <p id="earnings-chart-current-value" aria-live="polite" className="sr-only">{selectedPoint.date}. Open {selectedCandle.open.toFixed(2)}, high {selectedCandle.high.toFixed(2)}, low {selectedCandle.low.toFixed(2)}, close {selectedCandle.close.toFixed(2)}, volume {selectedPoint.volume}.</p>
  </div>
}
