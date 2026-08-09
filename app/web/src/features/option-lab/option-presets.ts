import type {
  OptionChainContract,
  OptionLeg,
  OptionPositionCreate,
  OptionPositionKind,
  OptionPositionTemplate,
} from "@/lib/types"

export const FALLBACK_OPTION_TEMPLATES: OptionPositionTemplate[] = [
  { kind: "long_call", name: "Long Call", legs: [{ optionType: "call", side: "long" }] },
  { kind: "long_put", name: "Long Put", legs: [{ optionType: "put", side: "long" }] },
  { kind: "short_call", name: "Short Call", legs: [{ optionType: "call", side: "short" }] },
  { kind: "short_put", name: "Short Put", legs: [{ optionType: "put", side: "short" }] },
  { kind: "covered_call", name: "Covered Call", shares: 100, legs: [{ optionType: "call", side: "short" }] },
  { kind: "cash_secured_put", name: "Cash-Secured Put", legs: [{ optionType: "put", side: "short" }] },
  { kind: "bull_call_spread", name: "Bull Call Spread", legs: [{ optionType: "call", side: "long" }, { optionType: "call", side: "short" }] },
  { kind: "bear_call_spread", name: "Bear Call Spread", legs: [{ optionType: "call", side: "short" }, { optionType: "call", side: "long" }] },
  { kind: "bull_put_spread", name: "Bull Put Spread", legs: [{ optionType: "put", side: "short" }, { optionType: "put", side: "long" }] },
  { kind: "bear_put_spread", name: "Bear Put Spread", legs: [{ optionType: "put", side: "long" }, { optionType: "put", side: "short" }] },
  { kind: "conversion", name: "Conversion", category: "Financing / Parity", shares: 100, legs: [{ role: "Protective Put", optionType: "put", side: "long" }, { role: "Covered Short Call", optionType: "call", side: "short" }] },
]

const positionDescriptions: Record<OptionPositionKind, string> = {
  custom: "A manually assembled option position.",
  long_call: "Defined-risk bullish exposure with upside convexity.",
  long_put: "Defined-risk bearish exposure or portfolio protection.",
  short_call: "Premium income with uncapped upside assignment risk.",
  short_put: "Premium income with an obligation to acquire shares.",
  covered_call: "Own shares and sell a call against them for premium income.",
  cash_secured_put: "Reserve strike cash while selling a put.",
  bull_call_spread: "Defined-risk bullish call spread with capped upside.",
  bear_call_spread: "Defined-risk bearish call credit spread.",
  bull_put_spread: "Defined-risk bullish put credit spread.",
  bear_put_spread: "Defined-risk bearish put debit spread.",
  conversion: "A put-call-parity financing structure with matched shares, put, call, strike, and expiry.",
}

export function optionPositionDescription(kind: OptionPositionKind) {
  return positionDescriptions[kind]
}

export function futureDate(days = 45, today = new Date()) {
  const expiration = new Date(today)
  expiration.setDate(expiration.getDate() + days)
  return expiration.toISOString().slice(0, 10)
}

function legId(index: number) {
  return globalThis.crypto?.randomUUID?.() || `option-leg-${Date.now()}-${index}`
}

function strikeFor(kind: OptionPositionKind, spot: number, index: number) {
  if (index === 0) return Math.max(1, Math.round(spot))
  if (kind === "conversion") return Math.max(1, Math.round(spot))
  if (kind === "bull_call_spread" || kind === "bear_call_spread") return Math.max(1, Math.round(spot + 10))
  return Math.max(1, Math.round(spot - 10))
}

export function createOptionDraft(
  template: OptionPositionTemplate,
  context: Partial<Pick<OptionPositionCreate, "ticker" | "underlying_price" | "interest_rate" | "dividend_yield" | "paths" | "seed">> = {},
): OptionPositionCreate {
  const ticker = (context.ticker || "NVDA").toUpperCase()
  const spot = context.underlying_price || 200
  const expiration = futureDate()
  const basePremium = Math.max(1, Number((spot * 0.04).toFixed(2)))
  const legs: OptionLeg[] = template.legs.map((leg, index) => ({
    leg_id: legId(index),
    option_type: leg.optionType,
    side: leg.side,
    strike: strikeFor(template.kind, spot, index),
    expiration,
    premium: Number((index === 0 ? basePremium : basePremium / 2).toFixed(2)),
    quantity: 1,
    implied_volatility: 0.3,
    multiplier: 100,
    contract_symbol: null,
    premium_source: "manual",
  }))
  const shares = template.shares || 0
  return {
    name: `${ticker} ${template.name}`,
    ticker,
    underlying_price: spot,
    position_kind: template.kind,
    legs,
    shares,
    share_cost_basis: shares ? spot : null,
    interest_rate: context.interest_rate ?? 0.04,
    dividend_yield: context.dividend_yield ?? 0,
    paths: context.paths ?? 200,
    seed: context.seed ?? 42,
  }
}

