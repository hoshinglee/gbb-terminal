import type { MarketChartPoint, ParameterValue, PricePoint, StrategyTemplate } from "@/lib/types"

function simpleMovingAverage(values: number[], window: number) {
  return values.map((_, index) => index + 1 < window ? null : values.slice(index + 1 - window, index + 1).reduce((sum, value) => sum + value, 0) / window)
}

function exponentialMovingAverage(values: number[], window: number) {
  const multiplier = 2 / (window + 1)
  let previous = values[0]
  return values.map((value, index) => {
    previous = index === 0 ? value : value * multiplier + previous * (1 - multiplier)
    return previous
  })
}

function rollingDeviation(values: number[], window: number) {
  return values.map((_, index) => {
    if (index + 1 < window) return null
    const sample = values.slice(index + 1 - window, index + 1)
    const mean = sample.reduce((sum, value) => sum + value, 0) / window
    return Math.sqrt(sample.reduce((sum, value) => sum + (value - mean) ** 2, 0) / window)
  })
}

function relativeStrengthIndex(values: number[], window: number) {
  let averageGain = 0
  let averageLoss = 0
  return values.map((value, index) => {
    if (index === 0) return null
    const change = value - values[index - 1]
    const gain = Math.max(change, 0)
    const loss = Math.max(-change, 0)
    if (index <= window) {
      averageGain += gain / window
      averageLoss += loss / window
      if (index < window) return null
    } else {
      averageGain = (averageGain * (window - 1) + gain) / window
      averageLoss = (averageLoss * (window - 1) + loss) / window
    }
    if (averageLoss === 0) return 100
    return 100 - 100 / (1 + averageGain / averageLoss)
  })
}

function valueOrUndefined(value: number | null) {
  return value === null || !Number.isFinite(value) ? undefined : Number(value.toFixed(4))
}

export function enrichPricePoints(points: PricePoint[]): MarketChartPoint[] {
  if (!points.length) return []
  const closes = points.map((point) => point.close)
  const volumes = points.map((point) => point.volume)
  const sma20 = simpleMovingAverage(closes, 20)
  const ema20 = exponentialMovingAverage(closes, 20)
  const deviations = rollingDeviation(closes, 20)
  const volumeSma20 = simpleMovingAverage(volumes, 20)
  const rsi14 = relativeStrengthIndex(closes, 14)
  const ema12 = exponentialMovingAverage(closes, 12)
  const ema26 = exponentialMovingAverage(closes, 26)
  const macd = closes.map((_, index) => ema12[index] - ema26[index])
  const macdSignal = exponentialMovingAverage(macd, 9)
  return points.map((point, index) => {
    const indicators: Record<string, number> = { ...point.indicators }
    const values = {
      sma20: valueOrUndefined(sma20[index]),
      ema20: valueOrUndefined(ema20[index]),
      bollingerMiddle20: valueOrUndefined(sma20[index]),
      bollingerUpper20: valueOrUndefined(sma20[index] === null || deviations[index] === null ? null : sma20[index]! + deviations[index]! * 2),
      bollingerLower20: valueOrUndefined(sma20[index] === null || deviations[index] === null ? null : sma20[index]! - deviations[index]! * 2),
      volumeSma20: valueOrUndefined(volumeSma20[index]),
      rsi14: valueOrUndefined(rsi14[index]),
      macd: valueOrUndefined(macd[index]),
      macdSignal: valueOrUndefined(macdSignal[index]),
      macdHistogram: valueOrUndefined(macd[index] - macdSignal[index]),
    }
    Object.entries(values).forEach(([key, value]) => {
      if (value !== undefined) indicators[key] = value
    })
    return { ...point, periodStart: point.date, periodEnd: point.date, indicators }
  })
}

export interface PriceOverlay {
  label: string
  color: string
  values: Array<number | null>
}

function numberValue(values: Record<string, ParameterValue>, key: string, fallback: number) {
  const value = Number(values[key])
  return Number.isFinite(value) ? value : fallback
}

function priorRollingExtreme(points: MarketChartPoint[], field: "high" | "low", window: number, shift: number, reducer: (values: number[]) => number) {
  return points.map((_, index) => {
    const end = index - shift + 1
    const start = end - window
    if (start < 0 || end <= start) return null
    return reducer(points.slice(start, end).map((point) => point[field]))
  })
}

