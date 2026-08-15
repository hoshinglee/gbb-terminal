import type {
  BacktestResult,
  CatalogueStrategy,
  DataStatus,
  LegacyProposal,
  MarketOverviewResponse,
  OptionChainResponse,
  OptionLifecycleEvent,
  OptionPositionCreate,
  OptionPositionResponse,
  OptionPositionState,
  OptionPositionTemplate,
  OptionSimulationRequest,
  OptionSimulationResult,
  OptionSimulationRunDetail,
  OptionSimulationRunSummary,
  ParameterSearchResponse,
  ParameterValue,
  PricePoint,
  ResearchDesign,
  ResearchRunResponse,
  StockOverviewResponse,
  StrategyInstance,
  StrategyTemplate,
  ValidationDesign,
  CompanyMetricsResponse,
  CompanyOverview,
  EarningsHistoryResponse,
  HistoricalValuationResponse,
  GuidanceHistoryResponse,
  OperatingIntelligenceResponse,
  RelationshipHistoryResponse,
  RelationshipNetworkResponse,
} from "@/lib/types"

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: init?.body ? { "Content-Type": "application/json", ...init.headers } : init?.headers,
  })
  const text = await response.text()
  const payload = text ? JSON.parse(text) as T & { detail?: string } : {} as T & { detail?: string }
  if (!response.ok) throw new ApiError(payload.detail || "The terminal API rejected this request.", response.status)
  return payload
}

export async function loadStrategySources() {
  const [templatePayload, cataloguePayload] = await Promise.all([
    request<{ templates: StrategyTemplate[] }>("/api/v2/strategy-templates"),
    request<{ strategies: CatalogueStrategy[] }>("/api/strategies"),
  ])
  return { templates: templatePayload.templates, catalogue: cataloguePayload.strategies }
}

export function loadChartData(ticker: string, period: string, indicators: string[]) {
  const parameters = new URLSearchParams({ ticker, period, indicators: indicators.join(",") })
  return request<{ symbol: string; period: string; dataStatus: DataStatus; chart: PricePoint[] }>(`/api/v2/chart-data?${parameters}`)
}

export function loadStockOverview(ticker: string, period: string) {
  const parameters = new URLSearchParams({ period })
  return request<StockOverviewResponse>(`/api/v2/stocks/${encodeURIComponent(ticker.trim().toUpperCase())}?${parameters}`)
}

export function loadMarketOverview() {
  return request<MarketOverviewResponse>("/api/v2/market-overview")
}

export function saveStrategy(strategy: StrategyInstance, originalInstruction = "") {
  return request<{ strategy: CatalogueStrategy }>("/api/v2/strategies", {
    method: "POST",
    body: JSON.stringify({ strategy, original_instruction: originalInstruction }),
  })
}

export function createResearchRun(strategy: StrategyInstance, researchDesign: ResearchDesign, validation: ValidationDesign) {
  return request<ResearchRunResponse>("/api/v2/research-runs", {
    method: "POST",
    body: JSON.stringify({ strategy, research_design: researchDesign, validation }),
  })
}

export function createParameterSearch(
  strategy: StrategyInstance,
  researchDesign: ResearchDesign,
  validation: ValidationDesign,
  ranges: Record<string, ParameterValue[]>,
) {
  return request<ParameterSearchResponse>("/api/v2/parameter-searches", {
    method: "POST",
    body: JSON.stringify({ strategy, research_design: researchDesign, validation, ranges, max_trials: 60 }),
  })
}

export function proposeInstruction(instruction: string) {
  return request<LegacyProposal>("/api/strategy/propose", {
    method: "POST",
    body: JSON.stringify({ instruction }),
  })
}

export function runInstruction(
  ticker: string,
  instruction: string,
  strategyYaml: string,
  timeframe: string,
  benchmark: string,
  commissionBps: number,
  slippageBps: number,
) {
  return request<BacktestResult & { catalogueStrategy: CatalogueStrategy }>("/api/backtest", {
    method: "POST",
    body: JSON.stringify({
      ticker,
      instruction,
      strategy_yaml: strategyYaml,
      window: timeframe,
      benchmark,
      commission_bps: commissionBps,
      slippage_bps: slippageBps,
    }),
  })
}

