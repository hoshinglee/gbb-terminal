import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { PortfolioRiskSheet } from "@/features/portfolio/portfolio-risk-sheet"
import {
  loadPortfolioContext,
  savePortfolioContext,
  snapshotRiskPolicy,
} from "@/lib/api"
import type { PortfolioBundle } from "@/lib/types"

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>()
  return {
    ...original,
    createPortfolioPosition: vi.fn(),
    deletePortfolioPosition: vi.fn(),
    loadPortfolioContext: vi.fn(),
    savePortfolioContext: vi.fn(),
    saveRiskPolicy: vi.fn(),
    snapshotRiskPolicy: vi.fn(),
    updatePortfolioPosition: vi.fn(),
  }
})

const bundle: PortfolioBundle = {
  context: {
    context_id: "personal",
    investable_value: 500_000,
    liquid_cash: 150_000,
    base_currency: "USD",
    created_at: "2026-08-18T00:00:00",
    updated_at: "2026-08-18T00:00:00",
  },
  positions: [{
    position_id: "position-1",
    context_id: "personal",
    company_id: "company-nvda",
    company_name: "NVIDIA Corporation",
    ticker: "NVDA",
    shares: 100,
    cost_basis_per_share: 140,
    manual_market_value: 20_000,
    notes: "Manual context",
    identity_status: "resolved",
    created_at: "2026-08-18T00:00:00",
    updated_at: "2026-08-18T00:00:00",
  }],
  risk_policy: {
    policy_id: "policy-1",
    policy_key: "personal-default",
    version: 1,
    name: "Personal Risk Policy",
    normal_target_position_percent: 8,
    max_single_name_exposure_percent: 15,
    max_assignment_exposure_percent: 12,
    max_short_option_collateral_percent: 20,
    min_unencumbered_cash_reserve_percent: null,
    min_unencumbered_cash_reserve_amount: 80_000,
    portfolio_stress_loss_ceiling_percent: 25,
    supersedes_policy_id: null,
    created_at: "2026-08-18T00:00:00",
  },
}

describe("PortfolioRiskSheet", () => {
  beforeEach(() => {
    vi.mocked(loadPortfolioContext).mockResolvedValue(bundle)
    vi.mocked(savePortfolioContext).mockResolvedValue(bundle.context!)
    vi.mocked(snapshotRiskPolicy).mockResolvedValue({
      snapshot_id: "snapshot-12345678",
      policy_id: "policy-1",
      policy_key: "personal-default",
      policy_version: 1,
      policy: bundle.risk_policy!,
      created_at: "2026-08-18T00:00:00",
    })
  })

  it("shows the compact policy, resolved holding, and creates a snapshot", async () => {
    const user = userEvent.setup()
    render(<PortfolioRiskSheet />)

    await user.click(screen.getByRole("button", { name: "Portfolio & Risk" }))
    expect(await screen.findByText("$80,000")).toBeInTheDocument()
    expect(screen.getByText("-25%")).toBeInTheDocument()

    await user.click(screen.getByRole("tab", { name: /Holdings/ }))
    expect(screen.getByText("NVIDIA Corporation")).toBeInTheDocument()
    expect(screen.getByText("Identity Resolved")).toBeInTheDocument()

    await user.click(screen.getByRole("tab", { name: "Risk Policy" }))
    await user.click(screen.getByRole("button", { name: "Create Snapshot" }))
    expect(snapshotRiskPolicy).toHaveBeenCalledOnce()
  })

  it("saves capital without requiring a risk policy", async () => {
    const user = userEvent.setup()
    vi.mocked(loadPortfolioContext).mockResolvedValue({ context: null, positions: [], risk_policy: null })
    render(<PortfolioRiskSheet />)

    await user.click(screen.getByRole("button", { name: "Portfolio & Risk" }))
    await screen.findByText("Investable Portfolio Context")
    await user.type(screen.getByRole("spinbutton", { name: "Investable value" }), "250000")
    await user.type(screen.getByRole("spinbutton", { name: "Liquid cash" }), "100000")
    await user.click(screen.getByRole("button", { name: "Save Capital Context" }))

    await waitFor(() => expect(savePortfolioContext).toHaveBeenCalledWith({ investable_value: 250_000, liquid_cash: 100_000, base_currency: "USD" }))
  })
})
