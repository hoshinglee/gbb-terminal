import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { AppShell } from "@/components/app-shell"
import { ResearchContextBar } from "@/features/strategy-lab/research-context-bar"
import { ResearchWorkspaceProvider } from "@/features/strategy-lab/workspace"

describe("research canvas accessibility", () => {
  it("provides skip navigation and equivalent desktop and mobile lab links", () => {
    render(<AppShell activeLab="strategy"><div>Canvas content</div></AppShell>)

    expect(screen.getByRole("link", { name: "Skip To Research" })).toHaveAttribute("href", "#strategy-main")
    expect(screen.getByRole("main")).toHaveAttribute("id", "strategy-main")
    expect(screen.getAllByRole("link", { name: "Strategy Lab" })).toHaveLength(2)
    expect(screen.getAllByRole("link", { name: /^Option Lab/ })).toHaveLength(2)
    expect(screen.getAllByRole("link", { name: "Strategy Lab" })[0]).toHaveAttribute("aria-current", "page")
  })

  it("exposes the React Option Lab as the active laboratory", () => {
    render(<AppShell activeLab="options"><div>Option canvas</div></AppShell>)

    expect(screen.getByRole("main")).toHaveAttribute("id", "option-main")
    expect(screen.getAllByRole("link", { name: "Option Lab" })[0]).toHaveAttribute("aria-current", "page")
    expect(screen.getAllByRole("link", { name: "Option Lab" })[0]).toHaveAttribute("href", "/?lab=options")
  })

  it("exposes Stock Observatory and Market Pulse without legacy routing", () => {
    const { rerender } = render(<AppShell activeLab="stock"><div>Stock canvas</div></AppShell>)

    expect(screen.getByRole("main")).toHaveAttribute("id", "stock-main")
    expect(screen.getAllByRole("link", { name: "Stock Observatory" })[0]).toHaveAttribute("href", "/?lab=stock")
    expect(screen.getAllByRole("link", { name: "Stock Observatory" })[0]).toHaveAttribute("aria-current", "page")

    rerender(<AppShell activeLab="market"><div>Market canvas</div></AppShell>)
    expect(screen.getByRole("main")).toHaveAttribute("id", "market-main")
    expect(screen.getAllByRole("link", { name: "Market Pulse" })[0]).toHaveAttribute("href", "/?lab=market")
    expect(screen.getAllByRole("link", { name: "Market Pulse" })[0]).toHaveAttribute("aria-current", "page")
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
