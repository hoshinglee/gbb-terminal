import { useId, useMemo, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { chartKeyboardIndex } from "@/lib/chart-keyboard"

export interface OptionChartPoint {
  independentValue: number
  value: number
}

export interface OptionChartSeries {
  label: string
  color: string
  points: OptionChartPoint[]
}

function scale(value: number, minimum: number, maximum: number, start: number, end: number) {
  if (maximum === minimum) return (start + end) / 2
  return start + ((value - minimum) / (maximum - minimum)) * (end - start)
}

function pathFor(points: OptionChartPoint[], bounds: { minimumIndependent: number; maximumIndependent: number; minimumValue: number; maximumValue: number }) {
  return points.map((point, index) => {
    const horizontal = scale(point.independentValue, bounds.minimumIndependent, bounds.maximumIndependent, 72, 976)
    const vertical = scale(point.value, bounds.minimumValue, bounds.maximumValue, 286, 18)
    return `${index ? "L" : "M"}${horizontal.toFixed(2)},${vertical.toFixed(2)}`
  }).join(" ")
}

function compact(value: number) {
  const absolute = Math.abs(value)
  if (absolute >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}m`
  if (absolute >= 1_000) return `${(value / 1_000).toFixed(1)}k`
  return value.toFixed(absolute >= 100 ? 0 : 2)
}

export function OptionLineChart({
  series,
  independentLabel,
  valueLabel,
  valueFormatter = (value) => `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`,
  animate = false,
  ariaLabel,
}: {
  series: OptionChartSeries[]
  independentLabel: string
  valueLabel: string
  valueFormatter?: (value: number) => string
  animate?: boolean
  ariaLabel: string
}) {
  const descriptionId = useId()
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)
  const primary = series[0]?.points || []
  const bounds = useMemo(() => {
    const allPoints = series.flatMap((item) => item.points)
    const independentValues = allPoints.map((point) => point.independentValue)
    const values = allPoints.map((point) => point.value)
    const minimumIndependent = Math.min(...independentValues)
    const maximumIndependent = Math.max(...independentValues)
    const rawMinimum = Math.min(...values, 0)
    const rawMaximum = Math.max(...values, 0)
    const padding = Math.max((rawMaximum - rawMinimum) * 0.08, 1)
    return { minimumIndependent, maximumIndependent, minimumValue: rawMinimum - padding, maximumValue: rawMaximum + padding }
  }, [series])
  if (!primary.length) return <div className="grid h-72 place-items-center rounded-lg border bg-[#0b1411] text-sm text-muted-foreground">No scenario points are available.</div>
  const activeIndex = selectedIndex === null ? primary.length - 1 : Math.min(selectedIndex, primary.length - 1)
  const activeIndependent = primary[activeIndex].independentValue
  const activeValues = series.map((item) => ({ label: item.label, color: item.color, value: item.points[Math.min(activeIndex, item.points.length - 1)]?.value ?? 0 }))
  const zeroVertical = bounds.minimumValue <= 0 && bounds.maximumValue >= 0 ? scale(0, bounds.minimumValue, bounds.maximumValue, 286, 18) : null
  const activeHorizontal = scale(activeIndependent, bounds.minimumIndependent, bounds.maximumIndependent, 72, 976)
  const selectFromPointer = (clientX: number, currentTarget: SVGSVGElement) => {
    const rectangle = currentTarget.getBoundingClientRect()
    const viewBoxHorizontal = ((clientX - rectangle.left) / rectangle.width) * 1000
    const ratio = Math.min(Math.max((viewBoxHorizontal - 72) / 904, 0), 1)
    setSelectedIndex(Math.round(ratio * (primary.length - 1)))
  }
  return (
    <div className="overflow-hidden rounded-lg border bg-[#0b1411]">
      <div aria-hidden="true" className="flex min-h-10 flex-wrap items-center gap-x-3 gap-y-1 border-b bg-background/85 px-3 py-2 font-mono text-[10px]">
        <Badge variant="outline">{independentLabel} {compact(activeIndependent)}</Badge>
        {activeValues.map((item) => <span key={item.label} style={{ color: item.color }}>{item.label} {valueFormatter(item.value)}</span>)}
      </div>
      <svg
        viewBox="0 0 1000 320"
        role="group"
        tabIndex={0}
        aria-label={ariaLabel}
        aria-describedby={descriptionId}
        aria-keyshortcuts="ArrowLeft ArrowRight Home End"
        className="block h-72 w-full touch-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary"
        onPointerMove={(event) => selectFromPointer(event.clientX, event.currentTarget)}
        onPointerLeave={() => setSelectedIndex(null)}
        onKeyDown={(event) => {
          const nextIndex = chartKeyboardIndex(event.key, selectedIndex, primary.length)
          if (nextIndex !== null) {
            event.preventDefault()
            setSelectedIndex(nextIndex)
          }
        }}
      >
        <rect x="0" y="0" width="1000" height="320" fill="#0b1411" />
        {[0, 0.25, 0.5, 0.75, 1].map((fraction) => {
          const vertical = 18 + fraction * 268
          const labelValue = bounds.maximumValue - fraction * (bounds.maximumValue - bounds.minimumValue)
          return <g key={`horizontal-${fraction}`}><line x1="72" x2="976" y1={vertical} y2={vertical} stroke="#22302a" strokeWidth="1" /><text x="64" y={vertical + 4} textAnchor="end" fill="#789087" fontSize="11" fontFamily="monospace">{compact(labelValue)}</text></g>
        })}
        {[0, 0.25, 0.5, 0.75, 1].map((fraction) => {
          const horizontal = 72 + fraction * 904
          const labelValue = bounds.minimumIndependent + fraction * (bounds.maximumIndependent - bounds.minimumIndependent)
          return <g key={`vertical-${fraction}`}><line x1={horizontal} x2={horizontal} y1="18" y2="286" stroke="#16221e" strokeWidth="1" /><text x={horizontal} y="306" textAnchor="middle" fill="#789087" fontSize="11" fontFamily="monospace">{compact(labelValue)}</text></g>
        })}
        {zeroVertical !== null && <line x1="72" x2="976" y1={zeroVertical} y2={zeroVertical} stroke="#8ca097" strokeDasharray="5 5" strokeWidth="1" />}
        {series.map((item, index) => <path key={item.label} d={pathFor(item.points, bounds)} fill="none" stroke={item.color} strokeWidth={index === 0 ? 2.5 : 1.25} opacity={index === 0 ? 1 : 0.45} pathLength="1" className={animate ? "option-path-draw" : undefined} style={animate ? { animationDelay: `${index * 45}ms` } : undefined} />)}
        <line x1={activeHorizontal} x2={activeHorizontal} y1="18" y2="286" stroke="#789087" strokeDasharray="3 4" opacity="0.8" />
        <text x="16" y="14" fill="#789087" fontSize="10" fontFamily="monospace">{valueLabel.toUpperCase()}</text>
        <text x="976" y="318" textAnchor="end" fill="#789087" fontSize="10" fontFamily="monospace">{independentLabel.toUpperCase()}</text>
      </svg>
      <p id={descriptionId} aria-live="polite" className="sr-only">Use Left and Right Arrow to inspect adjacent points. Home selects the first point and End selects the last. {independentLabel} {activeIndependent.toFixed(2)}. {activeValues.map((item) => `${item.label} ${valueFormatter(item.value)}`).join(". ")}.</p>
    </div>
  )
}
