export type LabId = "strategy" | "options" | "market" | "intelligence"
export type LabHrefTarget = LabId | "stock"

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
  if (requested === "stock") return "intelligence"
  return requested === "options" || requested === "market" || requested === "intelligence" ? requested : "strategy"
}

export function labHref(lab: LabHrefTarget, ticker?: string) {
  const parameters = new URLSearchParams()
  const destination = lab === "stock" ? "intelligence" : lab
  if (destination !== "strategy") parameters.set("lab", destination)
  if (ticker) parameters.set("ticker", normalizeTicker(ticker))
  const query = parameters.toString()
  return query ? `/?${query}` : "/"
}

export function legacyStockRedirect(search: string) {
  const parameters = new URLSearchParams(search)
  if (parameters.get("lab") !== "stock") return null
  return labHref("intelligence", tickerFromSearch(search))
}
