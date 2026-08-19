import { useCallback, useEffect, useMemo, useState } from "react"
import {
  AlertCircle,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  BookOpenCheck,
  Building2,
  CalendarClock,
  Database,
  ExternalLink,
  FileCheck2,
  FlaskConical,
  Layers3,
  Minus,
  Network,
  Orbit,
  RefreshCw,
  Search,
  Star,
  StarOff,
  Target,
  TrendingUp,
} from "lucide-react"
import { toast } from "sonner"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { EarningsReactionChart, type EventMarketPeriod } from "@/features/company-intelligence/earnings-reaction-chart"
import { FinancialHistory, type FinancialMetricSets } from "@/features/company-intelligence/financial-history"
import { GuidanceTimeline } from "@/features/company-intelligence/guidance-timeline"
import { OperationsIntelligence } from "@/features/company-intelligence/operations-intelligence"
import { RelationshipNetwork } from "@/features/company-intelligence/relationship-network"
import { ValuationHistoryChart } from "@/features/company-intelligence/valuation-history-chart"
import {
  ApiError,
  cancelIntelligenceJob,
  loadCompanyEarnings,
  loadCompanyGuidance,
  loadCompanyMetrics,
  loadCompanyOperations,
  loadCompanyOverview,
  loadCompanyRelationships,
  loadCompanySourceHealth,
  loadCompanyValuation,
  loadIntelligenceJob,
  loadStockOverview,
  refreshCompanySources,
} from "@/lib/api"
import { ordinal } from "@/lib/format"
import { labHref, normalizeTicker } from "@/lib/navigation"
import type {
  CompanyMetric,
  CompanyOverview,
  DataStatus,
  EarningsEventAnalysis,
  EarningsHistoryResponse,
  GuidanceHistoryResponse,
  HistoricalValuationResponse,
  IntelligenceSourceHealthResponse,
  LocalIntelligenceJob,
  OperatingIntelligenceResponse,
  RelationshipNetworkResponse,
  StockOverviewResponse,
  ValuationStatistics,
} from "@/lib/types"
import { cn } from "@/lib/utils"
import { readWatchlist, writeWatchlist } from "@/lib/watchlist"

type ValuationPeriod = "1y" | "3y" | "5y" | "10y" | "max"
type CompanySection = "overview" | "financials" | "valuation" | "earnings" | "operations" | "network" | "guidance" | "sources"

const valuationPeriods: Record<ValuationPeriod, string> = {
  "1y": "1 Year",
  "3y": "3 Years",
  "5y": "5 Years",
  "10y": "10 Years",
  max: "Maximum",
}

const valuationIds = ["trailing_pe", "price_to_sales", "price_to_book", "ev_to_revenue", "price_to_fcf", "fcf_yield"]

const emptyFinancials: FinancialMetricSets = { annual: null, quarterly: null, ttm: null }

function message(error: unknown) {
  if (error instanceof ApiError || error instanceof Error) return error.message
  return "Company Intelligence could not load this research surface."
}

function compact(value: number) {
  return Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 2 }).format(value)
}

function money(value: number) {
  return value.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 })
}

function metricValue(metric?: { value: number | null; unit: string } | null) {
  if (!metric || metric.value === null) return "—"
  if (metric.unit === "USD") return `$${compact(metric.value)}`
  if (metric.unit === "USD/share") return `$${metric.value.toFixed(2)}`
  if (metric.unit === "%") return `${metric.value.toFixed(2)}%`
  if (metric.unit === "shares") return compact(metric.value)
  return metric.value.toLocaleString(undefined, { maximumFractionDigits: 2 })
}

function percentage(value: number | null | undefined) {
  return value === null || value === undefined ? "—" : `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`
}

function multiple(value: number | null | undefined, status?: string) {
  if (status === "nm") return "NM"
  return value === null || value === undefined ? "—" : `${value.toFixed(2)}x`
}

function readableDate(value?: string | null) {
  if (!value) return "Not Reported"
  const parsed = new Date(`${value.length === 10 ? `${value}T12:00:00` : value}`)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })
}

function readableDateTime(value?: string | null) {
  if (!value) return "Not Reported"
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString()
}

