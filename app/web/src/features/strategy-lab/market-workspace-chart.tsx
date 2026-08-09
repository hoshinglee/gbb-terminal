import { useEffect, useMemo, useRef, useState } from "react"
import {
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  CrosshairMode,
  HistogramSeries,
  LineStyle,
  LineSeries,
  type CandlestickData,
  type SeriesMarker,
  type Time,
} from "lightweight-charts"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { chartKeyboardIndex } from "@/lib/chart-keyboard"
import { darvasPriceOverlays, enrichPricePoints, fibonacciPriceOverlay, strategyPriceOverlays } from "@/lib/indicators"
import type { MarketChartPayload, MarketChartPoint, ParameterValue, PricePoint, StrategyTemplate, Trade } from "@/lib/types"

interface MarketWorkspaceChartProps {
  points: Array<PricePoint | MarketChartPoint>
  marketChart?: MarketChartPayload | null
  trades?: Trade[]
  template?: StrategyTemplate
  parameterValues?: Record<string, ParameterValue>
  loading?: boolean
  symbol?: string
}

type OverlayKey = "rule" | "sma" | "ema" | "bollinger" | "darvas" | "fibonacci"

const intervalLabels: Record<string, string> = { day: "Day", week: "Week", month: "Month", year: "Year" }
const EMPTY_TRADES: Trade[] = []
const EMPTY_PARAMETER_VALUES: Record<string, ParameterValue> = {}

