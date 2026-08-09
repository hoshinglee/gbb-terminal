import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { PaperPositionHistorySheet } from "@/features/option-lab/paper-position-history-sheet"
import type { OptionPositionState } from "@/lib/types"

const paperPosition: OptionPositionState = {
  position_id: "paper-position-1",
  name: "NVDA Covered Call",
  ticker: "NVDA",
  position_kind: "covered_call",
  research_run_id: "simulation-run-1",
  current_structure: "Covered Call",
  status: "open",
  opened_at: "2026-08-09T10:00:00",
  updated_at: "2026-08-09T11:00:00",
  underlying_price: 180,
  cash: -17_400,
  shares: 100,
  share_cost_basis: 180,
  realized_pnl: 0,
  collateral: 0,
  legs: [{
    leg_id: "short-call-1",
    option_type: "call",
    side: "short",
    strike: 190,
    expiration: "2026-09-18",
    premium: 6,
    quantity: 1,
    implied_volatility: 0.3,
    multiplier: 100,
    contract_symbol: null,
    premium_source: "manual",
  }],
  closed_quantities: {},
}

describe("paper position history", () => {
  it("reopens a persisted local ledger", async () => {
    const user = userEvent.setup()
    const loadPosition = vi.fn().mockResolvedValue(undefined)
    render(<PaperPositionHistorySheet positions={[paperPosition]} loading={false} onRefresh={vi.fn()} onLoad={loadPosition} />)

    await user.click(screen.getByRole("button", { name: /Positions/ }))
    await user.click(screen.getByRole("button", { name: /NVDA Covered Call/ }))

    expect(loadPosition).toHaveBeenCalledWith("paper-position-1")
  })
})
