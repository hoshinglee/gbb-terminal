export type LabId = "strategy" | "options" | "stock" | "market"

const supportedSymbol = /^[A-Z0-9.^=-]{1,12}$/

export function normalizeTicker(value: string | null | undefined, fallback = "NVDA") {
  const normalized = (value || "").trim().toUpperCase()
  return supportedSymbol.test(normalized) ? normalized : fallback
}

export function tickerFromSearch(search: string, fallback = "NVDA") {
  return normalizeTicker(new URLSearchParams(search).get("ticker"), fallback)
}

export function labFromSearch(search: string): LabId {
  const requested = new URLSearchParams(search).get("lab")
  return requested === "options" || requested === "stock" || requested === "market" ? requested : "strategy"
}

export function labHref(lab: LabId, ticker?: string) {
  const parameters = new URLSearchParams()
  if (lab !== "strategy") parameters.set("lab", lab)
  if (ticker) parameters.set("ticker", normalizeTicker(ticker))
  const query = parameters.toString()
  return query ? `/?${query}` : "/"
}
