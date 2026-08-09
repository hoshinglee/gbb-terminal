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

export type OptionType = "call" | "put"
export type PositionSide = "long" | "short"
export type OptionPositionKind =
  | "custom"
  | "long_call"
  | "long_put"
  | "short_call"
  | "short_put"
  | "covered_call"
  | "cash_secured_put"
  | "bull_call_spread"
  | "bear_call_spread"
  | "bull_put_spread"
  | "bear_put_spread"
  | "conversion"

export type OptionLifecycleEventType =
  | "hold"
  | "close"
  | "partial_close"
  | "roll_strike"
  | "roll_expiry"
  | "exercise"
  | "expire"
  | "early_assignment"
  | "expiry_assignment"
  | "buy_shares"
  | "sell_shares"
  | "add_leg"

export interface OptionPositionTemplate {
  kind: OptionPositionKind
  name: string
  category?: "Directional" | "Income" | "Defined Risk" | "Financing / Parity"
  description?: string
  capitalProfile?: string
  riskLabel?: string
  expiryPolicy?: string
  strikePolicy?: string
  shares?: number
  legs: Array<{ role?: string; optionType: OptionType; side: PositionSide }>
}

export interface OptionChainContract {
  contract: string
  strike: number
  last: number
  bid: number
  ask: number
  mid?: number
  spread?: number
  change?: number
  percentChange?: number
  volume: number
  openInterest: number
  iv: number
  inTheMoney?: boolean
  lastTradeAt?: string | null
  currency?: string
  quoteQuality?: "Two-Sided" | "Incomplete Quote"
}

export interface OptionChainResponse {
  expiration?: string
  defaultExpiration?: string
  expirations: string[]
  calls: OptionChainContract[]
  puts: OptionChainContract[]
  source?: string
  historicalStatus?: string
  dataStatus?: DataStatus
}

export interface OptionLeg {
  leg_id: string
  option_type: OptionType
  side: PositionSide
  strike: number
  expiration: string
  premium: number
  quantity: number
  implied_volatility: number
  multiplier: number
  contract_symbol?: string | null
  premium_source?: "manual" | "ask" | "bid" | "last" | "mid"
}

export interface OptionSimulationRequest {
  run_name?: string | null
  ticker: string
  underlying_price: number
  position_kind: OptionPositionKind
  legs: OptionLeg[]
  shares: number
  share_cost_basis: number | null
  interest_rate: number
  dividend_yield: number
  paths: number
  seed: number
  data_provenance?: Record<string, unknown>
}

export interface OptionPositionCreate extends OptionSimulationRequest {
  name: string
  research_run_id?: string | null
}

export interface OptionSimulationResult {
  runId: string
  createdAt: string
  modelVersion: string
  model: string
  comparisonModel: string
  historicalStatus: string
  assumptions: {
    interestRate: number
    dividendYield: number
    valuationDate: string
    contractMultiplier: number
  }
  limitations: string[]
  dataProvenance: Record<string, unknown>
  positionProfile: {
    shareOutlay: number
    longPremiumDebit: number
    shortPremiumCredit: number
    netCashAtEntry: number
    netCapitalCommitted: number
    netCreditReceived: number
    riskLabel: string
  }
  conversionAnalysis: null | {
    lockedTerminalProceeds: number
    netCapitalCommitted: number
    nominalProfit: number
    nominalReturnPercent: number
    holdingDays: number
    annualizedReturnPercent: number
    configuredCashRatePercent: number
    annualizedExcessVsCashPercent: number
    dividendYieldAssumptionPercent: number
    interpretation: string
  }
  managementPlaybook: {
    title: string
    riskLabel: string
    branches: Array<{
      id: string
      title: string
      trigger: string
      action: string
      eventType: string
      impact: string
      requiredCash?: number
      warnings: string[]
    }>
  }
  summary: {
    breakEvens: number[]
    maximumGain: number | "Unlimited"
    maximumLoss: number | "Unlimited"
    collateral: number
    assignmentExposure: number
  }
  greeks: Array<{
    legId: string
    optionType: OptionType
    side: PositionSide
    strike: number
    americanPrice: number
    blackScholesPrice: number
    probabilityInTheMoney: number
    delta: number
    gamma: number
    theta: number
    vega: number
  }>
  payoff: Array<{ underlyingPrice: number; pnl: number }>
  surface: Array<{ day: number; points: Array<{ underlyingPrice: number; pnl: number }> }>
  monteCarlo: Array<{
    path: number
    points: Array<{ day: number; underlyingPrice: number; positionPnl: number }>
  }>
}

export interface OptionPositionState {
  position_id: string
  name: string
  ticker: string
  position_kind: OptionPositionKind
  research_run_id?: string | null
  current_structure?: string
  status: "open" | "closed" | "expired" | "assigned" | "exercised"
  opened_at: string
  updated_at: string
  underlying_price: number
  cash: number
  shares: number
  share_cost_basis: number
  realized_pnl: number
  collateral: number
  legs: OptionLeg[]
  closed_quantities: Record<string, number>
}

export interface OptionLifecycleEvent {
  event_type: OptionLifecycleEventType
  underlying_price: number
  option_marks: Record<string, number>
  quantity: number | null
  leg_id: string | null
  new_strike: number | null
  new_expiration: string | null
  new_premium: number | null
  new_leg?: OptionLeg | null
  note: string
}

export interface OptionLedgerEvent {
  eventId: string
  eventNumber: number
  eventType: "opened" | OptionLifecycleEventType
  event: Record<string, unknown>
  stateAfter: OptionPositionState
  createdAt: string
}

export interface OptionPositionResponse {
  position: OptionPositionState
  events: OptionLedgerEvent[]
}

export interface OptionSimulationRunSummary {
  runId: string
  runName: string | null
  ticker: string
  positionKind: OptionPositionKind
  request: OptionSimulationRequest
  summary: OptionSimulationResult["summary"]
  modelVersion: string
  createdAt: string
}

export interface OptionSimulationRunDetail extends Omit<OptionSimulationRunSummary, "summary"> {
  result: Omit<OptionSimulationResult, "runId" | "createdAt" | "modelVersion">
}