export function runCatalogueStrategy(
  ticker: string,
  strategyId: string,
  timeframe: string,
  benchmark: string,
  commissionBps: number,
  slippageBps: number,
) {
  return request<BacktestResult & { catalogueStrategy: CatalogueStrategy }>("/api/backtest", {
    method: "POST",
    body: JSON.stringify({
      ticker,
      instruction: "",
      strategy_id: strategyId,
      window: timeframe,
      benchmark,
      commission_bps: commissionBps,
      slippage_bps: slippageBps,
    }),
  })
}

export function loadOptionTemplates() {
  return request<{ templates: OptionPositionTemplate[] }>("/api/v2/options/templates")
}

export function loadOptionChain(ticker: string, expiration?: string) {
  const parameters = expiration ? `?${new URLSearchParams({ expiration })}` : ""
  return request<OptionChainResponse>(`/api/v2/options/chains/${encodeURIComponent(ticker.trim().toUpperCase())}${parameters}`)
}

export function simulateOptionPosition(position: OptionSimulationRequest) {
  return request<OptionSimulationResult>("/api/v2/options/simulations", {
    method: "POST",
    body: JSON.stringify(position),
  })
}

export function loadOptionSimulationRuns(limit = 20) {
  return request<{ runs: OptionSimulationRunSummary[] }>(`/api/v2/options/simulations?${new URLSearchParams({ limit: String(limit) })}`)
}

export function loadOptionSimulationRun(runId: string) {
  return request<OptionSimulationRunDetail>(`/api/v2/options/simulations/${encodeURIComponent(runId)}`)
}

export function createOptionPosition(position: OptionPositionCreate) {
  return request<OptionPositionResponse>("/api/v2/options/positions", {
    method: "POST",
    body: JSON.stringify(position),
  })
}

export function loadOptionPositions(limit = 20) {
  return request<{ positions: OptionPositionState[] }>(`/api/v2/options/positions?${new URLSearchParams({ limit: String(limit) })}`)
}

export function loadOptionPosition(positionId: string) {
  return request<OptionPositionResponse>(`/api/v2/options/positions/${encodeURIComponent(positionId)}`)
}

export function applyOptionLifecycleEvent(positionId: string, event: OptionLifecycleEvent) {
  return request<OptionPositionResponse>(`/api/v2/options/positions/${encodeURIComponent(positionId)}/events`, {
    method: "POST",
    body: JSON.stringify(event),
  })
}

export function loadCompanyOverview(ticker: string) {
  return request<CompanyOverview>(`/api/v3/companies/${encodeURIComponent(ticker.trim().toUpperCase())}`)
}

export function loadCompanyMetrics(ticker: string, period: "annual" | "quarterly" | "ttm" = "ttm") {
  const parameters = new URLSearchParams({ period })
  return request<CompanyMetricsResponse>(`/api/v3/companies/${encodeURIComponent(ticker.trim().toUpperCase())}/metrics?${parameters}`)
}

export function loadCompanyValuation(
  ticker: string,
  period: "1y" | "3y" | "5y" | "10y" | "max" = "5y",
  frequency: "daily" | "weekly" = "weekly",
) {
  const parameters = new URLSearchParams({ period, frequency })
  return request<HistoricalValuationResponse>(`/api/v3/companies/${encodeURIComponent(ticker.trim().toUpperCase())}/valuation?${parameters}`)
}

export function loadCompanyEarnings(ticker: string, benchmark = "SPY", limit = 40) {
  const parameters = new URLSearchParams({ benchmark: benchmark.trim().toUpperCase(), limit: String(limit) })
  return request<EarningsHistoryResponse>(`/api/v3/companies/${encodeURIComponent(ticker.trim().toUpperCase())}/earnings?${parameters}`)
}

export function loadCompanyRelationships(ticker: string) {
  return request<RelationshipNetworkResponse>(`/api/v3/companies/${encodeURIComponent(ticker.trim().toUpperCase())}/relationships`)
}

export function loadCompanyRelationshipHistory(ticker: string, relationshipId: string) {
  return request<RelationshipHistoryResponse>(`/api/v3/companies/${encodeURIComponent(ticker.trim().toUpperCase())}/relationships/${encodeURIComponent(relationshipId)}`)
}

export function loadCompanyOperations(ticker: string) {
  return request<OperatingIntelligenceResponse>(`/api/v3/companies/${encodeURIComponent(ticker.trim().toUpperCase())}/operations`)
}

export function loadCompanyGuidance(ticker: string) {
  return request<GuidanceHistoryResponse>(`/api/v3/companies/${encodeURIComponent(ticker.trim().toUpperCase())}/guidance`)
}
