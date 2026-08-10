import { describe, expect, it } from "vitest"

import { labFromSearch, labHref, normalizeTicker, tickerFromSearch } from "@/lib/navigation"

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
    expect(labFromSearch("?lab=unknown")).toBe("strategy")
  })
})
