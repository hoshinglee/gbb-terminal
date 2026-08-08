import { createContext, type Dispatch, type ReactNode, useContext, useMemo, useReducer } from "react"

import type {
  BacktestResult,
  CatalogueStrategy,
  ParameterMode,
  ParameterSearchResponse,
  ParameterValue,
  ResearchDesign,
  StrategyInstance,
  StrategyTemplate,
  Timeframe,
  ValidationDesign,
} from "@/lib/types"

export type StrategySelection =
  | { kind: "none" }
  | { kind: "instruction"; instruction: string }
  | { kind: "template"; template: StrategyTemplate; instance: StrategyInstance; origin: "template" | "catalogue" }
  | { kind: "catalogue"; strategy: CatalogueStrategy }

export interface SearchRange {
  minimum: number
  maximum: number
}

export interface WorkspaceState {
  selection: StrategySelection
  ticker: string
  universe: string
  timeframe: Timeframe
  benchmark: string
  commissionBps: number
  slippageBps: number
  relativeStrengthReference: "market" | "sector" | "custom"
  relativeStrengthSymbol: string
  validation: ValidationDesign
  ranges: Record<string, SearchRange>
  result: BacktestResult | null
  search: ParameterSearchResponse | null
  runLabel: string
}

type WorkspaceAction =
  | { type: "select-template"; template: StrategyTemplate }
  | { type: "select-catalogue"; strategy: CatalogueStrategy; template?: StrategyTemplate }
  | { type: "edit-instruction"; instruction: string }
  | { type: "update-parameter"; key: string; value: ParameterValue }
  | { type: "update-parameter-mode"; key: string; mode: ParameterMode }
  | { type: "update-risk"; key: string; value: number | null }
  | { type: "update-range"; key: string; range: SearchRange }
  | { type: "update-context"; field: "ticker" | "universe" | "benchmark" | "relativeStrengthSymbol"; value: string }
  | { type: "update-timeframe"; value: Timeframe }
  | { type: "update-cost"; field: "commissionBps" | "slippageBps"; value: number }
  | { type: "update-relative-reference"; value: WorkspaceState["relativeStrengthReference"] }
  | { type: "update-validation"; field: keyof ValidationDesign; value: number }
  | { type: "set-result"; result: BacktestResult; search?: ParameterSearchResponse | null; label: string }

const initialState: WorkspaceState = {
  selection: { kind: "none" },
  ticker: "NVDA",
  universe: "NVDA, MSFT, AAPL, AMZN, META",
  timeframe: "1y",
  benchmark: "SPY",
  commissionBps: 0,
  slippageBps: 0,
  relativeStrengthReference: "market",
  relativeStrengthSymbol: "",
  validation: { training_fraction: 0.6, final_test_fraction: 0.2, walk_forward_folds: 3 },
  ranges: {},
  result: null,
  search: null,
  runLabel: "",
}

