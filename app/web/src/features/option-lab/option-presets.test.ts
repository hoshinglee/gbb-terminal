import { describe, expect, it } from "vitest"

import {
  applyContractToLeg,
  createOptionDraft,
  FALLBACK_OPTION_TEMPLATES,
  replaceOptionTemplate,
  validateOptionDraft,
} from "@/features/option-lab/option-presets"

describe("option position presets", () => {
  it("builds a covered call with required shares", () => {
    const template = FALLBACK_OPTION_TEMPLATES.find((item) => item.kind === "covered_call")!
    const draft = createOptionDraft(template, { ticker: "nvda", underlying_price: 180 })

    expect(draft.ticker).toBe("NVDA")
    expect(draft.shares).toBe(100)
    expect(draft.share_cost_basis).toBe(180)
    expect(validateOptionDraft(draft)).toBeNull()
  })

  it("rebuilds legs when a different position is selected", () => {
    const call = createOptionDraft(FALLBACK_OPTION_TEMPLATES[0], { underlying_price: 200 })
    call.interest_rate = 0.03
    const spread = replaceOptionTemplate(call, FALLBACK_OPTION_TEMPLATES.find((item) => item.kind === "bull_call_spread")!)

    expect(spread.legs).toHaveLength(2)
    expect(spread.legs.map((leg) => leg.side)).toEqual(["long", "short"])
    expect(spread.legs[1].strike).toBeGreaterThan(spread.legs[0].strike)
    expect(spread.interest_rate).toBe(0.03)
  })

  it("loads current-chain values into only the chosen leg", () => {
    const draft = createOptionDraft(FALLBACK_OPTION_TEMPLATES.find((item) => item.kind === "bull_put_spread")!)
    const target = draft.legs[1]
    const updated = applyContractToLeg(draft, target.leg_id, {
      contract: "NVDA270101P00190000",
      strike: 190,
      last: 0,
      bid: 4,
      ask: 4.4,
      volume: 20,
      openInterest: 1200,
      iv: 31,
    }, "2027-01-01")

    expect(updated.legs[1]).toMatchObject({ strike: 190, premium: 4.4, premium_source: "ask", implied_volatility: 0.31, expiration: "2027-01-01" })
    expect(updated.legs[0]).toEqual(draft.legs[0])
  })

  it("uses executable-side prices for long and short contracts", () => {
    const contract = {
      contract: "NVDA270101C00200000",
      strike: 200,
      last: 3.5,
      bid: 3.2,
      ask: 3.8,
      volume: 20,
      openInterest: 1200,
      iv: 31,
    }
    const longCall = createOptionDraft(FALLBACK_OPTION_TEMPLATES.find((item) => item.kind === "long_call")!)
    const shortCall = createOptionDraft(FALLBACK_OPTION_TEMPLATES.find((item) => item.kind === "short_call")!)

    expect(applyContractToLeg(longCall, longCall.legs[0].leg_id, contract, "2027-01-01").legs[0]).toMatchObject({ premium: 3.8, premium_source: "ask" })
    expect(applyContractToLeg(shortCall, shortCall.legs[0].leg_id, contract, "2027-01-01").legs[0]).toMatchObject({ premium: 3.2, premium_source: "bid" })
  })

  it("builds a matched conversion without hidden leg assumptions", () => {
    const template = FALLBACK_OPTION_TEMPLATES.find((item) => item.kind === "conversion")!
    const draft = createOptionDraft(template, { underlying_price: 120 })

    expect(draft.shares).toBe(100)
    expect(draft.legs).toHaveLength(2)
    expect(draft.legs.map((leg) => [leg.side, leg.option_type])).toEqual([["long", "put"], ["short", "call"]])
    expect(new Set(draft.legs.map((leg) => leg.strike)).size).toBe(1)
    expect(validateOptionDraft(draft)).toBeNull()
  })
})
