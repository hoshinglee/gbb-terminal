import { describe, expect, it } from "vitest"

import { summarizeSectors, universeRefreshOutcome } from "@/features/market-pulse/market-pulse"
import type { LocalUniverseJob, MarketOverviewRow } from "@/lib/types"

function sector(symbol: string, changePercent: number | null, available = true): MarketOverviewRow {
  return {
    symbol,
    name: symbol,
    price: available ? 100 : null,
    change: changePercent,
    changePercent,
    periodReturn: changePercent,
    relativeStrength: changePercent,
    dataStatus: { source: "Fixture", status: available ? "Delayed" : "Unavailable" },
    available,
  }
}

describe("market sector summary", () => {
  it("excludes unavailable rows from breadth and ranking", () => {
    const summary = summarizeSectors([
      sector("XLK", 1.2),
      sector("XLE", -0.8),
      sector("XLU", 0),
      sector("XLRE", null, false),
    ])

    expect(summary).toMatchObject({ available: 3, advancing: 1, declining: 1, unchanged: 1 })
    expect(summary.leader?.symbol).toBe("XLK")
    expect(summary.laggard?.symbol).toBe("XLE")
  })

  it("keeps a partial domain result visible through a completed local job", () => {
    const job = {
      status: "completed",
      result: { status: "partial" },
    } as LocalUniverseJob

    expect(universeRefreshOutcome(job)).toBe("partial")
  })
})
