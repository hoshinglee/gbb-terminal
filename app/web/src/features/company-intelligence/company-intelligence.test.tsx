import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { CompanyIntelligence } from "@/features/company-intelligence/company-intelligence"
import {
  loadCompanyEarnings,
  loadCompanyMetrics,
  loadCompanyOverview,
  loadCompanyValuation,
} from "@/lib/api"
import type { EarningsEventAnalysis, EarningsHistoryResponse } from "@/lib/types"

vi.mock("@/features/company-intelligence/earnings-reaction-chart", () => ({
  EarningsReactionChart: ({ analysis }: { analysis: EarningsEventAnalysis }) => <div data-testid="reaction-chart">Chart {analysis.event.eventId}</div>,
}))

vi.mock("@/lib/api", () => ({
  ApiError: class ApiError extends Error {},
  loadCompanyOverview: vi.fn(),
  loadCompanyMetrics: vi.fn(),
  loadCompanyValuation: vi.fn(),
  loadCompanyEarnings: vi.fn(),
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

describe("Company Intelligence earnings explorer", () => {
  beforeEach(() => {
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
    vi.mocked(loadCompanyMetrics).mockResolvedValue({
      apiVersion: "v3",
      company: earnings.company,
      periodKind: "ttm",
      asOf: "2026-08-10T00:00:00Z",
      definitionVersion: "1.1.0",
      metrics: [{ metricId: "revenue", label: "Revenue", value: 120_000_000_000, unit: "USD", periodKind: "ttm", periodStart: "2025-01-01", periodEnd: "2025-12-31", fiscalYear: 2025, fiscalPeriod: "TTM", definitionVersion: "1.1.0", derived: false, sourceFactIds: ["revenue-fact"], warnings: [] }],
      warnings: [],
    })
    vi.mocked(loadCompanyValuation).mockResolvedValue({
      apiVersion: "v3",
      company: earnings.company,
      frequency: "weekly",
      startDate: "2021-08-10",
      endDate: "2026-08-10",
      asOf: "2026-08-10T00:00:00Z",
      engineVersion: "1.0.0",
      history: {},
      statistics: { trailing_pe: { metricId: "trailing_pe", label: "Trailing P/E", unit: "x", status: "available", current: 31.4, percentile: 64, median: 28.1, minimum: 14, maximum: 72, zScore: 0.4, sampleSize: 260 } },
      warnings: [],
      provenance: { priceSource: "Yahoo Finance", priceDataset: "daily_prices", fundamentalSource: "SEC EDGAR", fundamentalDataset: "normalized_financial_metrics", asOf: "2026-08-10T00:00:00Z", engineVersion: "1.0.0", sourceFactIds: [] },
    })
    vi.mocked(loadCompanyEarnings).mockResolvedValue(earnings)
  })

  it("keeps company context, sample size, evidence, and non-predictive language visible", async () => {
    render(<CompanyIntelligence initialTicker="NVDA" />)

    expect(await screen.findByRole("heading", { name: "NVIDIA CORP" })).toBeInTheDocument()
    expect(screen.getByText("6 usable events · 1 excluded")).toBeInTheDocument()
    expect(screen.getByText("Reported Facts")).toBeInTheDocument()
    expect(screen.getByText("Calculated Market Reaction")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /Open SEC Filing/ })).toHaveAttribute("href", "https://www.sec.gov/event-q1")
    expect(screen.getByText(/do not predict the next earnings reaction/i)).toBeInTheDocument()
    expect(screen.getByLabelText("Company ticker")).toHaveValue("NVDA")
    expect(screen.getByLabelText("Earnings benchmark")).toHaveValue("SPY")
  })

  it("selects another event through a keyboard-focusable event control", async () => {
    render(<CompanyIntelligence initialTicker="NVDA" />)
    const secondEvent = await screen.findByRole("button", { name: /Q4 2024/ })

    fireEvent.click(secondEvent)

    await waitFor(() => expect(screen.getByTestId("reaction-chart")).toHaveTextContent("event-q4"))
    expect(secondEvent).toHaveAttribute("aria-pressed", "true")
    expect(screen.getByRole("link", { name: /Open SEC Filing/ })).toHaveAttribute("href", "https://www.sec.gov/event-q4")
  })
})
