import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { planOptionPositions, runOptionScenario } from "@/lib/api"
import type { OptionPlanResult, OptionScenarioResult } from "@/lib/types"
import { OptionsPlanner } from "./options-planner"

vi.mock("@/lib/api", () => ({
  planOptionPositions: vi.fn(),
  runOptionScenario: vi.fn(),
}))

const expiration = "2026-12-18"
const position = {
  run_name: "NVDA Bull Call Spread Plan",
  ticker: "NVDA",
  underlying_price: 200,
  position_kind: "bull_call_spread" as const,
  legs: [
    { leg_id: "long", option_type: "call" as const, side: "long" as const, strike: 200, expiration, premium: 10, quantity: 1, implied_volatility: 0.3, multiplier: 100, contract_symbol: "NVDA-C-200", premium_source: "ask" as const },
    { leg_id: "short", option_type: "call" as const, side: "short" as const, strike: 220, expiration, premium: 4, quantity: 1, implied_volatility: 0.3, multiplier: 100, contract_symbol: "NVDA-C-220", premium_source: "bid" as const },
  ],
  shares: 0,
  share_cost_basis: null,
  interest_rate: 0.04,
  dividend_yield: 0,
  paths: 200,
  seed: 42,
  data_provenance: { source: "Fixture", status: "Delayed" },
}

const plan: OptionPlanResult = {
  ticker: "NVDA",
  outlook: "bullish",
  targetDate: "2026-11-15",
  underlyingPrice: 200,
  expiration,
  generatedAt: "2026-10-01T12:00:00Z",
  candidates: [{
    candidateId: "bull-call",
    name: "Bull Call Spread",
    positionKind: "bull_call_spread",
    tradeoff: "Lower debit with capped risk and reward.",
    position,
    expiration,
    strikes: [200, 220],
    netDebit: 600,
    netCredit: 0,
    capitalRequired: 600,
    collateral: 2000,
    maximumLoss: -600,
    maximumGain: 1400,
    profitCharacter: "Capped",
    breakEvens: [206],
    greeks: { delta: 22, gamma: 1.2, theta: -4, vega: 12 },
    quotes: [
      { legId: "long", contractSymbol: "NVDA-C-200", optionType: "call", side: "long", strike: 200, bid: 9.5, ask: 10, last: 9.8, spread: 0.5, spreadPercent: 5.13, quoteQuality: "Two-Sided", premiumUsed: 10, premiumSource: "ask", impliedVolatility: 30, volume: 100, openInterest: 500 },
      { legId: "short", contractSymbol: "NVDA-C-220", optionType: "call", side: "short", strike: 220, bid: 4, ask: 4.4, last: 4.2, spread: 0.4, spreadPercent: 9.52, quoteQuality: "Two-Sided", premiumUsed: 4, premiumSource: "bid", impliedVolatility: 30, volume: 80, openInterest: 400 },
    ],
    quoteQuality: "Two-Sided",
    withinBudget: true,
    warnings: [],
  }],
  earningsContext: { historicalMedianAbsoluteMovePercent: 7.8, sampleSize: 12, asOf: "2026-09-30T00:00:00Z", eventSource: "SEC EDGAR Company Facts", priceSource: "Yahoo Finance", warnings: [], interpretation: "Context only." },
  impliedMoveContext: { movePercent: 9.6, straddlePrice: 19.2, strike: 200, expiration, quoteMethod: "Call mid + put mid", interpretation: "Not labelled an earnings-implied move." },
  dataProvenance: { source: "Fixture", status: "Delayed" },
  warnings: [],
  limitations: ["Educational comparison only."],
}

const scenario: OptionScenarioResult = {
  ticker: "NVDA",
  positionKind: "bull_call_spread",
  scenarioPrice: 215,
  scenarioDate: "2026-11-15",
  modeledPositionValue: 1100,
  modeledOptionValue: 1100,
  modeledShareValue: 0,
  pnl: 500,
  pnlPercent: 83.33,
  breakEvens: [206],
  breakEvenRelation: "$9.00 above the nearest modeled expiry break-even.",
  remainingDays: 33,
  greeks: { delta: 18, gamma: 0.8, theta: -2.5, vega: 8 },
  assumptions: { model: "Cox-Ross-Rubinstein American Binomial", interestRate: 0.04, dividendYield: 0, impliedVolatilities: [30, 30], contractMultiplier: 100 },
  dataProvenance: { source: "Fixture" },
  warnings: ["The modeled value is theoretical."],
}

describe("OptionsPlanner", () => {
  beforeEach(() => {
    vi.mocked(planOptionPositions).mockResolvedValue(plan)
    vi.mocked(runOptionScenario).mockResolvedValue(scenario)
  })

  it("supports keyboard outlook selection and sends ownership constraints", async () => {
    const user = userEvent.setup()
    const onProgress = vi.fn()
    render(<OptionsPlanner ticker="NVDA" interestRate={0.04} dividendYield={0} onUseCandidate={vi.fn()} onProgress={onProgress} />)

    const neutral = screen.getByRole("button", { name: /Neutral/ })
    neutral.focus()
    await user.keyboard("{Enter}")
    expect(neutral).toHaveAttribute("aria-pressed", "true")
    await user.click(screen.getByText(/Ownership And Target Range/))
    await user.clear(screen.getByLabelText("Shares already owned"))
    await user.type(screen.getByLabelText("Shares already owned"), "100")
    await user.click(screen.getByRole("button", { name: /Acquiring Shares Is Acceptable/ }))
    await user.click(screen.getByRole("button", { name: /Compare Structures/ }))

    await screen.findByText("Bull Call Spread")
    expect(planOptionPositions).toHaveBeenCalledWith(expect.objectContaining({ outlook: "neutral", shares_owned: 100, acquiring_shares_acceptable: true }))
    expect(onProgress).toHaveBeenLastCalledWith(2)
  })

  it("keeps the comparison visible while opening the detailed builder", async () => {
    const user = userEvent.setup()
    const onUseCandidate = vi.fn()
    render(<OptionsPlanner ticker="NVDA" interestRate={0.04} dividendYield={0} onUseCandidate={onUseCandidate} onProgress={vi.fn()} />)

    await user.click(screen.getByRole("button", { name: /Compare Structures/ }))
    await user.click(await screen.findByRole("button", { name: /Use In Detailed Builder/ }))

    expect(onUseCandidate).toHaveBeenCalledWith(plan.candidates[0])
    expect(screen.getByRole("heading", { name: /Different trade-offs/ })).toBeInTheDocument()
  })

  it("models the primary price-and-date scenario through the server API", async () => {
    const user = userEvent.setup()
    const onProgress = vi.fn()
    render(<OptionsPlanner ticker="NVDA" interestRate={0.04} dividendYield={0} onUseCandidate={vi.fn()} onProgress={onProgress} />)

    await user.click(screen.getByRole("button", { name: /Compare Structures/ }))
    await screen.findByText(/What if NVDA is \$X on date Y/)
    await user.clear(screen.getByLabelText("Option scenario price"))
    await user.type(screen.getByLabelText("Option scenario price"), "215")
    await user.click(screen.getByRole("button", { name: /Model Scenario/ }))

    await waitFor(() => expect(runOptionScenario).toHaveBeenCalledWith(expect.objectContaining({ position, scenario_price: 215 })))
    expect(await screen.findByText("$9.00 above the nearest modeled expiry break-even.")).toBeInTheDocument()
    expect(screen.getByText("$500.00 · 83.33%")).toBeInTheDocument()
    expect(onProgress).toHaveBeenLastCalledWith(3)
  })
})
