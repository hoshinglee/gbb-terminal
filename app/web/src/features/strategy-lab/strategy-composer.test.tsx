import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"

import { StrategyComposer } from "@/features/strategy-lab/strategy-composer"
import { ResearchWorkspaceProvider, useResearchWorkspace } from "@/features/strategy-lab/workspace"
import type { CatalogueStrategy, StrategyTemplate } from "@/lib/types"

const templates: StrategyTemplate[] = [
  {
    template_id: "sma-crossover",
    family: "Trend",
    version: 1,
    name: "SMA Crossover",
    description: "Enter on a fast and slow moving-average crossover.",
    direction: "long",
    parameters: [
      { key: "fast_window", label: "Fast SMA", parameter_type: "integer", unit: "Sessions", default: 10, minimum: 2, maximum: 50, step: 1, choices: [], adaptive_modes: [], searchable: true },
      { key: "slow_window", label: "Slow SMA", parameter_type: "integer", unit: "Sessions", default: 50, minimum: 10, maximum: 250, step: 5, choices: [], adaptive_modes: [], searchable: true },
    ],
    required_datasets: [],
    rule_graph: { kind: "crossover", average: "sma" },
  },
  {
    template_id: "rsi-mean-reversion",
    family: "Mean Reversion",
    version: 1,
    name: "RSI Mean Reversion",
    description: "Enter after an oversold RSI reading.",
    direction: "long",
    parameters: [
      { key: "window", label: "RSI Window", parameter_type: "integer", unit: "Sessions", default: 14, minimum: 2, maximum: 100, step: 1, choices: [], adaptive_modes: [], searchable: true },
      { key: "entry_level", label: "Oversold Entry", parameter_type: "number", unit: "", default: 30, minimum: 5, maximum: 45, step: 1, choices: [], adaptive_modes: [], searchable: true },
      { key: "exit_level", label: "Recovery Exit", parameter_type: "number", unit: "", default: 55, minimum: 45, maximum: 90, step: 1, choices: [], adaptive_modes: [], searchable: true },
    ],
    required_datasets: [],
    rule_graph: { kind: "threshold" },
  },
]

const savedRsi: CatalogueStrategy = {
  id: "saved-rsi",
  name: "RSI Recovery",
  description: "A saved RSI recovery configuration.",
  instruction: "",
  provider: "strategy_model_v2",
  family: "Mean Reversion",
  templateId: "rsi-mean-reversion",
  templateVersion: 1,
  strategyJson: {
    instance_id: "rsi-instance",
    template_id: "rsi-mean-reversion",
    template_version: 1,
    name: "RSI Recovery",
    description: "A saved RSI recovery configuration.",
    parameter_values: { window: 21, entry_level: 28, exit_level: 52 },
    parameter_modes: { window: "fixed", entry_level: "fixed", exit_level: "fixed" },
    risk: {},
  },
  updatedAt: "2026-08-07T00:00:00",
}

function Harness() {
  const { dispatch } = useResearchWorkspace()
  return <><button onClick={() => dispatch({ type: "select-template", template: templates[0] })}>Load SMA Template</button><button onClick={() => dispatch({ type: "select-catalogue", strategy: savedRsi, template: templates[1] })}>Load RSI Catalogue</button><button onClick={() => dispatch({ type: "edit-instruction", instruction: "Long after a volume-confirmed breakout and exit below support." })}>Use Instruction</button><StrategyComposer templates={templates} onOpenCommand={() => undefined} /></>
}

describe("StrategyComposer selection state", () => {
  it("replaces template parameters when a catalogue strategy is loaded", async () => {
    const user = userEvent.setup()
    render(<ResearchWorkspaceProvider><Harness /></ResearchWorkspaceProvider>)
    await user.click(screen.getByRole("button", { name: "Load SMA Template" }))
    expect(screen.getByRole("button", { name: /Edit Fast SMA/ })).toHaveTextContent("10")
    await user.click(screen.getByRole("button", { name: "Load RSI Catalogue" }))
    expect(screen.queryByRole("button", { name: /Edit Fast SMA/ })).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Edit RSI Window/ })).toHaveTextContent("21")
    expect(screen.getByText("RSI Recovery")).toBeInTheDocument()
  })

  it("clears validated-template configuration when natural language takes over", async () => {
    const user = userEvent.setup()
    render(<ResearchWorkspaceProvider><Harness /></ResearchWorkspaceProvider>)
    await user.click(screen.getByRole("button", { name: "Load SMA Template" }))
    await user.click(screen.getByRole("button", { name: "Use Instruction" }))
    expect(screen.queryByRole("button", { name: /Edit Fast SMA/ })).not.toBeInTheDocument()
    expect(screen.getByRole("textbox")).toHaveValue("Long after a volume-confirmed breakout and exit below support.")
  })

  it("adds a visible trailing stop to a validated template", async () => {
    const user = userEvent.setup()
    render(<ResearchWorkspaceProvider><Harness /></ResearchWorkspaceProvider>)
    await user.click(screen.getByRole("button", { name: "Load SMA Template" }))
    await user.click(screen.getByRole("button", { name: "Add Trailing Stop" }))

    expect(screen.getByRole("button", { name: /Trailing Stop 8%/ })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Remove trailing stop" })).toBeInTheDocument()
  })
})
