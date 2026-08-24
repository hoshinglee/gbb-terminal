import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { DecisionCenter } from "@/features/decision-center/decision-center"
import { loadDecisionCenter, saveThesisCard } from "@/lib/api"
import type { DecisionCenterWorkspace, ThesisCard } from "@/lib/types"

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>()
  return {
    ...original,
    compareDecisionExpressions: vi.fn(),
    createDecisionRecord: vi.fn(),
    loadDecisionCenter: vi.fn(),
    loadDecisionRecords: vi.fn(),
    runDecisionStressTest: vi.fn(),
    saveEntryPlan: vi.fn(),
    savePositionIntent: vi.fn(),
    saveThesisCard: vi.fn(),
    updateDecisionRecord: vi.fn(),
  }
})

const emptyWorkspace: DecisionCenterWorkspace = {
  company_id: "company-nvda",
  ticker: "NVDA",
  company_name: "NVIDIA Corporation",
  thesis: null,
  position_intent: null,
  entry_plans: [],
  decisions: [],
  risk_policy: null,
}

const thesis: ThesisCard = {
  thesis_id: "thesis-1",
  thesis_key: "company-nvda",
  company_id: "company-nvda",
  ticker: "NVDA",
  company_name: "NVIDIA Corporation",
  version: 1,
  status: "watch",
  evidence_strength: "limited",
  moat_assessment: "moderate",
  major_risks: ["Customer concentration"],
  catalysts: ["New product cycle"],
  invalidation_criteria: [],
  rationale: "Demand remains durable, subject to evidence.",
  evidence_references: [],
  supersedes_thesis_id: null,
  created_at: "2026-08-23T00:00:00",
}

describe("DecisionCenter", () => {
  beforeEach(() => {
    vi.mocked(loadDecisionCenter).mockResolvedValue(emptyWorkspace)
    vi.mocked(saveThesisCard).mockResolvedValue(thesis)
  })

  it("shows the full decision chain without blocking on missing context", async () => {
    render(<DecisionCenter initialTicker="NVDA" />)

    expect(await screen.findByRole("heading", { name: "NVIDIA Corporation" })).toBeInTheDocument()
    expect(screen.getByText("Context Incomplete")).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /Thesis/ })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /Position & Fit/ })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /Entry & Stress/ })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: /Journal/ })).toBeInTheDocument()
    expect(screen.getByText(/No source spans attached yet/)).toBeInTheDocument()
  })

  it("saves user interpretation and structured thesis lists", async () => {
    const user = userEvent.setup()
    render(<DecisionCenter initialTicker="NVDA" />)

    await screen.findByRole("heading", { name: "NVIDIA Corporation" })
    await user.type(screen.getByLabelText("Thesis rationale"), "Demand remains durable, subject to evidence.")
    await user.type(screen.getByLabelText("Major risks"), "Customer concentration")
    await user.type(screen.getByLabelText("Catalysts"), "New product cycle")
    await user.click(screen.getByRole("button", { name: "Save Thesis Version" }))

    await waitFor(() => expect(saveThesisCard).toHaveBeenCalledWith("NVDA", expect.objectContaining({
      status: "watch",
      major_risks: ["Customer concentration"],
      catalysts: ["New product cycle"],
      rationale: "Demand remains durable, subject to evidence.",
    })))
  })
})
