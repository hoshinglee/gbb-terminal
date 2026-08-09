import { describe, expect, it } from "vitest"

import { chartKeyboardIndex } from "@/lib/chart-keyboard"

describe("chartKeyboardIndex", () => {
  it("moves from the latest point and clamps at either boundary", () => {
    expect(chartKeyboardIndex("ArrowLeft", null, 5)).toBe(3)
    expect(chartKeyboardIndex("ArrowLeft", 0, 5)).toBe(0)
    expect(chartKeyboardIndex("ArrowRight", 4, 5)).toBe(4)
  })

  it("supports first and latest shortcuts without consuming unrelated keys", () => {
    expect(chartKeyboardIndex("Home", 3, 5)).toBe(0)
    expect(chartKeyboardIndex("End", 1, 5)).toBe(4)
    expect(chartKeyboardIndex("Enter", 1, 5)).toBeNull()
    expect(chartKeyboardIndex("ArrowLeft", null, 0)).toBeNull()
  })
})
