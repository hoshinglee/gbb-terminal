import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { AppShell } from "@/components/app-shell"
import { ResearchContextBar } from "@/features/strategy-lab/research-context-bar"
import { ResearchWorkspaceProvider } from "@/features/strategy-lab/workspace"

describe("research canvas accessibility", () => {
  it("provides skip navigation and equivalent desktop and mobile lab links", () => {
    render(<AppShell><div>Canvas content</div></AppShell>)

    expect(screen.getByRole("link", { name: "Skip To Research" })).toHaveAttribute("href", "#strategy-main")
    expect(screen.getByRole("main")).toHaveAttribute("id", "strategy-main")
    expect(screen.getAllByRole("link", { name: "Strategy Lab" })).toHaveLength(2)
    expect(screen.getAllByRole("link", { name: /^Option Lab/ })).toHaveLength(2)
    expect(screen.getAllByRole("link", { name: "Strategy Lab" })[0]).toHaveAttribute("aria-current", "page")
  })

  it("labels the compact research controls without relying on placeholders", () => {
    render(<ResearchWorkspaceProvider><ResearchContextBar running={false} onRun={vi.fn()} onOpenCommand={vi.fn()} /></ResearchWorkspaceProvider>)

    expect(screen.getByRole("region", { name: "Research controls" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Choose strategy/ })).toBeInTheDocument()
    expect(screen.getByLabelText("Research ticker")).toHaveValue("NVDA")
    expect(screen.getByRole("combobox", { name: "Backtest window" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Run Research" })).toBeDisabled()
  })
})
