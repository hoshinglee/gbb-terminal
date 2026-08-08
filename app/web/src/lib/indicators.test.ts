import { describe, expect, it } from "vitest"

import { strategyPriceOverlays } from "@/lib/indicators"
import type { MarketChartPoint, StrategyTemplate } from "@/lib/types"

const points: MarketChartPoint[] = Array.from({ length: 8 }, (_, index) => ({
  date: `2026-01-${String(index + 1).padStart(2, "0")}`,
  periodStart: `2026-01-${String(index + 1).padStart(2, "0")}`,
  periodEnd: `2026-01-${String(index + 1).padStart(2, "0")}`,
  open: 10 + index,
  high: 12 + index,
  low: 8 + index,
  close: 11 + index,
  volume: 1_000 + index,
  indicators: {},
}))

function template(kind: string): StrategyTemplate {
  return {
    template_id: `${kind}-fixture`,
    family: "Fixture",
    version: 2,
    name: "Fixture",
    description: "Fixture strategy.",
    direction: "long",
    parameters: [],
    required_datasets: [],
    rule_graph: { kind },
  }
}

describe("strategyPriceOverlays", () => {
  it("matches the confirmed Darvas rolling ceiling and floor", () => {
    const overlays = strategyPriceOverlays(points, template("darvas_volume"), { box_window: 3, confirmation_bars: 2 })

    expect(overlays.map((overlay) => overlay.label)).toEqual(["Darvas Ceiling 3/2", "Darvas Floor 3/2"])
    expect(overlays[0].values[3]).toBeNull()
    expect(overlays[0].values[4]).toBe(14)
    expect(overlays[1].values[4]).toBe(8)
  })

  it("uses only prior bars for deterministic Fibonacci resistance", () => {
    const overlays = strategyPriceOverlays(points, template("fibonacci"), { window: 3, ratio: 0.5 })

    expect(overlays[0].label).toBe("Fib Resistance 50.0%")
    expect(overlays[0].values[2]).toBeNull()
    expect(overlays[0].values[3]).toBe(11)
  })
})