export function darvasPriceOverlays(points: MarketChartPoint[], boxWindow = 20, confirmations = 3): PriceOverlay[] {
  return [
    { label: `Darvas Ceiling ${boxWindow}/${confirmations}`, color: "#64d5c7", values: priorRollingExtreme(points, "high", boxWindow, confirmations, (values) => Math.max(...values)) },
    { label: `Darvas Floor ${boxWindow}/${confirmations}`, color: "#f8bd5e", values: priorRollingExtreme(points, "low", boxWindow, confirmations, (values) => Math.min(...values)) },
  ]
}

export function fibonacciPriceOverlay(points: MarketChartPoint[], window = 55, ratio = 0.618): PriceOverlay {
  const values = points.map((_, index) => {
    if (index < window) return null
    const sample = points.slice(index - window, index)
    const swingHigh = Math.max(...sample.map((point) => point.high))
    const swingLow = Math.min(...sample.map((point) => point.low))
    return swingHigh - (swingHigh - swingLow) * ratio
  })
  return { label: `Fib Resistance ${(ratio * 100).toFixed(1)}%`, color: "#a78bfa", values }
}

export function strategyPriceOverlays(
  points: MarketChartPoint[],
  template?: StrategyTemplate,
  parameterValues: Record<string, ParameterValue> = {},
): PriceOverlay[] {
  const closes = points.map((point) => point.close)
  if (!template) return [{ label: "SMA 20", color: "#64d5c7", values: simpleMovingAverage(closes, 20) }]
  const kind = template.rule_graph.kind
  if (kind === "crossover") {
    const fastWindow = numberValue(parameterValues, "fast_window", 10)
    const slowWindow = numberValue(parameterValues, "slow_window", 50)
    const calculator = template.rule_graph.average === "ema" ? exponentialMovingAverage : simpleMovingAverage
    const prefix = template.rule_graph.average === "ema" ? "EMA" : "SMA"
    return [
      { label: `${prefix} ${fastWindow}`, color: "#64d5c7", values: calculator(closes, fastWindow) },
      { label: `${prefix} ${slowWindow}`, color: "#f8bd5e", values: calculator(closes, slowWindow) },
    ]
  }
  if (kind === "bollinger") {
    const window = numberValue(parameterValues, "window", 20)
    const multiplier = numberValue(parameterValues, "deviations", 2)
    const middle = simpleMovingAverage(closes, window)
    const deviation = rollingDeviation(closes, window)
    return [
      { label: `Bollinger Mid ${window}`, color: "#64d5c7", values: middle },
      { label: `Upper ${multiplier}σ`, color: "#a78bfa", values: middle.map((value, index) => value === null || deviation[index] === null ? null : value + deviation[index]! * multiplier) },
      { label: `Lower ${multiplier}σ`, color: "#a78bfa", values: middle.map((value, index) => value === null || deviation[index] === null ? null : value - deviation[index]! * multiplier) },
    ]
  }
  if (kind === "donchian") {
    const entryWindow = numberValue(parameterValues, "entry_window", 55)
    const exitWindow = numberValue(parameterValues, "exit_window", 20)
    const rolling = (field: "high" | "low", window: number, reducer: (values: number[]) => number) => points.map((_, index) => index < window ? null : reducer(points.slice(index - window, index).map((point) => point[field])))
    return [
      { label: `Channel High ${entryWindow}`, color: "#64d5c7", values: rolling("high", entryWindow, (values) => Math.max(...values)) },
      { label: `Channel Low ${exitWindow}`, color: "#f8bd5e", values: rolling("low", exitWindow, (values) => Math.min(...values)) },
    ]
  }
  if (kind === "darvas_volume") {
    const boxWindow = numberValue(parameterValues, "box_window", 20)
    const confirmations = numberValue(parameterValues, "confirmation_bars", 3)
    return darvasPriceOverlays(points, boxWindow, confirmations)
  }
  if (kind === "fibonacci") {
    const window = numberValue(parameterValues, "window", 55)
    const ratio = numberValue(parameterValues, "ratio", 0.618)
    return [fibonacciPriceOverlay(points, window, ratio)]
  }
  return [{ label: "SMA 20", color: "#64d5c7", values: simpleMovingAverage(closes, 20) }]
}
