import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { CompanyIntelligence } from "@/features/company-intelligence/company-intelligence"
import {
  cancelIntelligenceJob,
  loadCompanyEarnings,
  loadCompanyGuidance,
  loadCompanyMetrics,
  loadCompanyOperations,
  loadCompanyOverview,
  loadCompanyRelationshipHistory,
  loadCompanyRelationships,
  loadCompanySourceHealth,
  loadCompanyValuation,
  loadIntelligenceJob,
  loadStockOverview,
  refreshCompanySources,
} from "@/lib/api"
import type {
  EarningsEventAnalysis,
  EarningsHistoryResponse,
  GuidanceHistoryResponse,
  IntelligenceSourceHealthResponse,
  LocalIntelligenceJob,
  OperatingIntelligenceResponse,
  RelationshipHistoryResponse,
  RelationshipNetworkResponse,
  SourceEvidence,
} from "@/lib/types"

vi.mock("@/features/company-intelligence/earnings-reaction-chart", () => ({
  EarningsReactionChart: ({ analysis, period }: { analysis: EarningsEventAnalysis; period: string }) => <div data-testid="reaction-chart">Chart {analysis.event.eventId} · {period}</div>,
}))

vi.mock("@/features/company-intelligence/valuation-history-chart", () => ({
  ValuationHistoryChart: () => <div data-testid="valuation-chart">Valuation history chart</div>,
}))

vi.mock("@/lib/api", () => ({
  ApiError: class ApiError extends Error {},
  loadCompanyOverview: vi.fn(),
  loadCompanyMetrics: vi.fn(),
  loadCompanyValuation: vi.fn(),
  loadCompanyEarnings: vi.fn(),
  loadCompanyRelationships: vi.fn(),
  loadCompanyRelationshipHistory: vi.fn(),
  loadCompanyOperations: vi.fn(),
  loadCompanyGuidance: vi.fn(),
  loadCompanySourceHealth: vi.fn(),
  loadStockOverview: vi.fn(),
  refreshCompanySources: vi.fn(),
  loadIntelligenceJob: vi.fn(),
  cancelIntelligenceJob: vi.fn(),
}))

const eventAnalysis = (eventId: string, fiscalPeriod: string, announcementDate: string): EarningsEventAnalysis => ({
  event: {
    eventId,
    companyId: "company-nvda",
    cik: "0001045810",
    ticker: "NVDA",
    fiscalYear: 2024,
    fiscalPeriod,
    periodEnd: "2024-03-31",
    announcementAt: `${announcementDate}T20:30:00Z`,
    announcementDate,
    session: "after_close",
    timingQuality: "exact",
    evidence: {
      source: "SEC EDGAR",
      dataset: "sec_company_facts",
      accessionNumber: `0001045810-24-${eventId}`,
      filingForm: "10-Q",
      filingUrl: `https://www.sec.gov/${eventId}`,
      filedDate: announcementDate,
      knownAt: `${announcementDate}T20:30:00Z`,
      sourceFactIds: [`fact-${eventId}`],
    },
    reportedMetrics: {
      revenue: { metricId: "revenue", label: "Revenue", value: 26_000_000_000, unit: "USD", periodEnd: "2024-03-31", sourceFactIds: [`fact-${eventId}`], warnings: [] },
      diluted_eps: { metricId: "diluted_eps", label: "Diluted EPS", value: 6.12, unit: "USD/share", periodEnd: "2024-03-31", sourceFactIds: [`eps-${eventId}`], warnings: [] },
    },
    guidanceMetadata: {},
    modelVersion: "1.0.0",
    warnings: ["SEC filing acceptance is used as event timing."],
  },
  reaction: {
    eventId,
    benchmarkTicker: "SPY",
    anchorSession: "2024-05-23",
    priorSession: "2024-05-22",
    openingGap: 3.2,
    abnormalVolume: 2.4,
    volumePercentile: 94,
    windows: {
      d0: { window: "d0", endSession: "2024-05-23", stockReturn: 9.3, benchmarkReturn: 0.4, benchmarkAdjustedReturn: 8.9, status: "available" },
      d5: { window: "d5", endSession: "2024-05-30", stockReturn: 12.1, benchmarkReturn: 1.1, benchmarkAdjustedReturn: 11, status: "available" },
      d20: { window: "d20", endSession: "2024-06-21", stockReturn: 18.4, benchmarkReturn: 2.4, benchmarkAdjustedReturn: 16, status: "available" },
    },
    path: [{ relativeSession: 0, sessionDate: "2024-05-23", close: 103.8, cumulativeReturn: 9.3, benchmarkAdjustedReturn: 8.9, volume: 900_000_000 }],
    engineVersion: "1.0.0",
    warnings: [],
  },
})

