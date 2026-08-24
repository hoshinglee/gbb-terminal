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

export interface PortfolioContextInput {
  investable_value: number
  liquid_cash: number
  base_currency: "USD"
}

export interface PortfolioContextRecord extends PortfolioContextInput {
  context_id: string
  created_at: string
  updated_at: string
}

export interface PortfolioPositionInput {
  ticker: string
  shares: number
  cost_basis_per_share: number
  manual_market_value: number | null
  notes: string
}

export interface PortfolioPosition extends PortfolioPositionInput {
  position_id: string
  context_id: string
  company_id: string | null
  company_name: string | null
  identity_status: "resolved" | "unresolved"
  created_at: string
  updated_at: string
}

export interface RiskPolicyInput {
  name: string
  normal_target_position_percent: number
  max_single_name_exposure_percent: number
  max_assignment_exposure_percent: number
  max_short_option_collateral_percent: number
  min_unencumbered_cash_reserve_percent: number | null
  min_unencumbered_cash_reserve_amount: number | null
  portfolio_stress_loss_ceiling_percent: number
}

export interface RiskPolicy extends RiskPolicyInput {
  policy_id: string
  policy_key: string
  version: number
  supersedes_policy_id: string | null
  created_at: string
}

export interface RiskPolicySnapshot {
  snapshot_id: string
  policy_id: string
  policy_key: string
  policy_version: number
  policy: RiskPolicy
  created_at: string
}

export interface PortfolioBundle {
  context: PortfolioContextRecord | null
  positions: PortfolioPosition[]
  risk_policy: RiskPolicy | null
}

export type ThesisStatus = "watch" | "insufficient_evidence" | "ready_for_position_planning" | "invalidated"
export type EvidenceStrength = "unknown" | "limited" | "moderate" | "strong"
export type MoatAssessment = "unknown" | "none" | "limited" | "moderate" | "strong"

export interface ThesisEvidenceLinkInput {
  span_id: string
  role: "support" | "context" | "contradiction"
  interpretation: string
}

export interface ThesisEvidenceReference extends ThesisEvidenceLinkInput {
  document_id: string
  source: string
  source_url: string
  document_title: string | null
  exact_text: string
  known_at: string
}

export interface ThesisCardInput {
  status: ThesisStatus
  evidence_strength: EvidenceStrength
  moat_assessment: MoatAssessment
  major_risks: string[]
  catalysts: string[]
  invalidation_criteria: string[]
  rationale: string
  evidence_links: ThesisEvidenceLinkInput[]
}

export interface ThesisCard extends Omit<ThesisCardInput, "evidence_links"> {
  thesis_id: string
  thesis_key: string
  company_id: string
  ticker: string
  company_name: string
  version: number
  evidence_references: ThesisEvidenceReference[]
  supersedes_thesis_id: string | null
  created_at: string
}

export interface PositionIntentInput {
  target_amount: number | null
  target_percent: number | null
  maximum_amount: number | null
  maximum_percent: number | null
  current_price: number | null
}

export interface PositionIntent {
  intent_id: string
  intent_key: string
  company_id: string
  ticker: string
  company_name: string
  version: number
  target_amount: number | null
  target_percent: number | null
  maximum_amount: number | null
  maximum_percent: number | null
  current_exposure_amount: number | null
  current_exposure_percent: number | null
  current_shares: number
  investable_value: number | null
  is_complete: boolean
  warnings: string[]
  supersedes_intent_id: string | null
  created_at: string
}

export type DecisionObjective = "ownership_now" | "accumulate_lower" | "income" | "defined_risk_upside"

export interface InstrumentExpression {
  kind: "direct_shares" | "option"
  name: string
  share_quantity: number | null
  share_price: number | null
  option_position: OptionSimulationRequest | null
  source_candidate_id: string | null
}

export interface PolicyCheck {
  key: string
  label: string
  status: "pass" | "warn" | "fail" | "incomplete" | "not_applicable"
  actual: number | null
  limit: number | null
  unit: "percent" | "usd" | "shares" | "none"
  arithmetic: string
  reason: string
}

