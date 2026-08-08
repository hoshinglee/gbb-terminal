import type {
  BacktestResult,
  CatalogueStrategy,
  DataStatus,
  LegacyProposal,
  ParameterSearchResponse,
  ParameterValue,
  PricePoint,
  ResearchDesign,
  ResearchRunResponse,
  StrategyInstance,
  StrategyTemplate,
  ValidationDesign,
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