function instanceFromTemplate(template: StrategyTemplate, selected?: StrategyInstance): StrategyInstance {
  return {
    instance_id: selected?.instance_id || globalThis.crypto?.randomUUID?.() || `strategy-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    template_id: template.template_id,
    template_version: template.version,
    name: selected?.name || template.name,
    description: selected?.description || template.description,
    parameter_values: Object.fromEntries(template.parameters.map((parameter) => [parameter.key, selected?.parameter_values[parameter.key] ?? parameter.default])),
    parameter_modes: Object.fromEntries(template.parameters.map((parameter) => [parameter.key, selected?.parameter_modes[parameter.key] || "fixed"])),
    risk: selected?.risk || {},
  }
}

function workspaceReducer(state: WorkspaceState, action: WorkspaceAction): WorkspaceState {
  switch (action.type) {
    case "select-template":
      return { ...state, selection: { kind: "template", template: action.template, instance: instanceFromTemplate(action.template), origin: "template" }, ranges: {}, result: null, search: null }
    case "select-catalogue":
      if (action.strategy.strategyJson && action.template) {
        return { ...state, selection: { kind: "template", template: action.template, instance: instanceFromTemplate(action.template, action.strategy.strategyJson), origin: "catalogue" }, ranges: {}, result: null, search: null }
      }
      return { ...state, selection: { kind: "catalogue", strategy: action.strategy }, ranges: {}, result: null, search: null }
    case "edit-instruction":
      return { ...state, selection: action.instruction ? { kind: "instruction", instruction: action.instruction } : { kind: "none" }, ranges: {}, result: null, search: null }
    case "update-parameter":
      if (state.selection.kind !== "template") return state
      return { ...state, selection: { ...state.selection, instance: { ...state.selection.instance, parameter_values: { ...state.selection.instance.parameter_values, [action.key]: action.value } } }, result: null, search: null }
    case "update-parameter-mode":
      if (state.selection.kind !== "template") return state
      return { ...state, selection: { ...state.selection, instance: { ...state.selection.instance, parameter_modes: { ...state.selection.instance.parameter_modes, [action.key]: action.mode } } }, result: null, search: null }
    case "update-risk": {
      if (state.selection.kind !== "template") return state
      const risk = { ...state.selection.instance.risk }
      if (action.value === null) delete risk[action.key]
      else risk[action.key] = action.value
      return { ...state, selection: { ...state.selection, instance: { ...state.selection.instance, risk } }, result: null, search: null }
    }
    case "update-range":
      return { ...state, ranges: { ...state.ranges, [action.key]: action.range }, result: null, search: null }
    case "update-context":
      return { ...state, [action.field]: action.value, result: null, search: null }
    case "update-timeframe":
      return { ...state, timeframe: action.value, result: null, search: null }
    case "update-cost":
      return { ...state, [action.field]: action.value, result: null, search: null }
    case "update-relative-reference":
      return { ...state, relativeStrengthReference: action.value, result: null, search: null }
    case "update-validation":
      return { ...state, validation: { ...state.validation, [action.field]: action.value }, result: null, search: null }
    case "set-result":
      return { ...state, result: action.result, search: action.search || null, runLabel: action.label }
  }
}

const WorkspaceContext = createContext<{ state: WorkspaceState; dispatch: Dispatch<WorkspaceAction> } | null>(null)

export function ResearchWorkspaceProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(workspaceReducer, initialState)
  const value = useMemo(() => ({ state, dispatch }), [state])
  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>
}

export function useResearchWorkspace() {
  const workspace = useContext(WorkspaceContext)
  if (!workspace) throw new Error("useResearchWorkspace must be used inside ResearchWorkspaceProvider")
  return workspace
}

export function selectedResearchDesign(state: WorkspaceState): ResearchDesign {
  const portfolio = state.selection.kind === "template" && state.selection.template.rule_graph.kind === "ranked_portfolio"
  return {
    ticker: portfolio ? null : state.ticker.trim().toUpperCase() || null,
    universe: portfolio ? state.universe.split(",").map((symbol) => symbol.trim().toUpperCase()).filter(Boolean) : [],
    timeframe: state.timeframe,
    benchmark: state.benchmark.trim().toUpperCase() || "SPY",
    relative_strength_reference: state.relativeStrengthReference,
    relative_strength_symbol: state.relativeStrengthSymbol.trim().toUpperCase() || null,
    execution: {
      initial_capital: 100_000,
      commission_bps: state.commissionBps,
      slippage_bps: state.slippageBps,
      annual_cash_rate: 0,
    },
  }
}

export function selectedSearchRanges(state: WorkspaceState): Record<string, ParameterValue[]> {
  if (state.selection.kind !== "template") return {}
  return Object.fromEntries(Object.entries(state.selection.instance.parameter_modes).filter(([, mode]) => mode === "search").map(([key]) => {
    const parameter = state.selection.kind === "template" ? state.selection.template.parameters.find((item) => item.key === key) : undefined
    const value = Number(state.selection.kind === "template" ? state.selection.instance.parameter_values[key] : 0)
    const range = state.ranges[key] || { minimum: parameter?.minimum ?? value, maximum: parameter?.maximum ?? value }
    const step = parameter?.step || 1
    const values: number[] = []
    for (let current = range.minimum; current <= range.maximum + step / 10 && values.length < 30; current += step) values.push(Number(current.toFixed(8)))
    return [key, values]
  }))
}
