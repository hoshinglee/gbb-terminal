import { describe, expect, it } from "vitest"

import { buildTreemapLayout } from "@/features/market-pulse/sector-constituents"
import type { SectorConstituentResearch } from "@/lib/types"

function constituent(symbol: string, marketCap: number | null): SectorConstituentResearch {
  return {
    symbol,
    companyName: `${symbol} Corporation`,
    sector: "Information Technology",
    subIndustry: "Software",
    companyId: null,
    price: 100,
    dailyChangePercent: 1,
    marketCap,
    marketCapSource: marketCap === null ? "unavailable_equal_area_fallback" : "calculated",
    dataStatus: "completed",
    observationTimestamp: "2026-08-16T12:00:00Z",
    knownAt: "2026-08-16T12:00:00Z",
    qualityWarnings: [],
  }
}

describe("sector constituent treemap", () => {
  it("sizes known companies by market cap", () => {
    const layout = buildTreemapLayout([
      constituent("LARGE", 300),
      constituent("SMALL", 100),
    ], 400, 200)
    const large = layout.find((rectangle) => rectangle.item.symbol === "LARGE")!
    const small = layout.find((rectangle) => rectangle.item.symbol === "SMALL")!

    expect(large.width * large.height).toBeCloseTo((small.width * small.height) * 3)
    expect(layout.every((rectangle) => !rectangle.usesEqualAreaFallback)).toBe(true)
  })

  it("places unavailable market caps in an explicit equal-area region", () => {
    const layout = buildTreemapLayout([
      constituent("KNOWN", 300),
      constituent("MISS1", null),
      constituent("MISS2", null),
    ], 400, 200)
    const missing = layout.filter((rectangle) => rectangle.usesEqualAreaFallback)

    expect(missing).toHaveLength(2)
    expect(missing[0].width * missing[0].height).toBeCloseTo(missing[1].width * missing[1].height)
    expect(missing.every((rectangle) => rectangle.y > 0)).toBe(true)
  })
})