export interface InstrumentFitResult {
  candidate_id: string
  expression: InstrumentExpression
  overall_status: "pass" | "warn" | "fail" | "incomplete"
  fit_label: string
  objective_fit: string
  current_exposure: number | null
  target_exposure: number | null
  maximum_exposure: number | null
  capital_required: number | null
  collateral_required: number | null
  assignment_obligation: number
  effective_acquisition_basis: number | null
  existing_shares: number
  shares_after_assignment: number | null
  post_assignment_exposure: number | null
  portfolio_footprint_percent: number | null
  cash_remaining: number | null
  maximum_loss: number | "Unlimited" | null
  break_evens: number[]
  sizing_flexibility: string
  upside_character: string
  downside_character: string
  checks: PolicyCheck[]
  arithmetic: string[]
  warnings: string[]
}

export interface ExpressionComparison {
  ticker: string
  company_id: string
  objective: DecisionObjective
  generated_at: string
  position_intent: PositionIntent
  candidates: InstrumentFitResult[]
  eligibility_notes: string[]
  warnings: string[]
  strategy_lab_url: string
  option_lab_url: string
}

export interface EntryTrancheInput {
  label: string
  allocation_amount: number | null
  allocation_percent: number | null
  status: "planned" | "available" | "used" | "skipped" | "cancelled"
  trigger: string
  rationale: string
  preferred_entry_price: number | null
  maximum_acceptable_execution_price: number | null
}

export interface EntryTranche extends EntryTrancheInput {
  tranche_id: string
  resolved_allocation_amount: number
  resolved_allocation_percent: number | null
}

export interface EntryPlanInput {
  position_intent_id: string
  expression: InstrumentExpression
  execution_mode: "patient" | "establish_exposure" | "catalyst"
  escape_plan: "abandon_wait" | "reassess_thesis" | "allow_starter_within_maximum"
  tranches: EntryTrancheInput[]
  notes: string
}

export interface EntryPlan extends Omit<EntryPlanInput, "tranches"> {
  entry_plan_id: string
  plan_key: string
  company_id: string
  ticker: string
  company_name: string
  version: number
  target_allocation_amount: number
  allocated_amount: number
  unallocated_reserve: number
  tranches: EntryTranche[]
  supersedes_entry_plan_id: string | null
  created_at: string
}

export interface StressScenarioInput {
  underlying_change_percent: number
  iv_change_percent?: number
  days_forward?: number
}

export interface StressScenarioResult {
  scenario: Required<StressScenarioInput>
  stressed_underlying_price: number
  position_pnl: number
  portfolio_pnl_percent: number | null
  post_stress_single_name_percent: number | null
  cash_remaining: number | null
  assignment_obligation: number
  collateral_exposure: number
  checks: PolicyCheck[]
  assumptions: string[]
  warnings: string[]
}

export interface StressTestResult {
  ticker: string
  expression: InstrumentExpression
  generated_at: string
  scenarios: StressScenarioResult[]
  limitations: string[]
}

export interface ProcessReview {
  thesis_evidence_sufficient: "yes" | "no" | "not_applicable" | "unreviewed"
  position_inside_risk_budget: "yes" | "no" | "not_applicable" | "unreviewed"
  instrument_fit_intended_exposure: "yes" | "no" | "not_applicable" | "unreviewed"
  execution_followed_plan: "yes" | "no" | "not_applicable" | "unreviewed"
  exit_followed_rule: "yes" | "no" | "not_applicable" | "unreviewed"
  process_quality: "good" | "poor" | "mixed" | "unreviewed"
  notes: string
}

export interface LaterOutcome {
  as_of: string
  outcome: "favorable" | "unfavorable" | "neutral" | "unavailable"
  return_percent: number | null
  description: string
}

export type DecisionState = "planned" | "entered" | "partially_entered" | "missed" | "cancelled" | "invalidated" | "closed" | "passed"
export type DecisionType = "ownership" | "accumulation" | "income" | "defined_risk" | "risk_reduction" | "pass"

export interface DecisionJournalRecord {
  decision_id: string
  revision: number
  company_id: string
  ticker: string
  company_name: string
  decision_type: DecisionType
  state: DecisionState
  thesis_snapshot: ThesisCard | null
  risk_policy_snapshot: RiskPolicy | null
  position_intent_snapshot: PositionIntent | null
  expression_snapshot: InstrumentExpression | null
  entry_plan_snapshot: EntryPlan | null
  rationale: string
  actual_execution: Record<string, unknown>
  process_review: ProcessReview
  later_outcome: LaterOutcome | null
  process_outcome_classification: string | null
  option_position_id: string | null
  created_at: string
  updated_at: string
}