const earnings: EarningsHistoryResponse = {
  apiVersion: "v3",
  company: { companyId: "company-nvda", cik: "0001045810", legalName: "NVIDIA CORP", primaryTicker: "NVDA", exchange: "Nasdaq", status: "active" },
  benchmarkTicker: "SPY",
  asOf: "2026-08-10T00:00:00Z",
  events: [eventAnalysis("event-q1", "Q1", "2024-05-22"), eventAnalysis("event-q4", "Q4", "2024-02-21")],
  aggregate: { sampleSize: 6, typicalAbsoluteEventMove: 7.4, positiveReactionFrequency: 66.7, medianD5Return: 4.2, medianD20Return: 8.1, eventMoveMinimum: -7.1, eventMoveMaximum: 24.4, excludedEvents: 1 },
  warnings: ["Historical earnings reactions do not predict the next earnings reaction."],
  provenance: { eventSource: "SEC EDGAR", eventDataset: "sec_company_facts", priceSource: "Yahoo Finance", asOf: "2026-08-10T00:00:00Z", eventModelVersion: "1.0.0", reactionEngineVersion: "1.0.0", sourceFactIds: ["fact-event-q1"] },
}

const sourceEvidence: SourceEvidence = {
  role: "support",
  linkedAt: "2025-03-01T12:00:00Z",
  document: {
    documentId: "document-1",
    source: "SEC EDGAR",
    dataset: "filings",
    documentType: "annual_report",
    externalId: "0001045810-25-000001",
    version: 1,
    title: "NVIDIA Annual Report",
    form: "10-K",
    accessionNumber: "0001045810-25-000001",
    sourceUrl: "https://www.sec.gov/nvda-10-k",
    filedAt: "2025-03-01T12:00:00Z",
    publishedAt: "2025-03-01T12:00:00Z",
    knownAt: "2025-03-01T12:00:00Z",
    retrievedAt: "2025-03-02T12:00:00Z",
    parseStatus: "parsed",
    qualityWarnings: [],
  },
  span: {
    spanId: "span-1",
    documentId: "document-1",
    exactText: "Taiwan Semiconductor Manufacturing Company manufactures our principal products.",
    section: "Business",
    pageNumber: 12,
    startOffset: 100,
    endOffset: 178,
    extractionMethod: "deterministic_phrase",
    extractedAt: "2025-03-02T12:00:00Z",
  },
}

const relationshipObservation = {
  observationId: "observation-1",
  relationshipId: "relationship-1",
  targetCompanyId: "company-tsm",
  exposureValue: null,
  exposureUnit: null,
  validFrom: "2025-01-01",
  validTo: null,
  knownAt: "2025-03-01T12:00:00Z",
  extractionMethod: "deterministic_phrase",
  confidence: "disclosed" as const,
  observationKind: "extracted" as const,
  supersedesObservationId: null,
  correctionNote: null,
  createdAt: "2025-03-02T12:00:00Z",
}

