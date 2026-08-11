import { useCallback, useEffect, useMemo, useState } from "react"
import {
  AlertCircle,
  ArrowRight,
  BookOpenCheck,
  Building2,
  CalendarClock,
  Database,
  ExternalLink,
  FileCheck2,
  FlaskConical,
  LineChart,
  Orbit,
  RefreshCw,
  Search,
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
import { EarningsReactionChart } from "@/features/company-intelligence/earnings-reaction-chart"
import {
  ApiError,
  loadCompanyEarnings,
  loadCompanyMetrics,
  loadCompanyOverview,
  loadCompanyValuation,
} from "@/lib/api"
import { ordinal } from "@/lib/format"
import { labHref, normalizeTicker } from "@/lib/navigation"
import type {
  CompanyMetric,
  CompanyMetricsResponse,
  CompanyOverview,
  EarningsEventAnalysis,
  EarningsHistoryResponse,
  HistoricalValuationResponse,
  ValuationStatistics,
} from "@/lib/types"
import { cn } from "@/lib/utils"

type ValuationPeriod = "1y" | "3y" | "5y" | "10y" | "max"

const valuationPeriods: Record<ValuationPeriod, string> = {
  "1y": "1 Year",
  "3y": "3 Years",
  "5y": "5 Years",
  "10y": "10 Years",
  max: "Maximum",
}

const coreMetricIds = [
  "revenue",
  "revenue_growth",
  "net_income",
  "diluted_eps",
  "gross_margin",
  "operating_margin",
  "free_cash_flow",
  "return_on_invested_capital",
]

const valuationIds = ["trailing_pe", "price_to_sales", "price_to_book", "ev_to_revenue", "price_to_fcf", "fcf_yield"]

function message(error: unknown) {
  if (error instanceof ApiError || error instanceof Error) return error.message
  return "Company Intelligence could not load this research surface."
}

function compact(value: number) {
  return Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 2 }).format(value)
}

