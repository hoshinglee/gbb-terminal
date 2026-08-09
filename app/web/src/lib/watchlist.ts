import { normalizeTicker } from "@/lib/navigation"

export const DEFAULT_WATCHLIST = ["NVDA", "MSFT", "AAPL", "SPY"]
export const WATCHLIST_KEY = "gbb-terminal-stock-watchlist"

export function normalizeWatchlist(values: unknown) {
  if (!Array.isArray(values)) return DEFAULT_WATCHLIST
  const symbols = [...new Set(values.filter((value): value is string => typeof value === "string").map((value) => normalizeTicker(value, "")).filter(Boolean))]
  return symbols.slice(0, 20)
}

export function readWatchlist(storage: Pick<Storage, "getItem"> = globalThis.localStorage) {
  try {
    const stored = storage.getItem(WATCHLIST_KEY)
    return stored ? normalizeWatchlist(JSON.parse(stored)) : DEFAULT_WATCHLIST
  } catch {
    return DEFAULT_WATCHLIST
  }
}

export function writeWatchlist(symbols: string[], storage: Pick<Storage, "setItem"> = globalThis.localStorage) {
  try {
    storage.setItem(WATCHLIST_KEY, JSON.stringify(normalizeWatchlist(symbols)))
  } catch {
    return false
  }
  return true
}