const relationships: RelationshipNetworkResponse = {
  apiVersion: "v3",
  company: earnings.company,
  asOf: "2026-08-10T00:00:00Z",
  matchingRelationshipCount: 2,
  returnedRelationshipCount: 2,
  relationships: [
    {
      edge: { relationshipId: "relationship-1", sourceCompanyId: "company-nvda", normalizedCounterpartyName: "taiwan semiconductor manufacturing company", rawCounterpartyName: "Taiwan Semiconductor Manufacturing Company", relationshipType: "manufacturer_foundry", direction: "upstream", modelVersion: "1.0.0", createdAt: "2025-03-02T12:00:00Z" },
      observation: relationshipObservation,
      sourceCompany: earnings.company,
      targetCompany: { companyId: "company-tsm", cik: "0001046179", legalName: "TAIWAN SEMICONDUCTOR MANUFACTURING CO LTD", primaryTicker: "TSM", exchange: "NYSE", status: "active" },
      perspectiveDirection: "upstream",
      evidence: [sourceEvidence],
    },
    {
      edge: { relationshipId: "relationship-2", sourceCompanyId: "company-nvda", normalizedCounterpartyName: "customer a", rawCounterpartyName: "Customer A", relationshipType: "customer_concentration", direction: "downstream", modelVersion: "1.0.0", createdAt: "2025-03-02T12:00:00Z" },
      observation: { ...relationshipObservation, observationId: "observation-2", relationshipId: "relationship-2", targetCompanyId: null, exposureValue: 13, exposureUnit: "% of revenue" },
      sourceCompany: earnings.company,
      targetCompany: null,
      perspectiveDirection: "downstream",
      evidence: [{ ...sourceEvidence, span: { ...sourceEvidence.span, spanId: "span-2", exactText: "Customer A represented 13% of revenue." } }],
    },
  ],
  warnings: ["Public disclosure is incomplete and absence of an edge is not evidence of no relationship."],
}

const relationshipHistory: RelationshipHistoryResponse = {
  apiVersion: "v3",
  company: earnings.company,
  asOf: relationships.asOf,
  edge: relationships.relationships[0].edge,
  observations: [relationshipObservation],
  evidence: { "observation-1": [sourceEvidence] },
}

const operations: OperatingIntelligenceResponse = {
  apiVersion: "v3",
  company: earnings.company,
  asOf: "2026-08-10T00:00:00Z",
  series: [
    {
      definition: { definitionId: "definition-compute", category: "segment", definitionKey: "compute-networking", label: "Compute & Networking", measure: "Revenue", unit: "USD", valueType: "currency", reportingBasis: "Issuer FY2025 reportable segments", version: 2, validFrom: "2025-01-01", validTo: null, supersedesDefinitionId: "definition-compute-v1", description: "Issuer-defined reportable segment", knownAt: "2025-03-01T12:00:00Z", extractionMethod: "structured_filing_table", modelVersion: "1.0.0", createdAt: "2025-03-02T12:00:00Z" },
      definitionEvidence: [sourceEvidence],
      points: [{ observation: { observationId: "operating-observation-1", definitionId: "definition-compute", periodStart: "2024-01-01", periodEnd: "2025-01-31", fiscalYear: 2025, fiscalPeriod: "FY", value: 116_000_000_000, unit: "USD", knownAt: "2025-03-01T12:00:00Z", extractionMethod: "structured_filing_table", createdAt: "2025-03-02T12:00:00Z" }, mixPercent: 88.4, growthPercent: 77.8, evidence: [sourceEvidence] }],
    },
    {
      definition: { definitionId: "definition-kpi", category: "kpi", definitionKey: "data-center-revenue", label: "Data Center Revenue", measure: "Revenue", unit: "USD", valueType: "currency", reportingBasis: "Issuer supplemental disclosure", version: 1, validFrom: "2025-01-01", validTo: null, supersedesDefinitionId: null, description: "Company-specific KPI", knownAt: "2025-03-01T12:00:00Z", extractionMethod: "structured_filing_table", modelVersion: "1.0.0", createdAt: "2025-03-02T12:00:00Z" },
      definitionEvidence: [sourceEvidence],
      points: [{ observation: { observationId: "operating-observation-2", definitionId: "definition-kpi", periodStart: "2024-01-01", periodEnd: "2025-01-31", fiscalYear: 2025, fiscalPeriod: "FY", value: 115_000_000_000, unit: "USD", knownAt: "2025-03-01T12:00:00Z", extractionMethod: "structured_filing_table", createdAt: "2025-03-02T12:00:00Z" }, mixPercent: null, growthPercent: 142, evidence: [sourceEvidence] }],
    },
  ],
  transitions: [{ priorDefinitionId: "definition-compute-v1", nextDefinitionId: "definition-compute", definitionKey: "compute-networking", priorLabel: "Compute & Networking", nextLabel: "Compute & Networking", priorReportingBasis: "Issuer FY2024 reportable segments", nextReportingBasis: "Issuer FY2025 reportable segments", knownAt: "2025-03-01T12:00:00Z" }],
  warnings: ["Company-specific KPI and geographic coverage follows issuer disclosures and may be incomplete."],
}