function metricValue(metric?: { value: number | null; unit: string } | null) {
  if (!metric || metric.value === null) return "—"
  if (metric.unit === "USD") return `$${compact(metric.value)}`
  if (metric.unit === "USD/share") return `$${metric.value.toFixed(2)}`
  if (metric.unit === "%") return `${metric.value >= 0 ? "+" : ""}${metric.value.toFixed(2)}%`
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

function latestMetric(metrics: CompanyMetric[], metricId: string) {
  return metrics.filter((metric) => metric.metricId === metricId).sort((left, right) => left.periodEnd.localeCompare(right.periodEnd)).at(-1)
}

function periodMetric(metrics: CompanyMetric[], metricId: string, periodEnd: string) {
  return metrics.find((metric) => metric.metricId === metricId && metric.periodEnd === periodEnd)
}

function EvidenceMetric({ label, value, note, tone = "default" }: { label: string; value: string; note: string; tone?: "default" | "positive" | "negative" }) {
  return <div className="rounded-lg border bg-background/45 p-4"><span className="font-mono text-[9px] uppercase tracking-[0.14em] text-muted-foreground">{label}</span><strong className={cn("mt-2 block text-xl", tone === "positive" && "text-primary", tone === "negative" && "text-destructive")}>{value}</strong><small className="mt-1 block leading-4 text-muted-foreground">{note}</small></div>
}

function ValuationCard({ statistics }: { statistics?: ValuationStatistics }) {
  if (!statistics) return null
  const isYield = statistics.unit === "%"
  const current = isYield ? percentage(statistics.current) : multiple(statistics.current, statistics.status)
  const medianValue = isYield ? percentage(statistics.median) : multiple(statistics.median)
  return <div className="rounded-lg border bg-background/45 p-4"><div className="flex items-start justify-between gap-2"><span className="text-sm font-medium">{statistics.label}</span><Badge variant={statistics.status === "available" ? "outline" : "secondary"}>{statistics.status === "nm" ? "NM" : statistics.status}</Badge></div><strong className="mt-3 block text-2xl">{current}</strong><div className="mt-3 grid grid-cols-2 gap-2 font-mono text-[9px] text-muted-foreground"><span>Median <b className="block text-foreground">{medianValue}</b></span><span>Percentile <b className="block text-foreground">{statistics.percentile === null ? "—" : ordinal(statistics.percentile)}</b></span></div><p className="mt-3 text-[10px] text-muted-foreground">{statistics.sampleSize} usable observations</p></div>
}

function EventList({ events, selectedId, onSelect }: { events: EarningsEventAnalysis[]; selectedId?: string; onSelect: (analysis: EarningsEventAnalysis) => void }) {
  return <ScrollArea className="h-[560px]"><Table><TableHeader><TableRow><TableHead>Fiscal Event</TableHead><TableHead>Reported</TableHead><TableHead>D0</TableHead><TableHead>D+5</TableHead><TableHead>D+20 Adj.</TableHead><TableHead>Volume</TableHead></TableRow></TableHeader><TableBody>{events.map((analysis) => {
    const event = analysis.event
    const reaction = analysis.reaction
    const revenue = event.reportedMetrics.revenue
    const eps = event.reportedMetrics.diluted_eps
    const selected = event.eventId === selectedId
    return <TableRow key={event.eventId} data-state={selected ? "selected" : undefined}><TableCell><button type="button" aria-pressed={selected} className="min-w-36 rounded-md p-2 text-left focus-visible:ring-2 focus-visible:ring-primary" onClick={() => onSelect(analysis)}><strong className="block">{event.fiscalPeriod || "FY"} {event.fiscalYear || ""}</strong><span className="mt-1 block text-[10px] text-muted-foreground">{readableDate(event.announcementDate)}</span><Badge variant="outline" className="mt-2 text-[8px]">{event.session.replace("_", " ")}</Badge></button></TableCell><TableCell><span className="block text-xs">Rev {metricValue(revenue)}</span><span className="mt-1 block text-[10px] text-muted-foreground">EPS {metricValue(eps)}</span></TableCell><TableCell className={cn((reaction.windows.d0?.stockReturn || 0) < 0 && "text-destructive")}>{percentage(reaction.windows.d0?.stockReturn)}</TableCell><TableCell>{percentage(reaction.windows.d5?.stockReturn)}</TableCell><TableCell>{percentage(reaction.windows.d20?.benchmarkAdjustedReturn)}</TableCell><TableCell>{reaction.abnormalVolume === null ? "—" : `${reaction.abnormalVolume.toFixed(2)}×`}<small className="block text-[9px] text-muted-foreground">{reaction.volumePercentile === null ? "No rank" : `${ordinal(reaction.volumePercentile)} pct.`}</small></TableCell></TableRow>
  })}</TableBody></Table></ScrollArea>
}

function EventDetail({ analysis }: { analysis: EarningsEventAnalysis }) {
  const { event, reaction } = analysis
  const reported = Object.values(event.reportedMetrics)
  return <div className="space-y-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="flex flex-wrap items-center gap-2"><Badge>{event.fiscalPeriod || "FY"} {event.fiscalYear}</Badge><Badge variant="outline">{event.session.replace("_", " ")}</Badge><Badge variant={event.timingQuality === "exact" ? "secondary" : "outline"}>{event.timingQuality === "exact" ? "Exact SEC Time" : "Date Only"}</Badge></div><h3 className="mt-3 text-xl font-semibold">Event anchored to {readableDate(reaction.anchorSession)}</h3><p className="mt-1 text-xs text-muted-foreground">Fiscal period ended {readableDate(event.periodEnd)} · baseline {readableDate(reaction.priorSession)}</p></div><Button asChild variant="outline"><a href={event.evidence.filingUrl} target="_blank" rel="noreferrer"><FileCheck2 />Open SEC Filing<ExternalLink /></a></Button></div>
    <div className="grid gap-3 xl:grid-cols-2"><Card className="gap-3 py-4"><CardHeader className="px-4"><div className="flex items-center gap-2"><BookOpenCheck className="size-4 text-primary" /><CardTitle className="text-sm">Reported Facts</CardTitle></div><CardDescription>Normalized SEC values for the fiscal period.</CardDescription></CardHeader><CardContent className="grid gap-2 px-4 sm:grid-cols-2">{reported.length ? reported.map((metric) => <EvidenceMetric key={metric.metricId} label={metric.label} value={metricValue(metric)} note={`${metric.sourceFactIds.length} source fact${metric.sourceFactIds.length === 1 ? "" : "s"}`} />) : <p className="text-sm text-muted-foreground">No supported normalized result was available.</p>}</CardContent></Card><Card className="gap-3 py-4"><CardHeader className="px-4"><div className="flex items-center gap-2"><TrendingUp className="size-4 text-chart-2" /><CardTitle className="text-sm">Calculated Market Reaction</CardTitle></div><CardDescription>Session-aware price and volume evidence, not a reported company fact.</CardDescription></CardHeader><CardContent className="grid gap-2 px-4 sm:grid-cols-2"><EvidenceMetric label="Opening Gap" value={percentage(reaction.openingGap)} note="Anchor open vs prior close" /><EvidenceMetric label="D0 Move" value={percentage(reaction.windows.d0?.stockReturn)} note="Prior close to anchor close" tone={(reaction.windows.d0?.stockReturn || 0) < 0 ? "negative" : "positive"} /><EvidenceMetric label="D+20 Adjusted" value={percentage(reaction.windows.d20?.benchmarkAdjustedReturn)} note={`Less ${reaction.benchmarkTicker} over identical sessions`} /><EvidenceMetric label="Abnormal Volume" value={reaction.abnormalVolume === null ? "—" : `${reaction.abnormalVolume.toFixed(2)}×`} note={reaction.volumePercentile === null ? "Insufficient prior volume" : `${ordinal(reaction.volumePercentile)} historical percentile`} /></CardContent></Card></div>
    <EarningsReactionChart analysis={analysis} />
    <div className="rounded-lg border border-dashed p-4 text-xs text-muted-foreground"><strong className="text-foreground">Evidence:</strong> {event.evidence.source} · {event.evidence.filingForm} · accession {event.evidence.accessionNumber} · known {new Date(event.evidence.knownAt).toLocaleString()}. {event.warnings.concat(reaction.warnings).join(" ")}</div>
  </div>
}

export function CompanyIntelligence({ initialTicker = "NVDA" }: { initialTicker?: string }) {
  const initial = normalizeTicker(initialTicker)
  const [tickerInput, setTickerInput] = useState(initial)
  const [ticker, setTicker] = useState(initial)
  const [benchmarkInput, setBenchmarkInput] = useState("SPY")
  const [benchmark, setBenchmark] = useState("SPY")
  const [valuationPeriod, setValuationPeriod] = useState<ValuationPeriod>("5y")
  const [overview, setOverview] = useState<CompanyOverview | null>(null)
  const [metrics, setMetrics] = useState<CompanyMetricsResponse | null>(null)
  const [valuation, setValuation] = useState<HistoricalValuationResponse | null>(null)
  const [earnings, setEarnings] = useState<EarningsHistoryResponse | null>(null)
  const [selectedEventId, setSelectedEventId] = useState<string>()
  const [loading, setLoading] = useState(false)
  const [errors, setErrors] = useState<string[]>([])

  const load = useCallback(async (symbol: string, selectedBenchmark: string, period: ValuationPeriod) => {
    const normalizedTicker = normalizeTicker(symbol, "")
    const normalizedBenchmark = normalizeTicker(selectedBenchmark, "SPY")
    if (!normalizedTicker) return toast.error("Enter a supported US market ticker.")
    setLoading(true)
    setErrors([])
    setTicker(normalizedTicker)
    setTickerInput(normalizedTicker)
    setBenchmark(normalizedBenchmark)
    setBenchmarkInput(normalizedBenchmark)
    const results = await Promise.allSettled([
      loadCompanyOverview(normalizedTicker),
      loadCompanyMetrics(normalizedTicker, "ttm"),
      loadCompanyValuation(normalizedTicker, period, "weekly"),
      loadCompanyEarnings(normalizedTicker, normalizedBenchmark),
    ])
    const [overviewResult, metricsResult, valuationResult, earningsResult] = results
    if (overviewResult.status === "fulfilled") setOverview(overviewResult.value); else setOverview(null)
    if (metricsResult.status === "fulfilled") setMetrics(metricsResult.value); else setMetrics(null)
    if (valuationResult.status === "fulfilled") setValuation(valuationResult.value); else setValuation(null)
    if (earningsResult.status === "fulfilled") {
      setEarnings(earningsResult.value)
      setSelectedEventId(earningsResult.value.events[0]?.event.eventId)
    } else {
      setEarnings(null)
      setSelectedEventId(undefined)
    }
    const failures = results.filter((result): result is PromiseRejectedResult => result.status === "rejected").map((result) => message(result.reason))
    setErrors([...new Set(failures)])
    if (failures.length === results.length) toast.error("Company Intelligence unavailable", { description: failures[0] })
    setLoading(false)
  }, [])

  useEffect(() => { void load(initial, "SPY", "5y") }, [initial, load])

  const selectedAnalysis = useMemo(
    () => earnings?.events.find((analysis) => analysis.event.eventId === selectedEventId) || earnings?.events[0],
    [earnings, selectedEventId],
  )
  const financialPeriods = useMemo(
    () => [...new Set((metrics?.metrics || []).map((metric) => metric.periodEnd))].sort().reverse().slice(0, 12),
    [metrics],
  )
  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    void load(tickerInput, benchmarkInput, valuationPeriod)
  }

  return <>
    <div role="region" aria-label="Company Intelligence controls" className="sticky top-0 z-20 flex flex-wrap items-center gap-2 border-b bg-background/92 px-3 py-3 shadow-sm backdrop-blur sm:px-4 xl:px-6"><form className="flex flex-wrap items-center gap-2" onSubmit={submit}><Input aria-label="Company ticker" className="w-28 font-mono font-semibold uppercase" value={tickerInput} maxLength={12} onChange={(event) => setTickerInput(event.target.value.toUpperCase())} /><Input aria-label="Earnings benchmark" className="w-28 font-mono font-semibold uppercase" value={benchmarkInput} maxLength={12} onChange={(event) => setBenchmarkInput(event.target.value.toUpperCase())} /><Button type="submit" variant="outline" disabled={loading}><Search />Research</Button></form><Select value={valuationPeriod} onValueChange={(value: ValuationPeriod) => { setValuationPeriod(value); void load(ticker, benchmark, value) }}><SelectTrigger aria-label="Valuation history window" className="w-36"><SelectValue /></SelectTrigger><SelectContent>{Object.entries(valuationPeriods).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select><div className="ml-0 flex w-full flex-wrap gap-2 sm:ml-auto sm:w-auto"><Button asChild variant="outline"><a href={labHref("stock", ticker)}><LineChart />Market View</a></Button><Button asChild variant="outline"><a href={labHref("strategy", ticker)}><FlaskConical />Strategy Lab</a></Button><Button asChild variant="outline"><a href={labHref("options", ticker)}><Orbit />Option Lab</a></Button><Button onClick={() => void load(ticker, benchmark, valuationPeriod)} disabled={loading}><RefreshCw className={loading ? "motion-safe:animate-spin" : ""} />Refresh</Button></div></div>
    <div className="space-y-5 p-3 sm:p-4 xl:p-6"><div className="flex flex-wrap items-end justify-between gap-4 px-1"><div><div className="mb-2 flex flex-wrap items-center gap-2"><Badge className="border-primary/30 bg-primary/10 text-primary">Company Intelligence</Badge><Badge variant="outline">{ticker}</Badge>{overview?.exchange ? <Badge variant="secondary">{overview.exchange}</Badge> : null}</div><h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{overview?.legalName || `${ticker} business evidence`}</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">Point-in-time financials, trailing valuation, and historical earnings reactions—kept separate from prediction and trade execution.</p></div><div className="font-mono text-[10px] text-muted-foreground"><Database className="mr-1 inline size-3" />{overview?.provenance.source || "Local DuckDB"} · {overview?.provenance.status || (loading ? "Loading" : "Unavailable")}</div></div>
      {errors.length ? <Alert variant={overview ? "default" : "destructive"}><AlertCircle /><AlertTitle>{overview ? "Some Intelligence Is Unavailable" : "Company Setup Required"}</AlertTitle><AlertDescription><ul className="space-y-1">{errors.map((error) => <li key={error}>• {error}</li>)}</ul>{!overview ? <p className="mt-2">Synchronize the SEC identity directory and company facts locally, then refresh this canvas.</p> : null}</AlertDescription></Alert> : null}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><EvidenceMetric label="Business" value={overview?.sector || "—"} note={overview?.industry || "Sector classification unavailable"} /><EvidenceMetric label="Latest Revenue" value={metricValue(latestMetric(metrics?.metrics || [], "revenue"))} note={`TTM ending ${readableDate(latestMetric(metrics?.metrics || [], "revenue")?.periodEnd)}`} /><EvidenceMetric label="Operating Margin" value={metricValue(latestMetric(metrics?.metrics || [], "operating_margin"))} note="Normalized SEC evidence" /><EvidenceMetric label="Trailing P/E" value={multiple(valuation?.statistics.trailing_pe?.current, valuation?.statistics.trailing_pe?.status)} note={valuation?.statistics.trailing_pe?.percentile === null || valuation?.statistics.trailing_pe?.percentile === undefined ? "Historical rank unavailable" : `${ordinal(valuation.statistics.trailing_pe.percentile)} percentile over ${valuationPeriods[valuationPeriod]}`} /></div>
      <Tabs defaultValue="earnings"><TabsList variant="line" className="grid w-full grid-cols-2 gap-1 group-data-[orientation=horizontal]/tabs:h-auto sm:inline-flex sm:w-fit sm:group-data-[orientation=horizontal]/tabs:h-9"><TabsTrigger value="earnings" className="h-9 sm:h-[calc(100%-1px)]"><CalendarClock />Earnings Explorer</TabsTrigger><TabsTrigger value="financials" className="h-9 sm:h-[calc(100%-1px)]"><BookOpenCheck />Financial History</TabsTrigger><TabsTrigger value="valuation" className="h-9 sm:h-[calc(100%-1px)]"><TrendingUp />Valuation</TabsTrigger><TabsTrigger value="sources" className="h-9 sm:h-[calc(100%-1px)]"><Database />Sources</TabsTrigger></TabsList>
        <TabsContent value="earnings" className="space-y-4"><Card className="gap-4"><CardHeader><div className="flex flex-wrap items-start justify-between gap-3"><div><CardTitle>Historical Earnings Reaction</CardTitle><CardDescription className="mt-2">Reported results and calculated market behavior stay visually distinct. Benchmark: {earnings?.benchmarkTicker || benchmark}.</CardDescription></div><Badge variant="outline">{earnings?.aggregate.sampleSize || 0} usable events · {earnings?.aggregate.excludedEvents || 0} excluded</Badge></div></CardHeader><CardContent className="grid gap-3 border-t pt-5 sm:grid-cols-2 xl:grid-cols-5"><EvidenceMetric label="Typical |D0| Move" value={percentage(earnings?.aggregate.typicalAbsoluteEventMove)} note={`${earnings?.aggregate.sampleSize || 0} event sample`} /><EvidenceMetric label="Positive D0 Frequency" value={percentage(earnings?.aggregate.positiveReactionFrequency)} note="Direction frequency, not forecast" /><EvidenceMetric label="Median D+5 Drift" value={percentage(earnings?.aggregate.medianD5Return)} note="Cumulative from prior close" /><EvidenceMetric label="Median D+20 Drift" value={percentage(earnings?.aggregate.medianD20Return)} note="Unadjusted stock return" /><EvidenceMetric label="Historical D0 Range" value={earnings?.aggregate.eventMoveMinimum === null || earnings?.aggregate.eventMoveMinimum === undefined ? "—" : `${percentage(earnings.aggregate.eventMoveMinimum)} to ${percentage(earnings.aggregate.eventMoveMaximum)}`} note="Observed sample only" /></CardContent></Card>
          {earnings?.events.length ? <div className="grid gap-4 2xl:grid-cols-[minmax(520px,0.9fr)_minmax(620px,1.25fr)]"><Card className="gap-0 overflow-hidden py-0"><CardHeader className="border-b py-5"><CardTitle className="text-base">Event History</CardTitle><CardDescription>Select a fiscal event to inspect its exact evidence and aligned path.</CardDescription></CardHeader><EventList events={earnings.events} selectedId={selectedAnalysis?.event.eventId} onSelect={(analysis) => setSelectedEventId(analysis.event.eventId)} /></Card><Card className="gap-4"><CardHeader><CardTitle className="text-base">Event Evidence</CardTitle><CardDescription>Price and volume are calculated observations; reported values come from SEC facts.</CardDescription></CardHeader><CardContent>{selectedAnalysis ? <EventDetail analysis={selectedAnalysis} /> : null}</CardContent></Card></div> : <Card><CardContent className="grid min-h-56 place-items-center text-center"><div><Building2 className="mx-auto size-8 text-muted-foreground" /><h3 className="mt-3 font-semibold">No earnings events are available.</h3><p className="mt-2 max-w-md text-sm text-muted-foreground">Load point-in-time SEC Company Facts for this supported company. The canvas will not fabricate event dates or consensus data.</p></div></CardContent></Card>}
          <Alert><AlertCircle /><AlertTitle>Historical Evidence, Not A Forecast</AlertTitle><AlertDescription>{earnings?.warnings.join(" ") || "Historical earnings reactions do not predict the next earnings reaction. Consensus and guidance comparisons remain unavailable without an approved estimates source."}</AlertDescription></Alert>
        </TabsContent>
        <TabsContent value="financials" className="space-y-4"><Card><CardHeader><CardTitle>Latest Normalized TTM Evidence</CardTitle><CardDescription>Definitions are versioned and every non-null value links back to SEC source facts.</CardDescription></CardHeader><CardContent className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{coreMetricIds.map((metricId) => { const metric = latestMetric(metrics?.metrics || [], metricId); return <EvidenceMetric key={metricId} label={metric?.label || metricId.replaceAll("_", " ")} value={metricValue(metric)} note={metric ? `${readableDate(metric.periodEnd)} · ${metric.sourceFactIds.length} source facts` : "Required SEC inputs unavailable"} /> })}</CardContent></Card><Card className="gap-0 overflow-hidden py-0"><CardHeader className="border-b py-5"><CardTitle>TTM Financial Progression</CardTitle><CardDescription>Compare only normalized periods available inside the current as-of boundary.</CardDescription></CardHeader><Table><TableHeader><TableRow><TableHead>Period End</TableHead><TableHead>Revenue</TableHead><TableHead>Growth</TableHead><TableHead>Diluted EPS</TableHead><TableHead>Gross Margin</TableHead><TableHead>Operating Margin</TableHead><TableHead>Free Cash Flow</TableHead></TableRow></TableHeader><TableBody>{financialPeriods.map((periodEnd) => <TableRow key={periodEnd}><TableCell className="font-mono text-xs">{periodEnd}</TableCell><TableCell>{metricValue(periodMetric(metrics?.metrics || [], "revenue", periodEnd))}</TableCell><TableCell>{metricValue(periodMetric(metrics?.metrics || [], "revenue_growth", periodEnd))}</TableCell><TableCell>{metricValue(periodMetric(metrics?.metrics || [], "diluted_eps", periodEnd))}</TableCell><TableCell>{metricValue(periodMetric(metrics?.metrics || [], "gross_margin", periodEnd))}</TableCell><TableCell>{metricValue(periodMetric(metrics?.metrics || [], "operating_margin", periodEnd))}</TableCell><TableCell>{metricValue(periodMetric(metrics?.metrics || [], "free_cash_flow", periodEnd))}</TableCell></TableRow>)}</TableBody></Table>{!financialPeriods.length ? <div className="grid h-40 place-items-center text-sm text-muted-foreground">No complete TTM periods are available.</div> : null}</Card></TabsContent>
        <TabsContent value="valuation" className="space-y-4"><Card><CardHeader><div className="flex flex-wrap items-start justify-between gap-3"><div><CardTitle>Trailing Valuation Versus Its Own History</CardTitle><CardDescription className="mt-2">Weekly observations use only fundamentals known by each US market close.</CardDescription></div><Badge variant="outline">{valuationPeriods[valuationPeriod]} · {valuation?.frequency || "weekly"}</Badge></div></CardHeader><CardContent className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{valuationIds.map((metricId) => <ValuationCard key={metricId} statistics={valuation?.statistics[metricId]} />)}</CardContent></Card>{valuation?.warnings.length ? <Alert><AlertCircle /><AlertTitle>Valuation Assumptions</AlertTitle><AlertDescription>{valuation.warnings.join(" ")} Enterprise value uses market capitalization plus debt minus cash; values may differ from commercial vendors.</AlertDescription></Alert> : null}</TabsContent>
        <TabsContent value="sources"><div className="grid gap-4 xl:grid-cols-2"><Card><CardHeader><CardTitle>Company Identity</CardTitle><CardDescription>Durable company identity is separate from the current security ticker.</CardDescription></CardHeader><CardContent className="space-y-3 text-sm"><div className="rounded-lg border p-3"><span className="text-muted-foreground">CIK</span><strong className="ml-3 font-mono">{overview?.cik || "—"}</strong></div><div className="rounded-lg border p-3"><span className="text-muted-foreground">Identity Source</span><strong className="ml-3">{overview?.provenance.source || "—"}</strong></div><div className="rounded-lg border p-3"><span className="text-muted-foreground">Known At</span><strong className="ml-3">{overview ? new Date(overview.provenance.knownAt).toLocaleString() : "—"}</strong></div></CardContent></Card><Card><CardHeader><CardTitle>Research Provenance</CardTitle><CardDescription>Every event exposes first-party evidence; prices remain delayed public observations.</CardDescription></CardHeader><CardContent className="space-y-3 text-sm"><div className="rounded-lg border p-3"><span className="text-muted-foreground">Event Source</span><strong className="ml-3">{earnings?.provenance.eventSource || "SEC EDGAR"}</strong></div><div className="rounded-lg border p-3"><span className="text-muted-foreground">Price Source</span><strong className="ml-3">{earnings?.provenance.priceSource || "Yahoo Finance"}</strong></div><div className="rounded-lg border p-3"><span className="text-muted-foreground">Source Facts</span><strong className="ml-3">{earnings?.provenance.sourceFactIds.length || 0}</strong></div></CardContent></Card></div></TabsContent>
      </Tabs>
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-dashed px-4 py-3 text-xs text-muted-foreground"><span>Educational US company research. Public data can be delayed, incomplete, or revised.</span><a className="inline-flex items-center gap-1 text-foreground hover:text-primary" href={labHref("stock", ticker)}>Inspect market context<ArrowRight className="size-3" /></a></div>
    </div>
  </>
}
