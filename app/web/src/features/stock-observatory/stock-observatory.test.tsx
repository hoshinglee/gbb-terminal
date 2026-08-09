import { afterEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"

import { StockObservatory } from "@/features/stock-observatory/stock-observatory"

vi.mock("@/features/strategy-lab/market-workspace-chart", () => ({
  MarketWorkspaceChart: ({ symbol }: { symbol: string }) => <div>Chart for {symbol}</div>,
}))

const point = {
  date: "2026-08-07",
  periodStart: "2026-08-07",
  periodEnd: "2026-08-07",
  open: 199,
  high: 205,
  low: 198,
  close: 203,
  volume: 1_000_000,
  indicators: {},
}

afterEach(() => vi.unstubAllGlobals())

describe("Stock Observatory", () => {
  it("loads the requested ticker and preserves it in cross-lab links", async () => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      const payload = url.includes("/api/v2/stocks/MSFT") ? {
        quote: { symbol: "MSFT", price: 203, change: 2, changePercent: 1, periodReturn: 5, dataStatus: { source: "Fixture", status: "Delayed" } },
        marketChart: { defaultInterval: "day", intervals: { day: [point], week: [point], month: [point], year: [point] } },
        period: "1y",
      } : { expirations: [], calls: [], puts: [], source: "Fixture", historicalStatus: "Current Snapshot", dataStatus: { source: "Fixture", status: "Delayed" } }
      return new Response(JSON.stringify(payload), { status: 200, headers: { "Content-Type": "application/json" } })
    }))

    render(<StockObservatory initialTicker="MSFT" />)

    expect(await screen.findByRole("heading", { name: /Read MSFT before choosing/ })).toBeInTheDocument()
    expect(await screen.findByText("Chart for MSFT")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /Test A Strategy/ })).toHaveAttribute("href", "/?ticker=MSFT")
    expect(screen.getByRole("link", { name: /Build An Option Position/ })).toHaveAttribute("href", "/?lab=options&ticker=MSFT")
  })
})
