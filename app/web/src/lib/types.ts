export type ParameterValue = number | boolean | string
export type ParameterMode = "fixed" | "adaptive" | "search"
export type Timeframe = "1mo" | "3mo" | "6mo" | "1y" | "2y"

export interface ParameterSpec {
  key: string
  label: string
  parameter_type: "integer" | "number" | "boolean" | "choice"
  unit: string
  default: ParameterValue
  minimum: number | null
  maximum: number | null
  step: number | null
  choices: string[]
  adaptive_modes: string[]
  searchable: boolean
}

export interface StrategyTemplate {
  template_id: string
  family: string
  version: number
  name: string
  description: string
  direction: "long" | "short"
  parameters: ParameterSpec[]
  required_datasets: Array<{ dataset: string; fields: string[]; point_in_time: boolean }>
  rule_graph: Record<string, unknown> & { kind?: string; average?: string }
}

export interface StrategyInstance {
  instance_id: string
  template_id: string
  template_version: number
  name: string
  description: string
  parameter_values: Record<string, ParameterValue>
  parameter_modes: Record<string, ParameterMode>
  risk: Record<string, number>
}

export interface CatalogueStrategy {
  id: string
  name: string
  description: string
  instruction: string
  provider: string
  family: string | null
  templateId: string | null
  templateVersion: number | null
  strategyJson: StrategyInstance | null
  updatedAt: string
}

export interface ExecutionAssumptions {
  initial_capital: number
  commission_bps: number
  slippage_bps: number
  annual_cash_rate: number
  signal_lag_sessions?: 1
  fill_price?: "next_open"
}

export interface ResearchDesign {
  ticker: string | null
  universe: string[]
  timeframe: Timeframe
  benchmark: string
  relative_strength_reference: "market" | "sector" | "custom"
  relative_strength_symbol: string | null
  execution: ExecutionAssumptions
}

export interface ValidationDesign {
  training_fraction: number
  final_test_fraction: number
  walk_forward_folds: number
}

export interface PricePoint {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  indicators: Record<string, number>
}

export interface MarketChartPoint extends PricePoint {
  periodStart: string
  periodEnd: string
  position?: number
  signalPosition?: number
  strategyEquity?: number
}

export interface Trade {
  status: "Closed" | "Open"
  side: "LONG" | "SHORT"
  entryDate: string
  entryPrice: number
  exitDate?: string | null
  asOfDate?: string
  exitPrice: number
  pnl: number
  pnlPercent: number
  barsHeld: number
  cost?: number
}

export interface BenchmarkMetric {
  totalReturn: number
  cagr: number
  maxDrawdown: number
  annualizedVolatility: number
}

export interface BacktestMetrics {
  totalReturn: number
  benchmarkReturn: number
  spyReturn?: number
  benchmarkReturns?: Record<string, number>
  excessReturn?: number
  excessReturns?: Record<string, number>
  cagr?: number
  maxDrawdown: number
  annualizedVolatility?: number
  sharpeRatio: number
  sortinoRatio?: number
  calmarRatio?: number
  exposure?: number
  turnover?: number
  timeUnderwater?: number
  trades: number
  openTrades: number
  winRate?: number
  profitFactor?: number | null
  averageTradePnl?: number
  averageTradeReturn?: number
  endingCapital?: number
  totalExecutionCosts?: number
  costSensitivity?: Array<{ totalCostBps: number; totalReturn: number }>
  benchmarkMetrics?: Record<string, BenchmarkMetric>
}

export interface EquityPoint extends PricePoint {
  strategy: number
  buyHold: number
  spy: number
  benchmarks: Record<string, number>
  position: number
  signalPosition: number
  fillPrice: number | null
  turnover: number
}

export interface BacktestResult {
  strategy: { name: string; description: string; parameters?: Record<string, unknown> }
  strategyYaml?: string
  metrics: BacktestMetrics
  verdict: { label: string; reason: string }
  explanation: string
  assumptions: ExecutionAssumptions
  executionModel: string
  evaluationPeriod: { start: string; end: string; sessions: number }
  benchmarks?: string[]
  regimes?: Array<{ regime: string; sessions: number; strategyReturn: number; averageExposure: number }>
  chart: EquityPoint[]
  marketChart: MarketChartPayload | null
  trades: Trade[]
  qualityWarnings?: string[]
}

export interface MarketChartPayload {
  defaultInterval: string
  intervals: Record<string, MarketChartPoint[]>
  indicatorSettings?: Record<string, Record<string, number>>
}

export interface ResearchRunResponse {
  run_id: string
  research_design: ResearchDesign
  data_snapshot: Record<string, unknown>
  results: BacktestResult
}

export interface ParameterSearchResponse {
  method: string
  objective?: string
  finalTestWasUntouched?: boolean
  bestParameters: Record<string, ParameterValue>
  attempts: Array<Record<string, unknown>>
  finalTest: BacktestResult
  finalTestStart: string
  trainingEnd: string
  developmentEnd?: string
  validationWindows?: Array<Record<string, unknown>>
  stabilityRegion?: Array<Record<string, ParameterValue>>
  deflatedSharpeProbability: number
  stableParameters: boolean
  performanceDecay: number
  overfittingWarning: string | null
  heatmap: {
    xParameter: string
    yParameter: string | null
    cells: Array<{ x: number | string; y: number | string | null; medianScore: number; trials: number }>
  }
}

export interface LegacyProposal {
  strategy: { name: string; description: string; parameters?: Record<string, unknown> }
  strategyYaml: string
  normalizedInstruction: string
  clarifications: string[]
  needsConfirmation: boolean
  existingStrategy: CatalogueStrategy | null
  provider: string
}

export interface DataStatus {
  source?: string
  status?: string
  observationTimestamp?: string
  knownAt?: string
  qualityWarnings?: string[]
}
