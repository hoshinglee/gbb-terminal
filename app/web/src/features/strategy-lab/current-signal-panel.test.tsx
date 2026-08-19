import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { CurrentSignalPanel } from "@/features/strategy-lab/current-signal-panel"
import type { CurrentSignal, Trade } from "@/lib/types"

const signal: CurrentSignal = {
  targetState: "LONG",
  executedState: "CASH",
  signalPosition: 1,
  executedPosition: 0,
  observationDate: "2026-08-14",
  pendingAtNextOpen: true,
  executionTiming: "Signals are observed at the session close and position changes execute at the next session open.",
  entryCriteria: "Fast average crosses above slow average",
  exitCriteria: "Fast average crosses below slow average",
  entryMatched: true,
  exitMatched: false,
  reason: "Entry criteria matched.",
  ruleValues: { fast_average: 191.25, slow_average: 188.5 },
  latestTransition: {
    signalDate: "2026-08-14",
    executionDate: null,
    fromState: "CASH",
    toState: "LONG",
    executionPrice: null,
    pendingAtNextOpen: true,
    reason: "Entry criteria matched.",
    ruleValues: { fast_average: 191.25, slow_average: 188.5 },
  },
}

const trade: Trade = {
  status: "Closed",
  side: "LONG",
  entryDate: "2026-07-01",
  entryPrice: 180,
  exitDate: "2026-07-24",
  exitPrice: 187,
  pnl: 3888.89,
  pnlPercent: 3.89,
  barsHeld: 17,
}

describe("CurrentSignalPanel", () => {
  it("shows target timing, rule values, transition, and latest trade", () => {
    render(<CurrentSignalPanel signal={signal} trades={[trade]} />)

    expect(screen.getByText("Current Signal")).toBeInTheDocument()
    expect(screen.getByText("Pending Next Open")).toBeInTheDocument()
    expect(screen.getAllByText("Fast Average")).toHaveLength(2)
    expect(screen.getByText(/Signal 2026-08-14/)).toBeInTheDocument()
    expect(screen.getByText(/2026-07-01 @ \$180.00/)).toBeInTheDocument()
    expect(screen.getByText(/not a trade recommendation/)).toBeInTheDocument()
  })
})