export function replaceOptionTemplate(current: OptionPositionCreate, template: OptionPositionTemplate) {
  return createOptionDraft(template, {
    ticker: current.ticker,
    underlying_price: current.underlying_price,
    interest_rate: current.interest_rate,
    dividend_yield: current.dividend_yield,
    paths: current.paths,
    seed: current.seed,
  })
}

export function optionContractPremium(contract: OptionChainContract, side: "long" | "short") {
  if (side === "long" && contract.ask > 0) return contract.ask
  if (side === "short" && contract.bid > 0) return contract.bid
  if (contract.last > 0) return contract.last
  if (contract.bid > 0 && contract.ask > 0) return Number(((contract.bid + contract.ask) / 2).toFixed(2))
  if (contract.ask > 0) return contract.ask
  if (contract.bid > 0) return contract.bid
  return 0
}

export function optionContractPremiumSource(contract: OptionChainContract, side: "long" | "short") {
  if (side === "long" && contract.ask > 0) return "ask" as const
  if (side === "short" && contract.bid > 0) return "bid" as const
  if (contract.last > 0) return "last" as const
  if (contract.bid > 0 && contract.ask > 0) return "mid" as const
  return contract.ask > 0 ? "ask" as const : "bid" as const
}

export function applyContractToLeg(draft: OptionPositionCreate, legIdToUpdate: string, contract: OptionChainContract, expiration: string) {
  return {
    ...draft,
    legs: draft.legs.map((leg) => leg.leg_id === legIdToUpdate ? {
      ...leg,
      strike: contract.strike,
      expiration,
      premium: optionContractPremium(contract, leg.side),
      premium_source: optionContractPremiumSource(contract, leg.side),
      implied_volatility: Math.max(contract.iv / 100, 0.0001),
      contract_symbol: contract.contract,
    } : leg),
  }
}

export function validateOptionDraft(draft: OptionPositionCreate) {
  if (!draft.ticker.trim()) return "Enter a US ticker."
  if (!(draft.underlying_price > 0)) return "Underlying price must be greater than zero."
  if (!draft.legs.length) return "Add at least one option leg."
  if (draft.legs.some((leg) => !(leg.strike > 0) || !(leg.premium >= 0) || !(leg.implied_volatility > 0) || !(leg.quantity > 0) || !leg.expiration)) return "Complete every option leg before simulation."
  const shortContracts = draft.legs.filter((leg) => leg.side === "short").reduce((total, leg) => total + leg.quantity, 0)
  if (draft.position_kind === "covered_call" && draft.shares < shortContracts * 100) return "A covered call needs 100 shares per short call contract."
  const matchingLegRecipes: OptionPositionKind[] = ["bull_call_spread", "bear_call_spread", "bull_put_spread", "bear_put_spread", "conversion"]
  if (matchingLegRecipes.includes(draft.position_kind) && (new Set(draft.legs.map((leg) => leg.expiration)).size !== 1 || new Set(draft.legs.map((leg) => leg.quantity)).size !== 1)) return "This recipe requires matching expirations and quantities across every option leg."
  if (draft.position_kind === "bull_call_spread" && !(draft.legs[0].strike < draft.legs[1].strike)) return "A Bull Call Spread needs the long strike below the short strike."
  if (draft.position_kind === "bear_call_spread" && !(draft.legs[0].strike < draft.legs[1].strike)) return "A Bear Call Spread needs the short strike below the long strike."
  if (draft.position_kind === "bull_put_spread" && !(draft.legs[0].strike > draft.legs[1].strike)) return "A Bull Put Spread needs the short strike above the long strike."
  if (draft.position_kind === "bear_put_spread" && !(draft.legs[0].strike > draft.legs[1].strike)) return "A Bear Put Spread needs the long strike above the short strike."
  if (draft.position_kind === "conversion" && (draft.shares !== draft.legs[0].quantity * draft.legs[0].multiplier || new Set(draft.legs.map((leg) => leg.strike)).size !== 1)) return "A Conversion needs exactly 100 shares per matched put/call pair using the same strike."
  return null
}
