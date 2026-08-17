import { describe, expect, it } from "vitest"

import { labFromSearch, labHref, legacyStockRedirect, normalizeTicker, tickerFromSearch } from "@/lib/navigation"

describe("laboratory navigation", () => {
  it("normalizes supported US market symbols", () => {
    expect(normalizeTicker(" brk-b ")).toBe("BRK-B")
    expect(normalizeTicker("bad symbol")).toBe("NVDA")
    expect(tickerFromSearch("?lab=stock&ticker=msft")).toBe("MSFT")
  })

  it("builds direct cross-lab ticker links", () => {
    expect(labHref("strategy", "NVDA")).toBe("/?ticker=NVDA")
    expect(labHref("options", "NVDA")).toBe("/?lab=options&ticker=NVDA")
    expect(labFromSearch("?lab=market")).toBe("market")
    expect(labFromSearch("?lab=intelligence")).toBe("intelligence")
    expect(labHref("intelligence", "NVDA")).toBe("/?lab=intelligence&ticker=NVDA")
    expect(labFromSearch("?lab=stock&ticker=NVDA")).toBe("intelligence")
    expect(labHref("stock", "NVDA")).toBe("/?lab=intelligence&ticker=NVDA")
    expect(legacyStockRedirect("?lab=stock&ticker=msft")).toBe("/?lab=intelligence&ticker=MSFT")
    expect(legacyStockRedirect("?lab=market")).toBeNull()
    expect(labFromSearch("?lab=unknown")).toBe("strategy")
  })
})
