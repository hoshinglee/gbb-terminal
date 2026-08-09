import { describe, expect, it, vi } from "vitest"

import { DEFAULT_WATCHLIST, normalizeWatchlist, readWatchlist, WATCHLIST_KEY, writeWatchlist } from "@/lib/watchlist"

describe("local stock watchlist", () => {
  it("normalizes, deduplicates, and caps symbols", () => {
    expect(normalizeWatchlist([" nvda ", "NVDA", "brk-b", "bad symbol"])).toEqual(["NVDA", "BRK-B"])
    expect(normalizeWatchlist("NVDA")).toEqual(DEFAULT_WATCHLIST)
  })

  it("reads and writes through an injectable local store", () => {
    const setItem = vi.fn()
    expect(writeWatchlist(["MSFT"], { setItem })).toBe(true)
    expect(setItem).toHaveBeenCalledWith(WATCHLIST_KEY, JSON.stringify(["MSFT"]))
    expect(readWatchlist({ getItem: () => JSON.stringify(["aapl"]) })).toEqual(["AAPL"])
  })
})