const guidance: GuidanceHistoryResponse = {
  apiVersion: "v3",
  company: earnings.company,
  asOf: "2026-08-10T00:00:00Z",
  records: [{
    statement: { statementId: "guidance-1", statementType: "financial_guidance", topic: "Quarterly Revenue", metricId: "revenue", statementText: "We expect revenue to be $28.0 billion, plus or minus 2 percent.", valueKind: "numeric_range", comparison: "within_range", lowerBound: 27_440_000_000, upperBound: 28_560_000_000, pointValue: null, unit: "USD", applicablePeriodStart: "2025-02-01", applicablePeriodEnd: "2025-04-30", fiscalYear: 2026, fiscalPeriod: "Q1", issuedAt: "2025-02-26T21:00:00Z", knownAt: "2025-02-26T21:00:00Z", extractionMethod: "deterministic_guidance", revision: 1, supersedesStatementId: null, modelVersion: "1.0.0", createdAt: "2025-02-27T12:00:00Z" },
    revisionDirection: "initial",
    status: "delivered",
    evaluations: [{ evaluationId: "evaluation-1", statementId: "guidance-1", status: "delivered", evaluatedAt: "2025-05-28T21:00:00Z", knownAt: "2025-05-28T21:00:00Z", method: "rule_based", actualValue: 28_100_000_000, actualUnit: "USD", sourceFactIds: ["revenue-q1"], resultingStatementId: null, note: "Objective result compared with the persisted statement bounds.", createdAt: "2025-05-29T12:00:00Z" }],
    statementEvidence: [{ ...sourceEvidence, span: { ...sourceEvidence.span, spanId: "guidance-span", exactText: "We expect revenue to be $28.0 billion, plus or minus 2 percent." } }],
    evaluationEvidence: { "evaluation-1": [sourceEvidence] },
  }],
  warnings: ["Guidance and commitments are historical source-backed statements, not forecasts generated by GBB Terminal."],
}

const sourceHealth: IntelligenceSourceHealthResponse = {
  apiVersion: "v3",
  companyId: "company-nvda",
  ticker: "NVDA",
  lastRefresh: null,
  documentCount: 2,
  parsedDocumentCount: 2,
  failedDocumentCount: 0,
  coverage: [
    { module: "evidence", status: "populated", recordCount: 2, evidenceSpanCount: 8, message: "2 parsed evidence documents are available." },
    { module: "network", status: "populated", recordCount: 2, evidenceSpanCount: 0, message: "2 source-backed network records are available." },
    { module: "operations", status: "populated", recordCount: 2, evidenceSpanCount: 0, message: "2 source-backed operations records are available." },
    { module: "guidance", status: "populated", recordCount: 1, evidenceSpanCount: 0, message: "1 source-backed guidance record is available." },
  ],
  warnings: [],
}