export function MarketWorkspaceChart({ points, marketChart, trades = EMPTY_TRADES, template, parameterValues = EMPTY_PARAMETER_VALUES, loading, symbol }: MarketWorkspaceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [interval, setInterval] = useState(marketChart?.defaultInterval || "day")
  const [activeOverlays, setActiveOverlays] = useState<OverlayKey[]>(["rule"])
  const selectedPoints = marketChart?.intervals[interval] || points
  const enriched = useMemo(() => selectedPoints.length && "periodStart" in selectedPoints[0] ? selectedPoints as MarketChartPoint[] : enrichPricePoints(selectedPoints as PricePoint[]), [selectedPoints])
  const ruleOverlays = useMemo(() => strategyPriceOverlays(enriched, template, parameterValues), [enriched, template, parameterValues])
  const overlays = useMemo(() => {
    const selected = activeOverlays.flatMap((overlay) => {
      if (overlay === "rule") return ruleOverlays
      if (overlay === "sma") return [{ label: "SMA 20", color: "#64d5c7", values: enriched.map((point) => point.indicators.sma20 ?? null) }]
      if (overlay === "ema") return [{ label: "EMA 20", color: "#f8bd5e", values: enriched.map((point) => point.indicators.ema20 ?? null) }]
      if (overlay === "bollinger") return [
        { label: "Bollinger Mid", color: "#8ba097", values: enriched.map((point) => point.indicators.bollingerMiddle20 ?? null) },
        { label: "Bollinger Upper", color: "#a78bfa", values: enriched.map((point) => point.indicators.bollingerUpper20 ?? null) },
        { label: "Bollinger Lower", color: "#a78bfa", values: enriched.map((point) => point.indicators.bollingerLower20 ?? null) },
      ]
      if (overlay === "darvas") return darvasPriceOverlays(enriched)
      return [fibonacciPriceOverlay(enriched)]
    })
    return [...new Map(selected.map((overlay) => [overlay.label, overlay])).values()]
  }, [activeOverlays, enriched, ruleOverlays])
  const [hover, setHover] = useState<{ candle: CandlestickData<Time>; point?: MarketChartPoint } | null>(null)
  const [keyboardIndex, setKeyboardIndex] = useState<number | null>(null)

  useEffect(() => {
    setInterval(marketChart?.defaultInterval || "day")
    setHover(null)
    setKeyboardIndex(null)
  }, [marketChart])

  useEffect(() => {
    setHover(null)
    setKeyboardIndex(null)
  }, [enriched])

  useEffect(() => {
    if (!containerRef.current || !enriched.length) return
    const chart = createChart(containerRef.current, {
      autoSize: true,
      height: 620,
      layout: { background: { type: ColorType.Solid, color: "#0b1411" }, textColor: "#789087", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace" },
      grid: { vertLines: { color: "#16221e" }, horzLines: { color: "#22302a" } },
      crosshair: { mode: CrosshairMode.Normal, vertLine: { color: "#8ba097", labelBackgroundColor: "#263a32" }, horzLine: { color: "#8ba097", labelBackgroundColor: "#263a32" } },
      rightPriceScale: { borderColor: "#293832" },
      timeScale: { borderColor: "#293832", timeVisible: false, rightOffset: 3 },
    })
    const candles = chart.addSeries(CandlestickSeries, { upColor: "#b6f559", downColor: "#ff6a6a", borderVisible: false, wickUpColor: "#b6f559", wickDownColor: "#ff6a6a" }, 0)
    candles.setData(enriched.map((point) => ({ time: point.date as Time, open: point.open, high: point.high, low: point.low, close: point.close })))
    overlays.forEach((overlay) => {
      const line = chart.addSeries(LineSeries, { color: overlay.color, lineWidth: 2, priceLineVisible: false, lastValueVisible: true, title: overlay.label }, 0)
      line.setData(enriched.flatMap((point, index) => overlay.values[index] === null ? [] : [{ time: point.date as Time, value: overlay.values[index]! }]))
    })
    const volume = chart.addSeries(HistogramSeries, { priceFormat: { type: "volume" }, priceLineVisible: false, lastValueVisible: false }, 1)
    volume.setData(enriched.map((point) => ({ time: point.date as Time, value: point.volume, color: point.close >= point.open ? "#b6f55970" : "#ff6a6a70" })))
    const volumeAverage = chart.addSeries(LineSeries, { color: "#64d5c7", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, title: "Volume Avg 20" }, 1)
    volumeAverage.setData(enriched.flatMap((point) => point.indicators.volumeSma20 === undefined ? [] : [{ time: point.date as Time, value: point.indicators.volumeSma20 }]))
    const rsi = chart.addSeries(LineSeries, { color: "#64d5c7", lineWidth: 2, priceLineVisible: false, title: "RSI 14" }, 2)
    rsi.setData(enriched.flatMap((point) => point.indicators.rsi14 === undefined ? [] : [{ time: point.date as Time, value: point.indicators.rsi14 }]))
    rsi.createPriceLine({ price: 70, color: "#f8bd5e88", lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: "70" })
    rsi.createPriceLine({ price: 30, color: "#f8bd5e88", lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: "30" })
    const macdHistogram = chart.addSeries(HistogramSeries, { priceLineVisible: false, lastValueVisible: false }, 3)
    macdHistogram.setData(enriched.flatMap((point) => point.indicators.macdHistogram === undefined ? [] : [{ time: point.date as Time, value: point.indicators.macdHistogram, color: point.indicators.macdHistogram >= 0 ? "#b6f55970" : "#ff6a6a70" }]))
    const macd = chart.addSeries(LineSeries, { color: "#f8bd5e", lineWidth: 2, priceLineVisible: false, title: "MACD" }, 3)
    macd.setData(enriched.flatMap((point) => point.indicators.macd === undefined ? [] : [{ time: point.date as Time, value: point.indicators.macd }]))
    const signal = chart.addSeries(LineSeries, { color: "#a78bfa", lineWidth: 1, priceLineVisible: false, title: "Signal" }, 3)
    signal.setData(enriched.flatMap((point) => point.indicators.macdSignal === undefined ? [] : [{ time: point.date as Time, value: point.indicators.macdSignal }]))
    const markerDate = (date: string) => enriched.find((point) => date >= point.periodStart && date <= point.periodEnd)?.date
    const markers: SeriesMarker<Time>[] = []
    trades.forEach((trade) => {
      const entryDate = markerDate(trade.entryDate)
      if (entryDate) markers.push({ time: entryDate as Time, position: "belowBar", color: "#64d5c7", shape: "arrowUp", text: `${trade.side} entry` })
      const exitDate = trade.exitDate ? markerDate(trade.exitDate) : undefined
      if (trade.status === "Closed" && exitDate) markers.push({ time: exitDate as Time, position: "aboveBar", color: "#f8bd5e", shape: "arrowDown", text: "Exit" })
    })
    createSeriesMarkers(candles, markers.sort((left, right) => String(left.time).localeCompare(String(right.time))))
    chart.panes()[0]?.setHeight(350)
    chart.panes()[1]?.setHeight(90)
    chart.panes()[2]?.setHeight(80)
    chart.panes()[3]?.setHeight(100)
    chart.timeScale().fitContent()
    chart.subscribeCrosshairMove((parameter) => {
      const candle = parameter.seriesData.get(candles)
      const date = parameter.time ? String(parameter.time) : ""
      setKeyboardIndex(null)
      setHover(candle && "open" in candle ? { candle: candle as CandlestickData<Time>, point: enriched.find((point) => point.date === date) } : null)
    })
    return () => chart.remove()
  }, [enriched, overlays, trades])

  if (loading) return <Skeleton className="h-[620px] w-full rounded-none" />
  if (!enriched.length) return <div className="grid h-[620px] place-items-center bg-[#0b1411] text-sm text-muted-foreground">Select a ticker to load the persistent market preview.</div>
  const keyboardPoint = keyboardIndex === null ? null : enriched[keyboardIndex]
  const latestPoint = keyboardPoint || hover?.point || enriched.at(-1)!
  const latest = keyboardPoint ? { open: keyboardPoint.open, high: keyboardPoint.high, low: keyboardPoint.low, close: keyboardPoint.close } : hover?.candle || { open: latestPoint.open, high: latestPoint.high, low: latestPoint.low, close: latestPoint.close }
  const toggleOverlay = (overlay: OverlayKey) => setActiveOverlays((selected) => selected.includes(overlay) ? selected.filter((item) => item !== overlay) : [...selected, overlay])
  const selectWithKeyboard = (key: string) => {
    const next = chartKeyboardIndex(key, keyboardIndex, enriched.length)
    if (next !== null) setKeyboardIndex(next)
    return next !== null
  }
  return (
    <div className="relative bg-[#0b1411]">
      <div className="flex flex-wrap items-center gap-2 border-b bg-background/80 px-3 py-2">
        {marketChart && Object.keys(marketChart.intervals).map((key) => <Button key={key} size="sm" variant={interval === key ? "secondary" : "ghost"} aria-pressed={interval === key} onClick={() => { setInterval(key); setKeyboardIndex(null); setHover(null) }}>{intervalLabels[key] || key}</Button>)}
        <span className="mx-1 h-5 w-px bg-border" />
        {(["rule", "sma", "ema", "bollinger", "darvas", "fibonacci"] as OverlayKey[]).map((overlay) => <Button key={overlay} size="sm" variant={activeOverlays.includes(overlay) ? "secondary" : "ghost"} aria-pressed={activeOverlays.includes(overlay)} onClick={() => toggleOverlay(overlay)}>{overlay === "rule" ? "Strategy Rule" : overlay === "bollinger" ? "Boll" : overlay === "fibonacci" ? "Fib" : overlay === "darvas" ? "Darvas" : overlay.toUpperCase()}</Button>)}
        <span className="ml-auto hidden text-[10px] text-muted-foreground sm:inline">Focus chart · ←/→ inspect dates</span>
      </div>
      <div aria-hidden="true" className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b bg-background/85 px-3 py-2 font-mono text-[10px]">
        <Badge variant="outline" className="border-primary/30 text-primary">{symbol?.trim().toUpperCase() || "NVDA"}</Badge>
        <span>{latestPoint.periodStart === latestPoint.periodEnd ? latestPoint.periodEnd : `${latestPoint.periodStart}–${latestPoint.periodEnd}`}</span>
        <span>O {latest.open.toFixed(2)}</span><span>H {latest.high.toFixed(2)}</span><span>L {latest.low.toFixed(2)}</span><span>C {latest.close.toFixed(2)}</span>
        <span>V {Intl.NumberFormat("en", { notation: "compact" }).format(latestPoint.volume)}</span>
        {latestPoint.position !== undefined && <span>Position {latestPoint.position}</span>}
        {latestPoint.indicators.rsi14 !== undefined && <span>RSI {latestPoint.indicators.rsi14.toFixed(1)}</span>}
        {overlays.map((overlay) => <span key={overlay.label} style={{ color: overlay.color }}>{overlay.label}</span>)}
      </div>
      <div
        ref={containerRef}
        role="group"
        tabIndex={0}
        aria-label={`Interactive ${symbol?.trim().toUpperCase() || "NVDA"} candlestick, volume, RSI, and MACD chart`}
        aria-describedby="market-chart-keyboard-help market-chart-current-value"
        aria-keyshortcuts="ArrowLeft ArrowRight Home End"
        className="h-[620px] w-full focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary"
        onKeyDown={(event) => { if (selectWithKeyboard(event.key)) event.preventDefault() }}
      />
      <p id="market-chart-keyboard-help" className="sr-only">Use Left and Right Arrow to inspect adjacent bars. Home selects the first bar and End selects the latest bar.</p>
      <p id="market-chart-current-value" aria-live="polite" className="sr-only">{latestPoint.periodStart === latestPoint.periodEnd ? latestPoint.periodEnd : `${latestPoint.periodStart} to ${latestPoint.periodEnd}`}. Open {latest.open.toFixed(2)}, high {latest.high.toFixed(2)}, low {latest.low.toFixed(2)}, close {latest.close.toFixed(2)}, volume {latestPoint.volume}.</p>
    </div>
  )
}
