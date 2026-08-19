import { useEffect, useMemo, useRef, useState } from "react"
import { ColorType, createChart, CrosshairMode, LineSeries, type Time } from "lightweight-charts"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { chartKeyboardIndex } from "@/lib/chart-keyboard"
import type { HistoricalValuationResponse, ValuationPoint } from "@/lib/types"

function displayValue(point: ValuationPoint) {
  if (point.value === null) return point.status === "nm" ? "NM" : "—"
  return point.unit === "%" ? `${point.value.toFixed(2)}%` : `${point.value.toFixed(2)}x`
}

export function ValuationHistoryChart({ valuation }: { valuation: HistoricalValuationResponse | null }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const availableMetrics = useMemo(() => Object.keys(valuation?.history || {}).filter((metricId) => (valuation?.history[metricId] || []).some((point) => point.value !== null)), [valuation])
  const [selectedMetric, setSelectedMetric] = useState(availableMetrics[0] || "")
  const [hoverIndex, setHoverIndex] = useState<number | null>(null)
  const [keyboardIndex, setKeyboardIndex] = useState<number | null>(null)

  useEffect(() => {
    if (!availableMetrics.includes(selectedMetric)) setSelectedMetric(availableMetrics[0] || "")
  }, [availableMetrics, selectedMetric])

  const points = useMemo(() => (valuation?.history[selectedMetric] || []).filter((point) => point.value !== null), [selectedMetric, valuation])

  useEffect(() => {
    setHoverIndex(null)
    setKeyboardIndex(null)
  }, [points])

  useEffect(() => {
    if (!containerRef.current || !points.length) return
    const chart = createChart(containerRef.current, {
      autoSize: true,
      height: 360,
      layout: { background: { type: ColorType.Solid, color: "#0b1411" }, textColor: "#789087", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace" },
      grid: { vertLines: { color: "#16221e" }, horzLines: { color: "#22302a" } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#293832" },
      timeScale: { borderColor: "#293832", rightOffset: 2 },
    })
    const series = chart.addSeries(LineSeries, { color: "#a78bfa", lineWidth: 2, priceLineVisible: false, title: points[0]?.label || selectedMetric })
    series.setData(points.map((point) => ({ time: point.valuationDate as Time, value: point.value! })))
    chart.timeScale().fitContent()
    chart.subscribeCrosshairMove((parameter) => {
      const index = points.findIndex((point) => point.valuationDate === String(parameter.time || ""))
      setHoverIndex(index >= 0 ? index : null)
      if (index >= 0) setKeyboardIndex(null)
    })
    return () => chart.remove()
  }, [points, selectedMetric])

  if (!availableMetrics.length) return <div className="grid h-64 place-items-center rounded-lg border border-dashed text-sm text-muted-foreground">Historical valuation observations are unavailable.</div>
  const selectedIndex = keyboardIndex ?? hoverIndex ?? Math.max(points.length - 1, 0)
  const selected = points[selectedIndex]
  const moveSelection = (key: string) => {
    const next = chartKeyboardIndex(key, keyboardIndex, points.length)
    if (next !== null) setKeyboardIndex(next)
    return next !== null
  }
  return <div className="overflow-hidden rounded-lg border bg-[#0b1411]">
    <div className="flex flex-wrap items-center gap-2 border-b bg-background/80 px-3 py-2">{availableMetrics.map((metricId) => <Button key={metricId} size="sm" variant={selectedMetric === metricId ? "secondary" : "ghost"} aria-pressed={selectedMetric === metricId} onClick={() => setSelectedMetric(metricId)}>{valuation?.statistics[metricId]?.label || metricId.replaceAll("_", " ")}</Button>)}<span className="ml-auto hidden text-[10px] text-muted-foreground sm:inline">Historical context · not a trading signal</span></div>
    {selected ? <div aria-hidden="true" className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b bg-background/85 px-3 py-2 font-mono text-[10px]"><Badge variant="outline">{selected.valuationDate}</Badge><span>{selected.label} {displayValue(selected)}</span><span>Price ${selected.price.toFixed(2)}</span><span className="text-muted-foreground">Fundamentals known {selected.fundamentalKnownAt ? new Date(selected.fundamentalKnownAt).toLocaleDateString() : "unavailable"}</span></div> : null}
    <div ref={containerRef} role="group" tabIndex={0} aria-label="Interactive historical valuation chart" aria-describedby="valuation-chart-help valuation-chart-current-value" aria-keyshortcuts="ArrowLeft ArrowRight Home End" className="h-[360px] w-full focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary" onKeyDown={(event) => { if (moveSelection(event.key)) event.preventDefault() }} />
    <p id="valuation-chart-help" className="sr-only">Use Left and Right Arrow to inspect adjacent valuation observations. Home selects the first observation and End selects the latest.</p>
    <p id="valuation-chart-current-value" aria-live="polite" className="sr-only">{selected ? `${selected.valuationDate}. ${selected.label} ${displayValue(selected)}.` : "No valuation observation selected."}</p>
  </div>
}