const completedSourceJob: LocalIntelligenceJob = {
  jobId: "job-intelligence-1",
  jobType: "intelligence_refresh",
  status: "completed",
  progress: 1,
  request: { ticker: "NVDA" },
  result: {
    refreshId: "refresh-1",
    companyId: "company-nvda",
    ticker: "NVDA",
    status: "completed",
    startedAt: "2026-08-10T00:00:00Z",
    completedAt: "2026-08-10T00:00:01Z",
    documentsDiscovered: 2,
    documentsDownloaded: 0,
    documentsUnchanged: 2,
    documentsParsed: 0,
    documentsFailed: 0,
    relationshipCount: 0,
    operatingObservationCount: 0,
    guidanceStatementCount: 0,
    coverage: sourceHealth.coverage,
    items: [],
    warnings: [],
    modelVersion: "1.0.0",
  },
  error: null,
  cancelRequested: false,
  createdAt: "2026-08-10T00:00:00Z",
  updatedAt: "2026-08-10T00:00:01Z",
}

const marketPoint = {
  date: "2024-05-23",
  periodStart: "2024-05-23",
  periodEnd: "2024-05-23",
  open: 100,
  high: 106,
  low: 99,
  close: 103.8,
  volume: 900_000_000,
  indicators: {},
}

describe("Company Intelligence earnings explorer", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(loadCompanyOverview).mockResolvedValue({
      apiVersion: "v3",
      companyId: "company-nvda",
      cik: "0001045810",
      legalName: "NVIDIA CORP",
      primaryTicker: "NVDA",
      exchange: "Nasdaq",
      status: "active",
      asOf: null,
      sector: "Technology",
      industry: "Semiconductors",
      fiscalYearEnd: "0128",
      securities: [],
      provenance: { source: "SEC EDGAR", dataset: "sec_company_tickers", observationTimestamp: "2026-08-10T00:00:00Z", knownAt: "2026-08-10T00:00:00Z", retrievedAt: "2026-08-10T00:00:00Z", status: "Delayed", qualityWarnings: [], cached: true },
    })
    vi.mocked(loadCompanyMetrics).mockImplementation(async (_ticker, period = "ttm") => ({
      apiVersion: "v3",
      company: earnings.company,
      periodKind: period,
      asOf: "2026-08-10T00:00:00Z",
      definitionVersion: "1.2.0",
      metrics: [
        { metricId: "revenue", label: "Revenue", value: 120_000_000_000, unit: "USD", periodKind: period, periodStart: "2025-01-01", periodEnd: "2025-12-31", fiscalYear: 2025, fiscalPeriod: period === "annual" ? "FY" : period === "quarterly" ? "Q4" : "TTM", definitionVersion: "1.2.0", derived: false, sourceFactIds: ["revenue-fact"], warnings: [] },
        { metricId: "operating_margin", label: "Operating Margin", value: 54.2, unit: "%", periodKind: period, periodStart: "2025-01-01", periodEnd: "2025-12-31", fiscalYear: 2025, fiscalPeriod: period === "annual" ? "FY" : period === "quarterly" ? "Q4" : "TTM", definitionVersion: "1.2.0", derived: true, sourceFactIds: ["margin-fact"], warnings: [] },
      ],
      warnings: [],
    }))
    vi.mocked(loadCompanyValuation).mockResolvedValue({
      apiVersion: "v3",
      company: earnings.company,
      frequency: "weekly",
      startDate: "2021-08-10",
      endDate: "2026-08-10",
      asOf: "2026-08-10T00:00:00Z",
      engineVersion: "1.0.0",
      history: {},
      statistics: { trailing_pe: { metricId: "trailing_pe", label: "Trailing P/E", unit: "x", status: "available", current: 31.4, percentile: 92, median: 28.1, minimum: 14, maximum: 72, zScore: 0.4, sampleSize: 260 } },
      warnings: [],
      provenance: { priceSource: "Yahoo Finance", priceDataset: "daily_prices", fundamentalSource: "SEC EDGAR", fundamentalDataset: "normalized_financial_metrics", asOf: "2026-08-10T00:00:00Z", engineVersion: "1.0.0", sourceFactIds: [] },
    })
    vi.mocked(loadCompanyEarnings).mockResolvedValue(earnings)
    vi.mocked(loadCompanyRelationships).mockResolvedValue(relationships)
    vi.mocked(loadCompanyRelationshipHistory).mockResolvedValue(relationshipHistory)
    vi.mocked(loadCompanyOperations).mockResolvedValue(operations)
    vi.mocked(loadCompanyGuidance).mockResolvedValue(guidance)
    vi.mocked(loadCompanySourceHealth).mockResolvedValue(sourceHealth)
    vi.mocked(loadStockOverview).mockResolvedValue({
      quote: { symbol: "NVDA", price: 182.7, change: 3.2, changePercent: 1.78, periodReturn: 45, dataStatus: { source: "Yahoo Finance", status: "Cached Snapshot", observationTimestamp: "2026-08-10T00:00:00Z", knownAt: "2026-08-10T00:00:00Z", retrievedAt: "2026-08-10T00:01:00Z", qualityWarnings: [], cached: true } },
      marketChart: { defaultInterval: "day", intervals: { day: [marketPoint], week: [marketPoint], month: [marketPoint], year: [marketPoint] } },
      period: "3y",
    })
    vi.mocked(refreshCompanySources).mockResolvedValue({ apiVersion: "v3", jobId: completedSourceJob.jobId, status: "running" })
    vi.mocked(loadIntelligenceJob).mockResolvedValue(completedSourceJob)
    vi.mocked(cancelIntelligenceJob).mockResolvedValue({ jobId: completedSourceJob.jobId, cancelRequested: true })
  })

  it("keeps company context, sample size, evidence, and non-predictive language visible", async () => {
    const user = userEvent.setup()
    render(<CompanyIntelligence initialTicker="NVDA" />)

    expect(await screen.findByRole("heading", { name: "NVIDIA CORP" })).toBeInTheDocument()
    expect(screen.getByText("Local Watchlist")).toBeInTheDocument()
    expect(screen.getByText("$182.70")).toBeInTheDocument()
    expect(screen.getByText("Above History")).toBeInTheDocument()
    await user.click(screen.getByRole("tab", { name: "Earnings" }))
    expect(screen.getByText("6 usable · 1 excluded")).toBeInTheDocument()
    expect(screen.getByText("Reported Facts")).toBeInTheDocument()
    expect(screen.getByText("Calculated Market Reaction")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /Open SEC Filing/ })).toHaveAttribute("href", "https://www.sec.gov/event-q1")
    expect(screen.getByText(/do not predict the next earnings reaction/i)).toBeInTheDocument()
    expect(screen.getByLabelText("Company ticker")).toHaveValue("NVDA")
    expect(screen.getByLabelText("Earnings benchmark")).toHaveValue("SPY")
    expect(screen.getByRole("tablist")).toHaveClass("grid", "w-full", "grid-cols-2", "group-data-[orientation=horizontal]/tabs:h-auto", "sm:flex", "sm:flex-wrap")
    expect(screen.getByRole("tablist")).not.toHaveClass("overflow-x-auto")
  })

  it("exposes persisted network, operating, and guidance evidence without hiding missing context", async () => {
    const user = userEvent.setup()
    render(<CompanyIntelligence initialTicker="NVDA" />)
    await screen.findByRole("heading", { name: "NVIDIA CORP" })

    await user.click(screen.getByRole("tab", { name: "Network" }))
    expect(await screen.findByText("Evidence-Backed Business Network")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /Open TAIWAN SEMICONDUCTOR MANUFACTURING CO LTD Company Intelligence/ })).toHaveAttribute("href", "/?lab=intelligence&ticker=TSM")
    expect(screen.getByText("Unresolved public-company mapping")).toBeInTheDocument()
    expect(screen.getByText("Incomplete Public Network")).toBeInTheDocument()
    const unresolvedNode = screen.getByRole("button", { name: "Inspect unresolved counterparty Customer A" })
    unresolvedNode.focus()
    fireEvent.keyDown(unresolvedNode, { key: "Enter" })
    expect(await screen.findByText("Customer A Relationship History")).toBeInTheDocument()
    expect(loadCompanyRelationshipHistory).toHaveBeenCalledWith("NVDA", "relationship-2")
    await user.click(screen.getByRole("button", { name: "Close" }))

    await user.click(screen.getByRole("tab", { name: "Operations" }))
    expect(await screen.findByText("Business Segments")).toBeInTheDocument()
    expect(screen.getByText("Reporting Definitions Changed")).toBeInTheDocument()
    expect(screen.getAllByText("Data Center Revenue").length).toBeGreaterThan(0)
    expect(screen.getByText(/does not calculate growth across incompatible definitions/i)).toBeInTheDocument()

    await user.click(screen.getByRole("tab", { name: "Guidance" }))
    expect(await screen.findByText("Management Guidance & Commitments")).toBeInTheDocument()
    expect(screen.getByText("Normalized Range")).toBeInTheDocument()
    expect(screen.getByText(/We expect revenue to be \$28.0 billion/i)).toBeInTheDocument()
    expect(screen.getByText("Historical Record, Not Model Forecast")).toBeInTheDocument()
  })

  it("selects another event through a keyboard-focusable event control", async () => {
    const user = userEvent.setup()
    render(<CompanyIntelligence initialTicker="NVDA" />)
    await user.click(await screen.findByRole("tab", { name: "Earnings" }))
    const secondEvent = await screen.findByRole("button", { name: /Q4 2024/ })

    fireEvent.click(secondEvent)

    await waitFor(() => expect(screen.getByTestId("reaction-chart")).toHaveTextContent("event-q4"))
    expect(secondEvent).toHaveAttribute("aria-pressed", "true")
    expect(screen.getByRole("link", { name: /Open SEC Filing/ })).toHaveAttribute("href", "https://www.sec.gov/event-q4")
  })

  it("keeps annual, quarterly, and TTM history separate from other time controls", async () => {
    const user = userEvent.setup()
    render(<CompanyIntelligence initialTicker="NVDA" />)
    await screen.findByRole("heading", { name: "NVIDIA CORP" })

    await user.click(screen.getByRole("tab", { name: "Financials" }))
    expect(screen.getAllByText("Trailing Twelve Months").length).toBeGreaterThan(0)
    expect(screen.getAllByText("Quarterly History").length).toBeGreaterThan(0)
    expect(screen.getAllByText("Annual History").length).toBeGreaterThan(0)
    expect(loadCompanyMetrics).toHaveBeenCalledWith("NVDA", "annual")
    expect(loadCompanyMetrics).toHaveBeenCalledWith("NVDA", "quarterly")
    expect(loadCompanyMetrics).toHaveBeenCalledWith("NVDA", "ttm")

    await user.click(screen.getByRole("tab", { name: "Valuation" }))
    expect(screen.getByRole("combobox", { name: "Valuation history window" })).toHaveTextContent("5 Years")
    expect(screen.getByTestId("valuation-chart")).toBeInTheDocument()
  })

  it("runs the visible SEC source refresh workflow from Sources", async () => {
    const user = userEvent.setup()
    render(<CompanyIntelligence initialTicker="NVDA" />)
    await screen.findByRole("heading", { name: "NVIDIA CORP" })

    await user.click(screen.getByRole("tab", { name: "Sources" }))
    expect(await screen.findByText("Public Intelligence Sources")).toBeInTheDocument()
    expect(screen.getByText("2 cached documents")).toBeInTheDocument()
    await user.click(screen.getByRole("button", { name: /Refresh Intelligence Sources/ }))

    await waitFor(() => expect(refreshCompanySources).toHaveBeenCalledWith("NVDA"))
    await waitFor(() => expect(loadIntelligenceJob).toHaveBeenCalledWith(completedSourceJob.jobId))
    await waitFor(() => expect(loadCompanySourceHealth).toHaveBeenCalledTimes(2))
  })
})
