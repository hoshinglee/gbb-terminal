import { useEffect, useMemo, useRef, useState } from "react"
import {
  AreaSeries,
  ColorType,
  createChart,
  CrosshairMode,
  LineSeries,
  type Time,
} from "lightweight-charts"

import { Badge } from "@/components/ui/badge"
import { chartKeyboardIndex } from "@/lib/chart-keyboard"
import type { EquityPoint } from "@/lib/types"

interface HoverValues {
  date: string
  strategy: number
  buyHold: number
  spy: number
  drawdown: number
}

function percentFromEquity(value: number) {
  return `${((value - 1) * 100).toFixed(2)}%`
}

function drawdowns(points: EquityPoint[]) {
  let peak = 0
  return points.map((point) => {
    peak = Math.max(peak, point.strategy)
    return peak > 0 ? (point.strategy / peak - 1) * 100 : 0
  })
}

export function EquityDrawdownChart({ points }: { points: EquityPoint[] }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const strategyDrawdowns = useMemo(() => drawdowns(points), [points])
  const [hover, setHover] = useState<HoverValues | null>(null)
  const [keyboardIndex, setKeyboardIndex] = useState<number | null>(null)

  useEffect(() => {
    setHover(null)
    setKeyboardIndex(null)
  }, [points])

  useEffect(() => {
    if (!containerRef.current || !points.length) return
    const chart = createChart(containerRef.current, {
      autoSize: true,
      height: 440,
      layout: {
        background: { type: ColorType.Solid, color: "#0b1411" },
        textColor: "#789087",
        fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
      },
      grid: { vertLines: { color: "#16221e" }, horzLines: { color: "#22302a" } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#293832" },
      timeScale: { borderColor: "#293832", rightOffset: 3 },
    })
    const seriesOptions = {
      lineWidth: 2 as const,
      priceLineVisible: false,
      priceFormat: { type: "custom" as const, formatter: percentFromEquity },
    }
    const strategy = chart.addSeries(LineSeries, { ...seriesOptions, color: "#b6f559", title: "Strategy" }, 0)
    const buyHold = chart.addSeries(LineSeries, { ...seriesOptions, color: "#64d5c7", title: "Buy & Hold" }, 0)
    const spy = chart.addSeries(LineSeries, { ...seriesOptions, color: "#f8bd5e", title: "SPY" }, 0)
    strategy.setData(points.map((point) => ({ time: point.date as Time, value: point.strategy })))
    buyHold.setData(points.map((point) => ({ time: point.date as Time, value: point.buyHold })))
    spy.setData(points.map((point) => ({ time: point.date as Time, value: point.spy })))
    const drawdown = chart.addSeries(AreaSeries, {
      lineColor: "#ff6a6a",
      topColor: "#ff6a6a55",
      bottomColor: "#ff6a6a08",
      lineWidth: 1,
      priceLineVisible: false,
      title: "Strategy Drawdown",
      priceFormat: { type: "custom", formatter: (value: number) => `${value.toFixed(1)}%` },
    }, 1)
    drawdown.setData(points.map((point, index) => ({ time: point.date as Time, value: strategyDrawdowns[index] })))
    chart.panes()[0]?.setHeight(300)
    chart.panes()[1]?.setHeight(120)
    chart.timeScale().fitContent()
    chart.subscribeCrosshairMove((parameter) => {
      const date = parameter.time ? String(parameter.time) : ""
      const index = points.findIndex((point) => point.date === date)
      if (index < 0) return setHover(null)
      setKeyboardIndex(null)
      setHover({
        date,
        strategy: points[index].strategy,
        buyHold: points[index].buyHold,
        spy: points[index].spy,
        drawdown: strategyDrawdowns[index],
      })
    })
    return () => chart.remove()
  }, [points, strategyDrawdowns])

  if (!points.length) return <div className="grid h-96 place-items-center text-sm text-muted-foreground">No equity history was returned.</div>
  const selectedKeyboardIndex = keyboardIndex !== null && points[keyboardIndex] ? keyboardIndex : null
  const keyboardValues = selectedKeyboardIndex === null ? null : { point: points[selectedKeyboardIndex], drawdown: strategyDrawdowns[selectedKeyboardIndex] }
  const latest = keyboardValues ? { date: keyboardValues.point.date, strategy: keyboardValues.point.strategy, buyHold: keyboardValues.point.buyHold, spy: keyboardValues.point.spy, drawdown: keyboardValues.drawdown } : hover || { date: points.at(-1)!.date, strategy: points.at(-1)!.strategy, buyHold: points.at(-1)!.buyHold, spy: points.at(-1)!.spy, drawdown: strategyDrawdowns.at(-1)! }
  const selectWithKeyboard = (key: string) => {
    const next = chartKeyboardIndex(key, keyboardIndex, points.length)
    if (next !== null) setKeyboardIndex(next)
    return next !== null
  }
  return (
    <div className="relative overflow-hidden rounded-lg border bg-[#0b1411]">
      <div aria-hidden="true" className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b bg-background/85 px-3 py-2 font-mono text-[10px]">
        <Badge variant="outline">{latest.date}</Badge>
        <span className="text-primary">Strategy {percentFromEquity(latest.strategy)}</span>
        <span className="text-chart-2">Buy & Hold {percentFromEquity(latest.buyHold)}</span>
        <span className="text-chart-3">SPY {percentFromEquity(latest.spy)}</span>
        <span className="text-destructive">Drawdown {latest.drawdown.toFixed(2)}%</span>
      </div>
      <div
        ref={containerRef}
        role="group"
        tabIndex={0}
        aria-label="Interactive strategy, buy and hold, SPY, and drawdown chart"
        aria-describedby="equity-chart-keyboard-help equity-chart-current-value"
        aria-keyshortcuts="ArrowLeft ArrowRight Home End"
        className="h-[440px] w-full focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary"
        onKeyDown={(event) => { if (selectWithKeyboard(event.key)) event.preventDefault() }}
      />
      <p id="equity-chart-keyboard-help" className="sr-only">Use Left and Right Arrow to inspect adjacent dates. Home selects the first date and End selects the latest date.</p>
      <p id="equity-chart-current-value" aria-live="polite" className="sr-only">{latest.date}. Strategy {percentFromEquity(latest.strategy)}, buy and hold {percentFromEquity(latest.buyHold)}, SPY {percentFromEquity(latest.spy)}, drawdown {latest.drawdown.toFixed(2)}%.</p>
    </div>
  )
}