export interface DecisionCenterWorkspace {
  company_id: string
  ticker: string
  company_name: string
  thesis: ThesisCard | null
  position_intent: PositionIntent | null
  entry_plans: EntryPlan[]
  decisions: DecisionJournalRecord[]
  risk_policy: RiskPolicy | null
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

export type SignalRuleValue = number | string | boolean | null

export interface SignalTransition {
  signalDate: string
  executionDate: string | null
  fromState: string
  toState: string
  executionPrice: number | null
  pendingAtNextOpen: boolean
  reason: string
  ruleValues: Record<string, SignalRuleValue>
}

export interface CurrentSignal {
  targetState: string
  executedState: string
  signalPosition: number
  executedPosition: number
  observationDate: string
  pendingAtNextOpen: boolean
  executionTiming: string
  entryCriteria: string
  exitCriteria: string
  entryMatched: boolean | null
  exitMatched: boolean | null
  reason: string
  ruleValues: Record<string, SignalRuleValue>
  latestTransition: SignalTransition | null
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
  currentSignal?: CurrentSignal
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
  dataset?: string
  symbol?: string
  source?: string
  status?: string
  observationTimestamp?: string
  knownAt?: string
  retrievedAt?: string
  qualityWarnings?: string[]
  remainingQuota?: number | null
  cached?: boolean
}

export interface StockQuote {
  symbol: string
  price: number
  change: number
  changePercent: number
  periodReturn: number
  updatedAt?: string | null
  dataStatus: DataStatus
}

export interface StockOverviewResponse {
  quote: StockQuote
  marketChart: MarketChartPayload
  period: string
}

export interface MarketOverviewRow {
  symbol: string
  name: string
  price: number | null
  change: number | null
  changePercent: number | null
  periodReturn: number | null
  relativeStrength: number | null
  dataStatus: DataStatus
  available: boolean
}

export interface DataProviderStatus {
  provider: string
  configured: boolean
  status: string
}

export interface MarketOverviewResponse {
  benchmark: MarketOverviewRow
  sectors: MarketOverviewRow[]
  macro: MarketOverviewRow[]
  providers: DataProviderStatus[]
  generatedAt: string
}

export type OptionType = "call" | "put"
export type PositionSide = "long" | "short"
export type OptionOutlook = "bullish" | "bearish" | "neutral"
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

export interface OptionPlanRequest {
  ticker: string
  outlook: OptionOutlook
  target_date: string
  target_price?: number | null
  target_price_low?: number | null
  target_price_high?: number | null
  shares_owned: number
  acquiring_shares_acceptable: boolean
  maximum_loss?: number | null
  capital_budget?: number | null
  interest_rate: number
  dividend_yield: number
}

export interface OptionPlanQuote {
  legId: string
  contractSymbol?: string | null
  optionType: OptionType
  side: PositionSide
  strike: number
  bid: number
  ask: number
  last: number
  spread: number
  spreadPercent: number | null
  quoteQuality: "Two-Sided" | "Incomplete Quote"
  premiumUsed: number
  premiumSource: "manual" | "ask" | "bid" | "last" | "mid"
  impliedVolatility: number
  volume: number
  openInterest: number
  lastTradeAt?: string | null
}

export interface OptionPlanCandidate {
  candidateId: string
  name: string
  positionKind: OptionPositionKind
  tradeoff: string
  position: OptionSimulationRequest
  expiration: string
  strikes: number[]
  netDebit: number
  netCredit: number
  capitalRequired: number
  collateral: number
  maximumLoss: number | "Unlimited"
  maximumGain: number | "Unlimited"
  profitCharacter: string
  breakEvens: number[]
  greeks: { delta: number; gamma: number; theta: number; vega: number }
  quotes: OptionPlanQuote[]
  quoteQuality: "Two-Sided" | "Incomplete Quote"
  withinBudget: boolean
  warnings: string[]
}

export interface OptionPlanResult {
  ticker: string
  outlook: OptionOutlook
  targetDate: string
  underlyingPrice: number
  expiration: string
  generatedAt: string
  candidates: OptionPlanCandidate[]
  earningsContext: null | {
    historicalMedianAbsoluteMovePercent: number | null
    sampleSize: number
    asOf: string
    eventSource: string
    priceSource: string
    warnings: string[]
    interpretation: string
  }
  impliedMoveContext: null | {
    movePercent: number
    straddlePrice: number
    strike: number
    expiration: string
    quoteMethod: string
    interpretation: string
  }
  dataProvenance: DataStatus
  warnings: string[]
  limitations: string[]
}

export interface OptionScenarioRequest {
  position: OptionSimulationRequest
  scenario_price: number
  scenario_date: string
}

export interface OptionScenarioResult {
  ticker: string
  positionKind: OptionPositionKind
  scenarioPrice: number
  scenarioDate: string
  modeledPositionValue: number
  modeledOptionValue: number
  modeledShareValue: number
  pnl: number
  pnlPercent: number | null
  breakEvens: number[]
  breakEvenRelation: string
  remainingDays: number
  greeks: { delta: number; gamma: number; theta: number; vega: number }
  assumptions: {
    model: string
    interestRate: number
    dividendYield: number
    impliedVolatilities: number[]
    contractMultiplier: number
  }
  dataProvenance: Record<string, unknown>
  warnings: string[]
}

export interface CompanyReference {
  companyId: string
  cik: string
  legalName: string
  primaryTicker: string | null
  exchange: string | null
  status: string
}

export interface CompanyOverview extends CompanyReference {
  apiVersion: "v3"
  asOf: string | null
  sector: string | null
  industry: string | null
  fiscalYearEnd: string | null
  securities: Array<{
    securityId: string
    ticker: string
    exchange: string | null
    validFrom: string
    validTo: string | null
    isPrimary: boolean
    status: string
    provenance: {
      source: string
      dataset: string
      observationTimestamp: string
      knownAt: string
      retrievedAt: string
      status: string
      qualityWarnings: string[]
      cached: boolean
    }
  }>
  provenance: {
    source: string
    dataset: string
    observationTimestamp: string
    knownAt: string
    retrievedAt: string
    status: string
    qualityWarnings: string[]
    cached: boolean
  }
}

export interface CompanyMetric {
  metricId: string
  label: string
  value: number | null
  unit: string
  periodKind: "annual" | "quarterly" | "ttm"
  periodStart: string | null
  periodEnd: string
  fiscalYear: number | null
  fiscalPeriod: string | null
  definitionVersion: string
  derived: boolean
  sourceFactIds: string[]
  warnings: string[]
}

export interface CompanyMetricsResponse {
  apiVersion: "v3"
  company: CompanyReference
  periodKind: "annual" | "quarterly" | "ttm"
  asOf: string
  definitionVersion: string
  metrics: CompanyMetric[]
  warnings: string[]
}

export type ValuationStatus = "available" | "nm" | "unavailable"

export interface ValuationPoint {
  valuationDate: string
  metricId: string
  label: string
  value: number | null
  unit: string
  status: ValuationStatus
  price: number
  marketCap: number | null
  enterpriseValue: number | null
  denominatorValue: number | null
  denominatorMetric: string
  fundamentalPeriodEnd: string | null
  fundamentalKnownAt: string | null
  sourceFactIds: string[]
  priceSource: string
  warnings: string[]
}

export interface ValuationStatistics {
  metricId: string
  label: string
  unit: string
  status: ValuationStatus
  current: number | null
  percentile: number | null
  median: number | null
  minimum: number | null
  maximum: number | null
  zScore: number | null
  sampleSize: number
}

export interface HistoricalValuationResponse {
  apiVersion: "v3"
  company: CompanyReference
  frequency: "daily" | "weekly"
  startDate: string
  endDate: string
  asOf: string
  engineVersion: string
  history: Record<string, ValuationPoint[]>
  statistics: Record<string, ValuationStatistics>
  warnings: string[]
  provenance: {
    priceSource: string
    priceDataset: string
    fundamentalSource: string
    fundamentalDataset: string
    asOf: string
    engineVersion: string
    sourceFactIds: string[]
  }
}

export interface EarningsReportedMetric {
  metricId: string
  label: string
  value: number | null
  unit: string
  periodEnd: string
  sourceFactIds: string[]
  warnings: string[]
}

export interface EarningsEvent {
  eventId: string
  companyId: string
  cik: string
  ticker: string
  fiscalYear: number | null
  fiscalPeriod: string | null
  periodEnd: string
  announcementAt: string | null
  announcementDate: string
  session: "before_open" | "after_close" | "intraday" | "unknown"
  timingQuality: "exact" | "date_only"
  evidence: {
    source: string
    dataset: string
    accessionNumber: string
    filingForm: string
    filingUrl: string
    filedDate: string
    knownAt: string
    sourceFactIds: string[]
  }
  reportedMetrics: Record<string, EarningsReportedMetric>
  guidanceMetadata: Record<string, unknown>
  modelVersion: string
  warnings: string[]
}

export interface EarningsReactionWindow {
  window: string
  endSession: string | null
  stockReturn: number | null
  benchmarkReturn: number | null
  benchmarkAdjustedReturn: number | null
  status: string
}

export interface EarningsReactionPathPoint {
  relativeSession: number
  sessionDate: string
  close: number
  cumulativeReturn: number
  benchmarkAdjustedReturn: number | null
  volume: number | null
}

export interface EarningsReaction {
  eventId: string
  benchmarkTicker: string
  anchorSession: string | null
  priorSession: string | null
  openingGap: number | null
  abnormalVolume: number | null
  volumePercentile: number | null
  windows: Record<string, EarningsReactionWindow>
  path: EarningsReactionPathPoint[]
  engineVersion: string
  warnings: string[]
}

export interface EarningsEventAnalysis {
  event: EarningsEvent
  reaction: EarningsReaction
}

export interface EarningsHistoryResponse {
  apiVersion: "v3"
  company: CompanyReference
  benchmarkTicker: string
  asOf: string
  events: EarningsEventAnalysis[]
  aggregate: {
    sampleSize: number
    typicalAbsoluteEventMove: number | null
    positiveReactionFrequency: number | null
    medianD5Return: number | null
    medianD20Return: number | null
    eventMoveMinimum: number | null
    eventMoveMaximum: number | null
    excludedEvents: number
  }
  warnings: string[]
  provenance: {
    eventSource: string
    eventDataset: string
    priceSource: string
    asOf: string
    eventModelVersion: string
    reactionEngineVersion: string
    sourceFactIds: string[]
  }
}

export type EvidenceRole = "support" | "context" | "contradiction"

export interface EvidenceDocumentSummary {
  documentId: string
  source: string
  dataset: string
  documentType: string
  externalId: string
  version: number
  title: string | null
  form: string | null
  accessionNumber: string | null
  sourceUrl: string
  filedAt: string | null
  publishedAt: string | null
  knownAt: string
  retrievedAt: string
  parseStatus: string
  qualityWarnings: string[]
}

export interface EvidenceSpanSummary {
  spanId: string
  documentId: string
  exactText: string
  section: string | null
  pageNumber: number | null
  startOffset: number | null
  endOffset: number | null
  extractionMethod: string
  extractedAt: string
}

export interface SourceEvidence {
  role: EvidenceRole
  linkedAt: string
  document: EvidenceDocumentSummary
  span: EvidenceSpanSummary
}

export type RelationshipType = "supplier" | "customer" | "manufacturer_foundry" | "distributor" | "strategic_partner" | "competitor" | "customer_concentration" | "supplier_concentration"
export type RelationshipDirection = "upstream" | "downstream" | "bidirectional" | "market"
export type RelationshipConfidence = "disclosed" | "strongly_inferred" | "inferred"

export interface RelationshipEdge {
  relationshipId: string
  sourceCompanyId: string
  normalizedCounterpartyName: string
  rawCounterpartyName: string
  relationshipType: RelationshipType
  direction: RelationshipDirection
  modelVersion: string
  createdAt: string
}

export interface RelationshipObservation {
  observationId: string
  relationshipId: string
  targetCompanyId: string | null
  exposureValue: number | null
  exposureUnit: string | null
  validFrom: string | null
  validTo: string | null
  knownAt: string
  extractionMethod: string
  confidence: RelationshipConfidence
  observationKind: "extracted" | "human_override"
  supersedesObservationId: string | null
  correctionNote: string | null
  createdAt: string
}

export interface CompanyRelationship {
  edge: RelationshipEdge
  observation: RelationshipObservation
  sourceCompany: CompanyReference
  targetCompany: CompanyReference | null
  perspectiveDirection: RelationshipDirection
  evidence: SourceEvidence[]
}

export interface RelationshipNetworkResponse {
  apiVersion: "v3"
  company: CompanyReference
  asOf: string
  matchingRelationshipCount: number
  returnedRelationshipCount: number
  relationships: CompanyRelationship[]
  warnings: string[]
}

export interface RelationshipHistoryResponse {
  apiVersion: "v3"
  company: CompanyReference
  asOf: string
  edge: RelationshipEdge
  observations: RelationshipObservation[]
  evidence: Record<string, SourceEvidence[]>
}

export type OperatingMetricCategory = "segment" | "geography" | "kpi"
export type OperatingValueType = "currency" | "percentage" | "count" | "ratio" | "duration" | "other"

export interface OperatingMetricDefinition {
  definitionId: string
  category: OperatingMetricCategory
  definitionKey: string
  label: string
  measure: string
  unit: string
  valueType: OperatingValueType
  reportingBasis: string
  version: number
  validFrom: string | null
  validTo: string | null
  supersedesDefinitionId: string | null
  description: string | null
  knownAt: string
  extractionMethod: string
  modelVersion: string
  createdAt: string
}

export interface OperatingMetricObservation {
  observationId: string
  definitionId: string
  periodStart: string | null
  periodEnd: string
  fiscalYear: number | null
  fiscalPeriod: string | null
  value: number
  unit: string
  knownAt: string
  extractionMethod: string
  createdAt: string
}

export interface OperatingMetricPoint {
  observation: OperatingMetricObservation
  mixPercent: number | null
  growthPercent: number | null
  evidence: SourceEvidence[]
}

export interface OperatingMetricSeries {
  definition: OperatingMetricDefinition
  definitionEvidence: SourceEvidence[]
  points: OperatingMetricPoint[]
}

export interface OperatingIntelligenceResponse {
  apiVersion: "v3"
  company: CompanyReference
  asOf: string
  series: OperatingMetricSeries[]
  transitions: Array<{
    priorDefinitionId: string
    nextDefinitionId: string
    definitionKey: string
    priorLabel: string
    nextLabel: string
    priorReportingBasis: string
    nextReportingBasis: string
    knownAt: string
  }>
  warnings: string[]
}

export type GuidanceStatus = "open" | "delivered" | "partially_delivered" | "missed" | "withdrawn" | "superseded" | "unknown"
export type GuidanceValueKind = "numeric_range" | "numeric_point" | "qualitative"

export interface GuidanceStatement {
  statementId: string
  statementType: "financial_guidance" | "strategic_commitment" | "kpi_target" | "risk_constraint"
  topic: string
  metricId: string | null
  statementText: string
  valueKind: GuidanceValueKind
  comparison: "within_range" | "at_least" | "at_most" | "approximately" | "not_applicable"
  lowerBound: number | null
  upperBound: number | null
  pointValue: number | null
  unit: string | null
  applicablePeriodStart: string | null
  applicablePeriodEnd: string | null
  fiscalYear: number | null
  fiscalPeriod: string | null
  issuedAt: string
  knownAt: string
  extractionMethod: string
  revision: number
  supersedesStatementId: string | null
  modelVersion: string
  createdAt: string
}

export interface GuidanceEvaluation {
  evaluationId: string
  statementId: string
  status: GuidanceStatus
  evaluatedAt: string
  knownAt: string
  method: "system" | "rule_based" | "manual" | "interpretive"
  actualValue: number | null
  actualUnit: string | null
  sourceFactIds: string[]
  resultingStatementId: string | null
  note: string | null
  createdAt: string
}

export interface GuidanceRecord {
  statement: GuidanceStatement
  revisionDirection: "initial" | "raised" | "cut" | "reaffirmed" | "changed"
  status: GuidanceStatus
  evaluations: GuidanceEvaluation[]
  statementEvidence: SourceEvidence[]
  evaluationEvidence: Record<string, SourceEvidence[]>
}

export interface GuidanceHistoryResponse {
  apiVersion: "v3"
  company: CompanyReference
  asOf: string
  records: GuidanceRecord[]
  warnings: string[]
}

export type IntelligenceRefreshStatus = "running" | "completed" | "partial" | "failed" | "cancelled"
export type IntelligenceCoverageStatus = "populated" | "no_disclosure" | "parser_failed" | "extraction_failed" | "provider_failed" | "unsupported_format" | "unavailable"

export interface IntelligenceModuleCoverage {
  module: string
  status: IntelligenceCoverageStatus
  recordCount: number
  evidenceSpanCount: number
  message: string
}

export interface IntelligenceRefreshItem {
  itemId: string
  refreshId: string
  externalId: string
  sourceUrl: string | null
  accessionNumber: string | null
  form: string | null
  status: "discovered" | "unchanged" | "downloaded" | "parsed" | "no_disclosure" | "parse_failed" | "extraction_failed" | "provider_failed" | "unsupported_format"
  documentId: string | null
  reason: string | null
  createdAt: string
}

export interface IntelligenceRefreshSummary {
  refreshId: string
  companyId: string
  ticker: string
  status: IntelligenceRefreshStatus
  startedAt: string
  completedAt: string | null
  documentsDiscovered: number
  documentsDownloaded: number
  documentsUnchanged: number
  documentsParsed: number
  documentsFailed: number
  relationshipCount: number
  operatingObservationCount: number
  guidanceStatementCount: number
  coverage: IntelligenceModuleCoverage[]
  items: IntelligenceRefreshItem[]
  warnings: string[]
  modelVersion: string
}

export interface IntelligenceSourceHealthResponse {
  apiVersion: "v3"
  companyId: string
  ticker: string
  lastRefresh: IntelligenceRefreshSummary | null
  documentCount: number
  parsedDocumentCount: number
  failedDocumentCount: number
  coverage: IntelligenceModuleCoverage[]
  warnings: string[]
}

export interface LocalIntelligenceJob {
  jobId: string
  jobType: "intelligence_refresh"
  status: "running" | "completed" | "failed" | "cancelled"
  progress: number
  request: Record<string, unknown>
  result: IntelligenceRefreshSummary | null
  error: string | null
  cancelRequested: boolean
  createdAt: string
  updatedAt: string
}

export type UniverseRefreshStatus = "running" | "completed" | "partial" | "failed" | "cancelled"
export type UniverseItemStatus = "queued" | "running" | "completed" | "partial" | "failed" | "skipped" | "cancelled"

export interface UniverseSnapshotSummary {
  snapshotId: string
  universeKey: "sp500"
  version: number
  asOfDate: string
  source: string
  sourceUrl: string
  knownAt: string
  retrievedAt: string
  constituentCount: number
  qualityWarnings: string[]
}

export interface UniverseRefreshSummary {
  refreshId: string
  universeKey: "sp500"
  snapshotId: string
  status: UniverseRefreshStatus
  profile: string
  totalCount: number
  completedCount: number
  partialCount: number
  skippedCount: number
  failedCount: number
  cancelledCount: number
  warnings: string[]
  startedAt: string
  completedAt: string | null
}

export interface UniverseStatusResponse {
  apiVersion: "v3"
  universeKey: "sp500"
  snapshot: UniverseSnapshotSummary | null
  latestRefresh: UniverseRefreshSummary | null
  cachedCount: number
  completedCount: number
  partialCount: number
  failedCount: number
  unavailableCount: number
  sectorCounts: Record<string, number>
  warnings: string[]
}

export interface SectorConstituentResearch {
  symbol: string
  companyName: string
  sector: string
  subIndustry: string
  companyId: string | null
  price: number | null
  dailyChangePercent: number | null
  marketCap: number | null
  marketCapSource: string
  dataStatus: string
  observationTimestamp: string | null
  knownAt: string | null
  qualityWarnings: string[]
}

export interface SectorConstituentSnapshot {
  apiVersion: "v3"
  universeKey: "sp500"
  snapshotId: string
  sectorSymbol: string
  sectorName: string
  constituentCount: number
  availableCount: number
  constituents: SectorConstituentResearch[]
  gainers: SectorConstituentResearch[]
  losers: SectorConstituentResearch[]
  unavailable: SectorConstituentResearch[]
  generatedAt: string
  warnings: string[]
}

export interface LocalUniverseJob {
  jobId: string
  jobType: "sp500_universe_refresh"
  status: "running" | "completed" | "failed" | "cancelled"
  progress: number
  request: Record<string, unknown>
  result: UniverseRefreshSummary | null
  error: string | null
  cancelRequested: boolean
  createdAt: string
  updatedAt: string
}
