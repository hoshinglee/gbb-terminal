import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { EvidenceWorkspace } from "@/features/strategy-lab/evidence-workspace"
import type { BacktestResult } from "@/lib/types"

vi.mock("@/features/strategy-lab/equity-drawdown-chart", () => ({
  EquityDrawdownChart: () => <div>Equity chart</div>,
}))

const result: BacktestResult = {
  strategy: { name: "SMA Crossover", description: "Trend strategy" },
  metrics: {
    totalReturn: 8,
    benchmarkReturn: 10,
    maxDrawdown: -5,
    sharpeRatio: 0.8,
    trades: 1,
    openTrades: 0,
    benchmarkMetrics: {},
  },
  verdict: { label: "Insufficient Evidence", reason: "Research only." },
  explanation: "The strategy returned less than buy and hold.",
  assumptions: { initial_capital: 100000, commission_bps: 0, slippage_bps: 0, annual_cash_rate: 0 },
  executionModel: "Next open",
  evaluationPeriod: { start: "2026-07-01", end: "2026-08-14", sessions: 32 },
  chart: [],
  marketChart: null,
  trades: [{ status: "Closed", side: "LONG", entryDate: "2026-07-01", entryPrice: 180, exitDate: "2026-07-24", exitPrice: 187, pnl: 3888, pnlPercent: 3.89, barsHeld: 17 }],
}

describe("EvidenceWorkspace trade history", () => {
  it("shows recent trade history and opens the full ledger", async () => {
    const user = userEvent.setup()
    render(<EvidenceWorkspace result={result} search={null} runLabel="Single Configuration" />)

    expect(screen.getByText("Recent entries, exits, open marks, and realized or unrealized P&L.")).toBeInTheDocument()
    expect(screen.getByText("2026-07-01 · $180.00")).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: /Trade History/ }))

    expect(screen.getByRole("tab", { name: /Trade History/ })).toHaveAttribute("data-state", "active")
    expect(screen.getByText("Trade ledger with entry, exit, profit and loss, holding period, and execution costs.")).toBeInTheDocument()
  })
})