function readableStatus(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function latestMetric(metrics: CompanyMetric[], metricId: string) {
  return metrics.filter((metric) => metric.metricId === metricId).sort((left, right) => left.periodEnd.localeCompare(right.periodEnd)).at(-1)
}

function priorMetric(metrics: CompanyMetric[], metricId: string) {
  return metrics.filter((metric) => metric.metricId === metricId).sort((left, right) => left.periodEnd.localeCompare(right.periodEnd)).at(-2)
}

function EvidenceMetric({ label, value, note, tone = "default" }: { label: string; value: string; note: string; tone?: "default" | "positive" | "negative" }) {
  return <div className="rounded-lg border bg-background/45 p-4"><span className="font-mono text-[9px] uppercase tracking-[0.14em] text-muted-foreground">{label}</span><strong className={cn("mt-2 block text-xl", tone === "positive" && "text-primary", tone === "negative" && "text-destructive")}>{value}</strong><small className="mt-1 block leading-4 text-muted-foreground">{note}</small></div>
}

function ComparableMetric({ label, value, comparison, comparisonUnit = "percent", note }: { label: string; value: string; comparison?: number | null; comparisonUnit?: "percent" | "points"; note: string }) {
  const direction = comparison === null || comparison === undefined || comparison === 0 ? "flat" : comparison > 0 ? "up" : "down"
  const comparisonText = comparisonUnit === "points" && comparison !== null && comparison !== undefined ? `${Math.abs(comparison).toFixed(2)} pp` : percentage(comparison)
  return <div className="rounded-lg border bg-background/45 p-4"><span className="font-mono text-[9px] uppercase tracking-[0.14em] text-muted-foreground">{label}</span><strong className="mt-2 block text-2xl text-foreground">{value}</strong>{comparison !== null && comparison !== undefined ? <span className={cn("mt-2 flex items-center gap-1 text-xs", direction === "up" ? "text-primary" : direction === "down" ? "text-destructive" : "text-muted-foreground")}>{direction === "up" ? <ArrowUpRight className="size-3.5" /> : direction === "down" ? <ArrowDownRight className="size-3.5" /> : <Minus className="size-3.5" />}{comparisonText} comparable move</span> : null}<small className="mt-1 block leading-4 text-muted-foreground">{note}</small></div>
}

function valuationRegime(statistics: ValuationStatistics) {
  if (statistics.status === "nm") return { label: "NM", classes: "border-muted-foreground/30 text-muted-foreground" }
  if (statistics.status !== "available") return { label: "Unavailable", classes: "border-muted-foreground/30 text-muted-foreground" }
  if (statistics.sampleSize < 20 || statistics.percentile === null) return { label: "Low Sample", classes: "border-chart-2/30 text-chart-2" }
  if (statistics.percentile <= 20) return { label: "Below History", classes: "border-chart-2/40 text-chart-2" }
  if (statistics.percentile <= 80) return { label: "Typical Range", classes: "border-muted-foreground/30 text-muted-foreground" }
  if (statistics.percentile <= 95) return { label: "Above History", classes: "border-chart-3/40 text-chart-3" }
  return { label: "Extreme vs History", classes: "border-chart-4/40 text-chart-4" }
}

function ValuationCard({ statistics }: { statistics?: ValuationStatistics }) {
  if (!statistics) return null
  const isYield = statistics.unit === "%"
  const current = isYield ? percentage(statistics.current) : multiple(statistics.current, statistics.status)
  const medianValue = isYield ? percentage(statistics.median) : multiple(statistics.median)
  const regime = valuationRegime(statistics)
  return <div className="rounded-lg border bg-background/45 p-4"><div className="flex items-start justify-between gap-2"><span className="text-sm font-medium">{statistics.label}</span><Badge variant="outline" className={regime.classes}>{regime.label}</Badge></div><strong className="mt-3 block text-2xl text-foreground">{current}</strong><div className="mt-3 grid grid-cols-2 gap-2 font-mono text-[9px] text-muted-foreground"><span>Median <b className="block text-foreground">{medianValue}</b></span><span>Percentile <b className="block text-foreground">{statistics.percentile === null ? "—" : ordinal(statistics.percentile)}</b></span></div><p className="mt-3 text-[10px] text-muted-foreground">{statistics.sampleSize} usable observations · historical regime only</p></div>
}

function EventList({ events, selectedId, onSelect }: { events: EarningsEventAnalysis[]; selectedId?: string; onSelect: (analysis: EarningsEventAnalysis) => void }) {
  return <ScrollArea className="h-[560px]"><Table><TableHeader><TableRow><TableHead>Fiscal Event</TableHead><TableHead>Reported</TableHead><TableHead>D0</TableHead><TableHead>D+5</TableHead><TableHead>D+20 Adj.</TableHead><TableHead>Volume</TableHead></TableRow></TableHeader><TableBody>{events.map((analysis) => {
    const event = analysis.event
    const reaction = analysis.reaction
    const revenue = event.reportedMetrics.revenue
    const eps = event.reportedMetrics.diluted_eps
    const selected = event.eventId === selectedId
    return <TableRow key={event.eventId} data-state={selected ? "selected" : undefined}><TableCell><button type="button" aria-pressed={selected} className="min-w-36 rounded-md p-2 text-left focus-visible:ring-2 focus-visible:ring-primary" onClick={() => onSelect(analysis)}><strong className="block">{event.fiscalPeriod || "FY"} {event.fiscalYear || ""}</strong><span className="mt-1 block text-[10px] text-muted-foreground">{readableDate(event.announcementDate)}</span><Badge variant="outline" className="mt-2 text-[8px]">{event.session.replace("_", " ")}</Badge></button></TableCell><TableCell><span className="block text-xs">Rev {metricValue(revenue)}</span><span className="mt-1 block text-[10px] text-muted-foreground">EPS {metricValue(eps)}</span></TableCell><TableCell className={cn((reaction.windows.d0?.stockReturn || 0) > 0 && "text-primary", (reaction.windows.d0?.stockReturn || 0) < 0 && "text-destructive")}>{percentage(reaction.windows.d0?.stockReturn)}</TableCell><TableCell>{percentage(reaction.windows.d5?.stockReturn)}</TableCell><TableCell>{percentage(reaction.windows.d20?.benchmarkAdjustedReturn)}</TableCell><TableCell>{reaction.abnormalVolume === null ? "—" : `${reaction.abnormalVolume.toFixed(2)}×`}<small className="block text-[9px] text-muted-foreground">{reaction.volumePercentile === null ? "No rank" : `${ordinal(reaction.volumePercentile)} pct.`}</small></TableCell></TableRow>
  })}</TableBody></Table></ScrollArea>
}

function EventDetail({ analysis, market, marketPeriod, marketLoading, onMarketPeriodChange }: { analysis: EarningsEventAnalysis; market: StockOverviewResponse | null; marketPeriod: EventMarketPeriod; marketLoading: boolean; onMarketPeriodChange: (period: EventMarketPeriod) => void }) {
  const { event, reaction } = analysis
  const reported = Object.values(event.reportedMetrics)
  return <div className="space-y-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="flex flex-wrap items-center gap-2"><Badge>{event.fiscalPeriod || "FY"} {event.fiscalYear}</Badge><Badge variant="outline">{event.session.replace("_", " ")}</Badge><Badge variant={event.timingQuality === "exact" ? "secondary" : "outline"}>{event.timingQuality === "exact" ? "Exact SEC Time" : "Date Only"}</Badge></div><h3 className="mt-3 text-xl font-semibold">Event anchored to {readableDate(reaction.anchorSession)}</h3><p className="mt-1 text-xs text-muted-foreground">Fiscal period ended {readableDate(event.periodEnd)} · baseline {readableDate(reaction.priorSession)}</p></div><Button asChild variant="outline"><a href={event.evidence.filingUrl} target="_blank" rel="noreferrer"><FileCheck2 />Open SEC Filing<ExternalLink /></a></Button></div>
    <div className="grid gap-3 xl:grid-cols-2"><Card className="gap-3 py-4"><CardHeader className="px-4"><div className="flex items-center gap-2"><BookOpenCheck className="size-4 text-primary" /><CardTitle className="text-sm">Reported Facts</CardTitle></div><CardDescription>Normalized SEC values stay neutral unless an actual expectation comparison exists.</CardDescription></CardHeader><CardContent className="grid gap-2 px-4 sm:grid-cols-2">{reported.length ? reported.map((metric) => <EvidenceMetric key={metric.metricId} label={metric.label} value={metricValue(metric)} note={`${metric.sourceFactIds.length} source fact${metric.sourceFactIds.length === 1 ? "" : "s"}`} />) : <p className="text-sm text-muted-foreground">No supported normalized result was available.</p>}</CardContent></Card><Card className="gap-3 py-4"><CardHeader className="px-4"><div className="flex items-center gap-2"><TrendingUp className="size-4 text-chart-2" /><CardTitle className="text-sm">Calculated Market Reaction</CardTitle></div><CardDescription>Positive and negative colors describe observed price movement, not company quality.</CardDescription></CardHeader><CardContent className="grid gap-2 px-4 sm:grid-cols-2"><EvidenceMetric label="Opening Gap" value={percentage(reaction.openingGap)} note="Anchor open vs prior close" tone={(reaction.openingGap || 0) < 0 ? "negative" : (reaction.openingGap || 0) > 0 ? "positive" : "default"} /><EvidenceMetric label="D0 Move" value={percentage(reaction.windows.d0?.stockReturn)} note="Prior close to anchor close" tone={(reaction.windows.d0?.stockReturn || 0) < 0 ? "negative" : (reaction.windows.d0?.stockReturn || 0) > 0 ? "positive" : "default"} /><EvidenceMetric label="D+20 Adjusted" value={percentage(reaction.windows.d20?.benchmarkAdjustedReturn)} note={`Less ${reaction.benchmarkTicker} over identical sessions`} tone={(reaction.windows.d20?.benchmarkAdjustedReturn || 0) < 0 ? "negative" : (reaction.windows.d20?.benchmarkAdjustedReturn || 0) > 0 ? "positive" : "default"} /><EvidenceMetric label="Abnormal Volume" value={reaction.abnormalVolume === null ? "—" : `${reaction.abnormalVolume.toFixed(2)}×`} note={reaction.volumePercentile === null ? "Insufficient prior volume" : `${ordinal(reaction.volumePercentile)} historical percentile`} /></CardContent></Card></div>
    <EarningsReactionChart analysis={analysis} marketChart={market?.marketChart || null} period={marketPeriod} onPeriodChange={onMarketPeriodChange} loading={marketLoading} />
    <div className="rounded-lg border border-dashed p-4 text-xs text-muted-foreground"><strong className="text-foreground">Evidence:</strong> {event.evidence.source} · {event.evidence.filingForm} · accession {event.evidence.accessionNumber} · known {new Date(event.evidence.knownAt).toLocaleString()}. {event.warnings.concat(reaction.warnings).join(" ")}</div>
  </div>
}

function ProvenanceCard({ status }: { status?: DataStatus }) {
  return <Card><CardHeader><div className="flex flex-wrap items-start justify-between gap-3"><div><CardTitle>Market Data Freshness</CardTitle><CardDescription className="mt-2">Price context can fail independently from SEC-backed company evidence.</CardDescription></div><Badge variant="outline">{status?.status || "Unavailable"}</Badge></div></CardHeader><CardContent className="grid gap-3 border-t pt-5 text-xs sm:grid-cols-2 xl:grid-cols-4"><div><span className="text-muted-foreground">Source</span><strong className="mt-1 block">{status?.source || "Public market provider"}</strong></div><div><span className="text-muted-foreground">Observed</span><strong className="mt-1 block">{readableDateTime(status?.observationTimestamp)}</strong></div><div><span className="text-muted-foreground">Known At</span><strong className="mt-1 block">{readableDateTime(status?.knownAt)}</strong></div><div><span className="text-muted-foreground">Retrieved</span><strong className="mt-1 block">{readableDateTime(status?.retrievedAt)}</strong></div>{status?.qualityWarnings?.length ? <div className="sm:col-span-2 xl:col-span-4"><span className="text-muted-foreground">Quality Notes</span><p className="mt-1 leading-5">{status.qualityWarnings.join(" ")}</p></div> : null}</CardContent></Card>
}

export function CompanyIntelligence({ initialTicker = "NVDA" }: { initialTicker?: string }) {
  const initial = normalizeTicker(initialTicker)
  const [tickerInput, setTickerInput] = useState(initial)
  const [ticker, setTicker] = useState(initial)
  const [activeSection, setActiveSection] = useState<CompanySection>("overview")
  const [benchmarkInput, setBenchmarkInput] = useState("SPY")
  const [benchmark, setBenchmark] = useState("SPY")
  const [valuationPeriod, setValuationPeriod] = useState<ValuationPeriod>("5y")
  const [marketPeriod, setMarketPeriod] = useState<EventMarketPeriod>("3y")
  const [overview, setOverview] = useState<CompanyOverview | null>(null)
  const [financials, setFinancials] = useState<FinancialMetricSets>(emptyFinancials)
  const [valuation, setValuation] = useState<HistoricalValuationResponse | null>(null)
  const [earnings, setEarnings] = useState<EarningsHistoryResponse | null>(null)
  const [market, setMarket] = useState<StockOverviewResponse | null>(null)
  const [relationships, setRelationships] = useState<RelationshipNetworkResponse | null>(null)
  const [operations, setOperations] = useState<OperatingIntelligenceResponse | null>(null)
  const [guidance, setGuidance] = useState<GuidanceHistoryResponse | null>(null)
  const [sourceHealth, setSourceHealth] = useState<IntelligenceSourceHealthResponse | null>(null)
  const [sourceJob, setSourceJob] = useState<LocalIntelligenceJob | null>(null)
  const [sourceRefreshStarting, setSourceRefreshStarting] = useState(false)
  const [selectedEventId, setSelectedEventId] = useState<string>()
  const [watchlist, setWatchlist] = useState<string[]>(() => readWatchlist())
  const [loading, setLoading] = useState(false)
  const [valuationLoading, setValuationLoading] = useState(false)
  const [earningsLoading, setEarningsLoading] = useState(false)
  const [marketLoading, setMarketLoading] = useState(false)
  const [errors, setErrors] = useState<string[]>([])

  const load = useCallback(async (symbol: string, selectedBenchmark: string, selectedValuationPeriod: ValuationPeriod, selectedMarketPeriod: EventMarketPeriod) => {
    const normalizedTicker = normalizeTicker(symbol, "")
    const normalizedBenchmark = normalizeTicker(selectedBenchmark, "SPY")
    if (!normalizedTicker) return toast.error("Enter a supported US market ticker.")
    setLoading(true)
    setErrors([])
    setTicker(normalizedTicker)
    setTickerInput(normalizedTicker)
    setBenchmark(normalizedBenchmark)
    setBenchmarkInput(normalizedBenchmark)
    setSourceJob(null)
    const results = await Promise.allSettled([
      loadCompanyOverview(normalizedTicker),
      loadCompanyMetrics(normalizedTicker, "annual"),
      loadCompanyMetrics(normalizedTicker, "quarterly"),
      loadCompanyMetrics(normalizedTicker, "ttm"),
      loadCompanyValuation(normalizedTicker, selectedValuationPeriod, "weekly"),
      loadCompanyEarnings(normalizedTicker, normalizedBenchmark),
      loadCompanyRelationships(normalizedTicker),
      loadCompanyOperations(normalizedTicker),
      loadCompanyGuidance(normalizedTicker),
      loadCompanySourceHealth(normalizedTicker),
      loadStockOverview(normalizedTicker, selectedMarketPeriod),
    ])
    const [overviewResult, annualResult, quarterlyResult, ttmResult, valuationResult, earningsResult, relationshipsResult, operationsResult, guidanceResult, sourceHealthResult, marketResult] = results
    setOverview(overviewResult.status === "fulfilled" ? overviewResult.value : null)
    setFinancials({
      annual: annualResult.status === "fulfilled" ? annualResult.value : null,
      quarterly: quarterlyResult.status === "fulfilled" ? quarterlyResult.value : null,
      ttm: ttmResult.status === "fulfilled" ? ttmResult.value : null,
    })
    setValuation(valuationResult.status === "fulfilled" ? valuationResult.value : null)
    if (earningsResult.status === "fulfilled") {
      setEarnings(earningsResult.value)
      setSelectedEventId(earningsResult.value.events[0]?.event.eventId)
    } else {
      setEarnings(null)
      setSelectedEventId(undefined)
    }
    setRelationships(relationshipsResult.status === "fulfilled" ? relationshipsResult.value : null)
    setOperations(operationsResult.status === "fulfilled" ? operationsResult.value : null)
    setGuidance(guidanceResult.status === "fulfilled" ? guidanceResult.value : null)
    setSourceHealth(sourceHealthResult.status === "fulfilled" ? sourceHealthResult.value : null)
    setMarket(marketResult.status === "fulfilled" ? marketResult.value : null)
    const failures = results.filter((result): result is PromiseRejectedResult => result.status === "rejected").map((result) => message(result.reason))
    setErrors([...new Set(failures)])
    if (failures.length === results.length) toast.error("Company Intelligence unavailable", { description: failures[0] })
    setLoading(false)
  }, [])

  useEffect(() => { void load(initial, "SPY", "5y", "3y") }, [initial, load])

  const selectedAnalysis = useMemo(
    () => earnings?.events.find((analysis) => analysis.event.eventId === selectedEventId) || earnings?.events[0],
    [earnings, selectedEventId],
  )
  const ttmMetrics = financials.ttm?.metrics || []
  const latestRevenue = latestMetric(ttmMetrics, "revenue")
  const latestOperatingMargin = latestMetric(ttmMetrics, "operating_margin")
  const priorOperatingMargin = priorMetric(ttmMetrics, "operating_margin")
  const operatingMarginChange = latestOperatingMargin?.value !== null && latestOperatingMargin?.value !== undefined && priorOperatingMargin?.value !== null && priorOperatingMargin?.value !== undefined ? latestOperatingMargin.value - priorOperatingMargin.value : null

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    setActiveSection("overview")
    void load(tickerInput, benchmark, valuationPeriod, marketPeriod)
  }
  const changeValuationPeriod = async (period: ValuationPeriod) => {
    setValuationPeriod(period)
    setValuationLoading(true)
    try {
      setValuation(await loadCompanyValuation(ticker, period, "weekly"))
    } catch (error) {
      toast.error("Valuation history unavailable", { description: message(error) })
    } finally {
      setValuationLoading(false)
    }
  }
  const submitBenchmark = async (event: React.FormEvent) => {
    event.preventDefault()
    const normalized = normalizeTicker(benchmarkInput, "SPY")
    setBenchmark(normalized)
    setBenchmarkInput(normalized)
    setEarningsLoading(true)
    try {
      const result = await loadCompanyEarnings(ticker, normalized)
      setEarnings(result)
      setSelectedEventId(result.events[0]?.event.eventId)
    } catch (error) {
      toast.error("Earnings comparison unavailable", { description: message(error) })
    } finally {
      setEarningsLoading(false)
    }
  }
  const changeMarketPeriod = async (period: EventMarketPeriod) => {
    if (period === marketPeriod) return
    setMarketPeriod(period)
    setMarketLoading(true)
    try {
      setMarket(await loadStockOverview(ticker, period))
    } catch (error) {
      toast.error("Event market history unavailable", { description: message(error) })
    } finally {
      setMarketLoading(false)
    }
  }
  const toggleWatchlist = () => {
    const next = watchlist.includes(ticker) ? watchlist.filter((symbol) => symbol !== ticker) : [...watchlist, ticker]
    setWatchlist(next)
    writeWatchlist(next)
  }
  const openWatchlistTicker = (symbol: string) => {
    setActiveSection("overview")
    void load(symbol, benchmark, valuationPeriod, marketPeriod)
  }
  const refreshSources = async () => {
    setSourceRefreshStarting(true)
    try {
      const accepted = await refreshCompanySources(ticker)
      let job = await loadIntelligenceJob(accepted.jobId)
      setSourceJob(job)
      while (job.status === "running") {
        await new Promise((resolve) => window.setTimeout(resolve, 500))
        job = await loadIntelligenceJob(accepted.jobId)
        setSourceJob(job)
      }
      if (job.status === "completed") toast.success("Intelligence sources refreshed", { description: "SEC documents and evidence-backed modules were updated locally." })
      else if (job.status === "cancelled") toast.info("Intelligence refresh cancelled", { description: "Documents completed before cancellation remain available." })
      else toast.error("Intelligence refresh failed", { description: job.error || job.result?.warnings.join(" ") })
      await load(ticker, benchmark, valuationPeriod, marketPeriod)
    } catch (error) {
      toast.error("Intelligence refresh unavailable", { description: message(error) })
    } finally {
      setSourceRefreshStarting(false)
    }
  }
  const cancelSourceRefresh = async () => {
    if (!sourceJob || sourceJob.status !== "running") return
    try {
      const result = await cancelIntelligenceJob(sourceJob.jobId)
      setSourceJob({ ...sourceJob, cancelRequested: result.cancelRequested })
    } catch (error) {
      toast.error("Cancellation request failed", { description: message(error) })
    }
  }

  const quote = market?.quote
  const trailingPe = valuation?.statistics.trailing_pe
  const trailingPeRegime = trailingPe ? valuationRegime(trailingPe).label : "Unavailable"

  return <>
    <div role="region" aria-label="Company Intelligence controls" className="sticky top-0 z-20 flex flex-wrap items-center gap-2 border-b bg-background/92 px-3 py-3 shadow-sm backdrop-blur sm:px-4 xl:px-6"><form className="flex items-center gap-2" onSubmit={submit}><Input aria-label="Company ticker" className="w-28 font-mono font-semibold uppercase" value={tickerInput} maxLength={12} onChange={(event) => setTickerInput(event.target.value.toUpperCase())} /><Button type="submit" variant="outline" disabled={loading}><Search />Research</Button></form><div className="ml-0 flex w-full flex-wrap gap-2 sm:ml-auto sm:w-auto"><Button asChild variant="outline"><a href={labHref("strategy", ticker)}><FlaskConical />Strategy Lab</a></Button><Button asChild variant="outline"><a href={labHref("options", ticker)}><Orbit />Option Lab</a></Button><Button onClick={() => void load(ticker, benchmark, valuationPeriod, marketPeriod)} disabled={loading}><RefreshCw className={loading ? "motion-safe:animate-spin" : ""} />Refresh</Button></div></div>
    <div className="space-y-5 p-3 sm:p-4 xl:p-6"><div className="flex flex-wrap items-end justify-between gap-4 px-1"><div><div className="mb-2 flex flex-wrap items-center gap-2"><Badge className="border-primary/30 bg-primary/10 text-primary">Company Intelligence</Badge><Badge variant="outline">{ticker}</Badge>{overview?.exchange ? <Badge variant="secondary">{overview.exchange}</Badge> : null}</div><h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{overview?.legalName || `${ticker} company research`}</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">One company-oriented surface for market context, point-in-time financials, valuation, earnings evidence, operations, relationships, guidance, and sources.</p></div><div className="font-mono text-[10px] text-muted-foreground"><Database className="mr-1 inline size-3" />{overview?.provenance.source || quote?.dataStatus.source || "Local DuckDB"} · {overview?.provenance.status || quote?.dataStatus.status || (loading ? "Loading" : "Unavailable")}</div></div>
      {errors.length ? <Alert variant={overview || quote ? "default" : "destructive"}><AlertCircle /><AlertTitle>{overview || quote ? "Some Intelligence Is Unavailable" : "Company Setup Required"}</AlertTitle><AlertDescription><ul className="space-y-1">{errors.map((error) => <li key={error}>• {error}</li>)}</ul>{!overview ? <p className="mt-2">Synchronize the SEC identity directory and company facts locally, then refresh this canvas.</p> : null}</AlertDescription></Alert> : null}
      <Tabs value={activeSection} onValueChange={(value) => setActiveSection(value as CompanySection)}><TabsList variant="line" className="grid w-full grid-cols-2 gap-1 group-data-[orientation=horizontal]/tabs:h-auto sm:flex sm:w-full sm:flex-wrap"><TabsTrigger value="overview" className="h-9"><Building2 />Overview</TabsTrigger><TabsTrigger value="financials" className="h-9"><BookOpenCheck />Financials</TabsTrigger><TabsTrigger value="valuation" className="h-9"><TrendingUp />Valuation</TabsTrigger><TabsTrigger value="earnings" className="h-9"><CalendarClock />Earnings</TabsTrigger><TabsTrigger value="operations" className="h-9"><Layers3 />Operations</TabsTrigger><TabsTrigger value="network" className="h-9"><Network />Network</TabsTrigger><TabsTrigger value="guidance" className="h-9"><Target />Guidance</TabsTrigger><TabsTrigger value="sources" className="h-9"><Database />Sources</TabsTrigger></TabsList>
        <TabsContent value="overview" className="space-y-4"><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5"><ComparableMetric label="Market Price" value={quote ? money(quote.price) : "—"} comparison={quote?.changePercent} note={quote ? `${money(quote.change)} versus the prior session` : "Market price is independently unavailable"} /><EvidenceMetric label="Business" value={overview?.sector || "—"} note={overview?.industry || "Sector classification unavailable"} /><EvidenceMetric label="Latest Revenue" value={metricValue(latestRevenue)} note={`TTM ending ${readableDate(latestRevenue?.periodEnd)}`} /><ComparableMetric label="Operating Margin" value={metricValue(latestOperatingMargin)} comparison={operatingMarginChange} comparisonUnit="points" note="Percentage-point comparison with prior TTM" /><div className="rounded-lg border bg-background/45 p-4"><span className="font-mono text-[9px] uppercase tracking-[0.14em] text-muted-foreground">Trailing P/E</span><strong className="mt-2 block text-2xl text-foreground">{multiple(trailingPe?.current, trailingPe?.status)}</strong><Badge variant="outline" className="mt-2">{trailingPeRegime}</Badge><small className="mt-2 block leading-4 text-muted-foreground">Historical context, not a buy or sell signal</small></div></div>
          <Card className="gap-3 py-4"><CardContent className="flex flex-wrap items-center gap-2 px-4 sm:px-5"><div className="mr-2 min-w-44 flex-1"><strong className="text-sm">Local Watchlist</strong><p className="mt-1 text-[10px] text-muted-foreground">Browser-local company navigation only; symbols are not holdings and are never cloud-synced.</p></div>{watchlist.map((symbol) => <Button key={symbol} size="sm" variant={symbol === ticker ? "secondary" : "outline"} aria-pressed={symbol === ticker} onClick={() => openWatchlistTicker(symbol)}>{symbol}</Button>)}<Button size="sm" variant="ghost" onClick={toggleWatchlist}>{watchlist.includes(ticker) ? <StarOff /> : <Star />}{watchlist.includes(ticker) ? `Remove ${ticker}` : `Add ${ticker}`}</Button></CardContent></Card>
          <Card><CardHeader><CardTitle>Research Map</CardTitle><CardDescription>Open the question you are answering. Each section owns its own time controls and failure state.</CardDescription></CardHeader><CardContent className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">{([ ["financials", "How is the business progressing?", `${financials.annual?.metrics.length || 0} annual metric observations`], ["valuation", "How does valuation compare with history?", `${valuation?.statistics ? Object.keys(valuation.statistics).length : 0} measures`], ["earnings", "How has the market reacted to earnings?", `${earnings?.events.length || 0} source-backed events`], ["operations", "What drives reported operations?", `${operations?.series.length || 0} disclosed series`], ["network", "Who appears in the business network?", `${relationships?.relationships.length || 0} disclosed relationships`], ["guidance", "What did management commit to?", `${guidance?.records.length || 0} historical statements`], ["sources", "What evidence is cached locally?", `${sourceHealth?.documentCount || 0} documents`] ] as Array<[CompanySection, string, string]>).map(([section, question, detail]) => <button key={section} type="button" className="rounded-lg border bg-background/45 p-4 text-left transition-colors hover:border-primary/50 focus-visible:ring-2 focus-visible:ring-primary" onClick={() => setActiveSection(section)}><strong className="text-sm">{question}</strong><span className="mt-2 flex items-center justify-between text-[10px] text-muted-foreground">{detail}<ArrowRight className="size-3" /></span></button>)}</CardContent></Card>
          <ProvenanceCard status={quote?.dataStatus} />
        </TabsContent>
        <TabsContent value="financials"><FinancialHistory datasets={financials} /></TabsContent>
        <TabsContent value="valuation" className="space-y-4"><Card><CardHeader><div className="flex flex-wrap items-start justify-between gap-3"><div><CardTitle>Trailing Valuation Versus Its Own History</CardTitle><CardDescription className="mt-2">Weekly observations use only fundamentals known by each US market close. Regimes describe historical location, not attractiveness.</CardDescription></div><Select value={valuationPeriod} onValueChange={(value: ValuationPeriod) => void changeValuationPeriod(value)}><SelectTrigger aria-label="Valuation history window" className="w-36"><SelectValue /></SelectTrigger><SelectContent>{Object.entries(valuationPeriods).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select></div></CardHeader><CardContent className="grid gap-3 border-t pt-5 sm:grid-cols-2 xl:grid-cols-3">{valuationIds.map((metricId) => <ValuationCard key={metricId} statistics={valuation?.statistics[metricId]} />)}{valuationLoading ? <div className="grid min-h-32 place-items-center text-sm text-muted-foreground"><RefreshCw className="mr-2 inline size-4 motion-safe:animate-spin" />Refreshing valuation history…</div> : null}</CardContent></Card><Card><CardHeader><CardTitle>Historical Valuation Path</CardTitle><CardDescription>Fixed weekly observations and their point-in-time fundamental inputs remain inspectable across the selected valuation window.</CardDescription></CardHeader><CardContent><ValuationHistoryChart valuation={valuation} /></CardContent></Card>{valuation?.warnings.length ? <Alert><AlertCircle /><AlertTitle>Valuation Assumptions</AlertTitle><AlertDescription>{valuation.warnings.join(" ")} Enterprise value uses market capitalization plus debt minus cash; values may differ from commercial vendors.</AlertDescription></Alert> : null}</TabsContent>
        <TabsContent value="earnings" className="space-y-4"><Card className="gap-4"><CardHeader><div className="flex flex-wrap items-start justify-between gap-3"><div><CardTitle>Historical Earnings Reaction</CardTitle><CardDescription className="mt-2">Reported results and calculated market behavior stay visually distinct. Event chart defaults to three years and can load five.</CardDescription></div><form className="flex items-center gap-2" onSubmit={(event) => void submitBenchmark(event)}><Input aria-label="Earnings benchmark" className="w-28 font-mono font-semibold uppercase" value={benchmarkInput} maxLength={12} onChange={(event) => setBenchmarkInput(event.target.value.toUpperCase())} /><Button type="submit" size="sm" variant="outline" disabled={earningsLoading}>{earningsLoading ? <RefreshCw className="motion-safe:animate-spin" /> : <Search />}Compare</Button></form></div></CardHeader><CardContent className="grid gap-3 border-t pt-5 sm:grid-cols-2 xl:grid-cols-5"><EvidenceMetric label="Typical |D0| Move" value={percentage(earnings?.aggregate.typicalAbsoluteEventMove)} note={`${earnings?.aggregate.sampleSize || 0} event sample`} /><EvidenceMetric label="Positive D0 Frequency" value={percentage(earnings?.aggregate.positiveReactionFrequency)} note="Direction frequency, not forecast" /><EvidenceMetric label="Median D+5 Drift" value={percentage(earnings?.aggregate.medianD5Return)} note="Cumulative from prior close" /><EvidenceMetric label="Median D+20 Drift" value={percentage(earnings?.aggregate.medianD20Return)} note="Unadjusted stock return" /><EvidenceMetric label="Historical D0 Range" value={earnings?.aggregate.eventMoveMinimum === null || earnings?.aggregate.eventMoveMinimum === undefined ? "—" : `${percentage(earnings.aggregate.eventMoveMinimum)} to ${percentage(earnings.aggregate.eventMoveMaximum)}`} note={`${earnings?.aggregate.sampleSize || 0} usable · ${earnings?.aggregate.excludedEvents || 0} excluded`} /></CardContent></Card>
          {earnings?.events.length ? <div className="grid gap-4 2xl:grid-cols-[minmax(420px,0.72fr)_minmax(680px,1.35fr)]"><Card className="gap-0 overflow-hidden py-0"><CardHeader className="border-b py-5"><CardTitle className="text-base">Event History</CardTitle><CardDescription>All supported events remain available. Select one to focus its candlestick evidence.</CardDescription></CardHeader><EventList events={earnings.events} selectedId={selectedAnalysis?.event.eventId} onSelect={(analysis) => setSelectedEventId(analysis.event.eventId)} /></Card><Card className="gap-4"><CardHeader><CardTitle className="text-base">Event Evidence</CardTitle><CardDescription>Price and volume are calculated observations; reported values come from SEC facts.</CardDescription></CardHeader><CardContent>{selectedAnalysis ? <EventDetail analysis={selectedAnalysis} market={market} marketPeriod={marketPeriod} marketLoading={marketLoading} onMarketPeriodChange={(period) => void changeMarketPeriod(period)} /> : null}</CardContent></Card></div> : <Card><CardContent className="grid min-h-56 place-items-center text-center"><div><Building2 className="mx-auto size-8 text-muted-foreground" /><h3 className="mt-3 font-semibold">No earnings events are available.</h3><p className="mt-2 max-w-md text-sm text-muted-foreground">Load point-in-time SEC Company Facts for this supported company. The canvas will not fabricate event dates or consensus data.</p></div></CardContent></Card>}
          <Alert><AlertCircle /><AlertTitle>Historical Evidence, Not A Forecast</AlertTitle><AlertDescription>{earnings?.warnings.join(" ") || "Historical earnings reactions do not predict the next earnings reaction. Consensus and guidance comparisons remain unavailable without an approved estimates source."}</AlertDescription></Alert>
        </TabsContent>
        <TabsContent value="operations"><OperationsIntelligence operations={operations} /></TabsContent>
        <TabsContent value="network"><RelationshipNetwork network={relationships} ticker={ticker} /></TabsContent>
        <TabsContent value="guidance"><GuidanceTimeline guidance={guidance} /></TabsContent>
        <TabsContent value="sources" className="space-y-4"><Card><CardHeader><div className="flex flex-wrap items-start justify-between gap-3"><div><CardTitle>Public Intelligence Sources</CardTitle><CardDescription className="mt-2">Discover permitted SEC filings, cache changed documents locally, and populate only evidence-backed claims.</CardDescription></div><div className="flex gap-2">{sourceJob?.status === "running" ? <Button variant="outline" onClick={() => void cancelSourceRefresh()} disabled={sourceJob.cancelRequested}>{sourceJob.cancelRequested ? "Cancelling…" : "Cancel"}</Button> : null}<Button onClick={() => void refreshSources()} disabled={sourceRefreshStarting || sourceJob?.status === "running"}><RefreshCw className={sourceRefreshStarting || sourceJob?.status === "running" ? "motion-safe:animate-spin" : ""} />Refresh Intelligence Sources</Button></div></div></CardHeader><CardContent className="space-y-4">{sourceJob?.status === "running" ? <div className="space-y-2 rounded-lg border p-3"><div className="flex justify-between text-xs"><span>{sourceJob.cancelRequested ? "Stopping after the current document" : "Collecting and parsing SEC evidence"}</span><strong>{Math.round(sourceJob.progress * 100)}%</strong></div><div role="progressbar" aria-label="Intelligence source refresh progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(sourceJob.progress * 100)} className="h-2 overflow-hidden rounded-full bg-muted"><div className="h-full bg-primary transition-[width]" style={{ width: `${sourceJob.progress * 100}%` }} /></div></div> : null}<div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{(sourceHealth?.coverage || []).map((coverage) => <div key={coverage.module} className="rounded-lg border bg-background/45 p-4"><div className="flex items-start justify-between gap-2"><span className="font-medium capitalize">{coverage.module}</span><Badge variant={coverage.status === "populated" ? "secondary" : coverage.status.includes("failed") ? "destructive" : "outline"}>{readableStatus(coverage.status)}</Badge></div><strong className="mt-3 block text-2xl">{coverage.recordCount}</strong><p className="mt-2 text-xs leading-5 text-muted-foreground">{coverage.message}</p></div>)}</div>{!sourceHealth?.coverage.length ? <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">Source health is unavailable. Reload the view, then retry the SEC refresh.</div> : null}<div className="flex flex-wrap gap-x-5 gap-y-2 font-mono text-[10px] text-muted-foreground"><span>{sourceHealth?.documentCount || 0} cached documents</span><span>{sourceHealth?.parsedDocumentCount || 0} parsed</span><span>{sourceHealth?.failedDocumentCount || 0} failed</span><span>Last run {sourceHealth?.lastRefresh?.completedAt ? new Date(sourceHealth.lastRefresh.completedAt).toLocaleString() : "not yet run"}</span></div>{sourceHealth?.warnings.length ? <Alert><AlertCircle /><AlertTitle>Source Coverage Notes</AlertTitle><AlertDescription>{sourceHealth.warnings.join(" ")}</AlertDescription></Alert> : null}</CardContent></Card><div className="grid gap-4 xl:grid-cols-2"><Card><CardHeader><CardTitle>Company Identity</CardTitle><CardDescription>Durable company identity is separate from the current security ticker.</CardDescription></CardHeader><CardContent className="space-y-3 text-sm"><div className="rounded-lg border p-3"><span className="text-muted-foreground">CIK</span><strong className="ml-3 font-mono">{overview?.cik || "—"}</strong></div><div className="rounded-lg border p-3"><span className="text-muted-foreground">Identity Source</span><strong className="ml-3">{overview?.provenance.source || "—"}</strong></div><div className="rounded-lg border p-3"><span className="text-muted-foreground">Known At</span><strong className="ml-3">{overview ? new Date(overview.provenance.knownAt).toLocaleString() : "—"}</strong></div></CardContent></Card><Card><CardHeader><CardTitle>Research Provenance</CardTitle><CardDescription>Every relationship, operating observation, and commitment exposes exact source evidence; prices remain delayed public observations.</CardDescription></CardHeader><CardContent className="space-y-3 text-sm"><div className="rounded-lg border p-3"><span className="text-muted-foreground">Event Source</span><strong className="ml-3">{earnings?.provenance.eventSource || "SEC EDGAR"}</strong></div><div className="rounded-lg border p-3"><span className="text-muted-foreground">Price Source</span><strong className="ml-3">{earnings?.provenance.priceSource || "Public market provider"}</strong></div><div className="rounded-lg border p-3"><span className="text-muted-foreground">Evidence Coverage</span><strong className="ml-3">{relationships?.relationships.length || 0} relationships · {operations?.series.length || 0} operating series · {guidance?.records.length || 0} guidance records</strong></div></CardContent></Card></div></TabsContent>
      </Tabs>
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-dashed px-4 py-3 text-xs text-muted-foreground"><span>Educational US company research. Public data can be delayed, incomplete, or revised.</span><button type="button" className="inline-flex items-center gap-1 text-foreground hover:text-primary" onClick={() => setActiveSection("earnings")}>Inspect event market context<ArrowRight className="size-3" /></button></div>
    </div>
  </>
}
