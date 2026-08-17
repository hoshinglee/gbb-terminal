import { useCallback, useEffect, useMemo, useState } from "react"
import { AlertCircle, ArrowRight, Clock3, Database, DownloadCloud, Gauge, RefreshCw, Server, ShieldCheck, TrendingDown, TrendingUp, XCircle } from "lucide-react"
import { toast } from "sonner"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ApiError, cancelUniverseJob, loadMarketOverview, loadSectorConstituents, loadSp500UniverseStatus, loadUniverseJob, refreshSp500Universe } from "@/lib/api"
import { labHref } from "@/lib/navigation"
import type { LocalUniverseJob, MarketOverviewResponse, MarketOverviewRow, SectorConstituentSnapshot, UniverseStatusResponse } from "@/lib/types"
import { cn } from "@/lib/utils"
import { SectorConstituents } from "@/features/market-pulse/sector-constituents"

function errorMessage(error: unknown) {
  if (error instanceof ApiError || error instanceof Error) return error.message
  return "The market-observability request failed unexpectedly."
}

function money(value: number | null) {
  return value === null ? "Unavailable" : value.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 })
}

function signedPercent(value: number | null) {
  return value === null ? "—" : `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`
}

function observedAt(row?: MarketOverviewRow) {
  const value = row?.dataStatus.knownAt || row?.dataStatus.observationTimestamp
  if (!value) return "Not Reported"
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString()
}

export function summarizeSectors(sectors: MarketOverviewRow[]) {
  const available = sectors.filter((row) => row.available && row.changePercent !== null)
  const advancing = available.filter((row) => row.changePercent! > 0).length
  const declining = available.filter((row) => row.changePercent! < 0).length
  const leader = available.reduce<MarketOverviewRow | null>((best, row) => best === null || row.changePercent! > best.changePercent! ? row : best, null)
  const laggard = available.reduce<MarketOverviewRow | null>((worst, row) => worst === null || row.changePercent! < worst.changePercent! ? row : worst, null)
  return { available: available.length, advancing, declining, unchanged: available.length - advancing - declining, leader, laggard }
}

export function universeRefreshOutcome(job: LocalUniverseJob) {
  if (job.status !== "completed") return job.status
  return job.result?.status === "partial" ? "partial" : "completed"
}

function Metric({ label, value, note, tone = "neutral" }: { label: string; value: string; note: string; tone?: "positive" | "negative" | "neutral" }) {
  return <div className="rounded-lg border bg-background/45 p-4"><span className="font-mono text-[9px] uppercase tracking-[0.14em] text-muted-foreground">{label}</span><strong className={cn("mt-2 block text-xl", tone === "positive" && "text-primary", tone === "negative" && "text-destructive")}>{value}</strong><small className="mt-1 block text-[10px] text-muted-foreground">{note}</small></div>
}

function Movement({ value }: { value: number | null }) {
  if (value === null) return <span className="text-muted-foreground">—</span>
  return <span className={value > 0 ? "text-primary" : value < 0 ? "text-destructive" : "text-muted-foreground"}>{value > 0 ? <TrendingUp className="mr-1 inline size-3" /> : value < 0 ? <TrendingDown className="mr-1 inline size-3" /> : null}{signedPercent(value)}</span>
}

function SectorHeatmap({ sectors, selected, onSelect }: { sectors: MarketOverviewRow[]; selected: string | null; onSelect: (symbol: string) => void }) {
  return <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-6">{sectors.map((sector) => <button key={sector.symbol} type="button" aria-pressed={selected === sector.symbol} onClick={() => onSelect(sector.symbol)} className={cn("rounded-lg border p-3 text-left transition-colors hover:border-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary", selected === sector.symbol && "border-primary bg-primary/10 ring-1 ring-primary/40", sector.changePercent !== null && sector.changePercent > 0 ? "bg-primary/6" : sector.changePercent !== null && sector.changePercent < 0 ? "bg-destructive/5" : "bg-background/40")}><div className="flex items-start justify-between gap-2"><div><strong className="text-sm">{sector.symbol}</strong><p className="mt-1 text-[10px] text-muted-foreground">{sector.name}</p></div><Movement value={sector.changePercent} /></div><div className="mt-3 flex items-center justify-between font-mono text-[9px]"><span className="text-muted-foreground">RS VS SPY</span><span>{signedPercent(sector.relativeStrength)}</span></div></button>)}</div>
}

function SectorTable({ sectors, onSelect }: { sectors: MarketOverviewRow[]; onSelect: (symbol: string) => void }) {
  return <Table><TableCaption>Relative strength compares each sector ETF's visible three-month return with SPY. It is not a forward forecast.</TableCaption><TableHeader><TableRow><TableHead>Sector</TableHead><TableHead>Last</TableHead><TableHead>Day</TableHead><TableHead>3M Return</TableHead><TableHead>RS vs SPY</TableHead><TableHead>Observed</TableHead><TableHead>Status</TableHead><TableHead>Research</TableHead></TableRow></TableHeader><TableBody>{sectors.map((sector) => <TableRow key={sector.symbol}><TableCell><strong>{sector.symbol}</strong><small className="ml-2 text-muted-foreground">{sector.name}</small></TableCell><TableCell>{money(sector.price)}</TableCell><TableCell><Movement value={sector.changePercent} /></TableCell><TableCell><Movement value={sector.periodReturn} /></TableCell><TableCell><Movement value={sector.relativeStrength} /></TableCell><TableCell>{observedAt(sector)}</TableCell><TableCell><Badge variant={sector.available ? "outline" : "destructive"}>{sector.dataStatus.status || "Unknown"}</Badge></TableCell><TableCell><div className="flex gap-1"><Button size="xs" variant="ghost" onClick={() => onSelect(sector.symbol)}>Constituents<ArrowRight /></Button><Button asChild size="xs" variant="ghost"><a href={labHref("strategy", sector.symbol)}>ETF Strategy<ArrowRight /></a></Button></div></TableCell></TableRow>)}</TableBody></Table>
}

function MacroTable({ rows }: { rows: MarketOverviewRow[] }) {
  return <Table><TableCaption>Cross-asset market proxies use delayed public daily observations with different market hours and publication conventions.</TableCaption><TableHeader><TableRow><TableHead>Proxy</TableHead><TableHead>Symbol</TableHead><TableHead>Last</TableHead><TableHead>Day</TableHead><TableHead>3M</TableHead><TableHead>Known At</TableHead><TableHead>Source</TableHead></TableRow></TableHeader><TableBody>{rows.map((row) => <TableRow key={row.symbol}><TableCell><strong>{row.name}</strong></TableCell><TableCell className="font-mono text-xs">{row.symbol}</TableCell><TableCell>{money(row.price)}</TableCell><TableCell><Movement value={row.changePercent} /></TableCell><TableCell><Movement value={row.periodReturn} /></TableCell><TableCell>{observedAt(row)}</TableCell><TableCell><Badge variant={row.available ? "outline" : "destructive"}>{row.dataStatus.source || "Unavailable"}</Badge></TableCell></TableRow>)}</TableBody></Table>
}

export function MarketPulse() {
  const [overview, setOverview] = useState<MarketOverviewResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [universe, setUniverse] = useState<UniverseStatusResponse | null>(null)
  const [universeJobId, setUniverseJobId] = useState<string | null>(null)
  const [universeJob, setUniverseJob] = useState<LocalUniverseJob | null>(null)
  const [universeError, setUniverseError] = useState("")
  const [selectedSector, setSelectedSector] = useState<string | null>(null)
  const [sectorData, setSectorData] = useState<SectorConstituentSnapshot | null>(null)
  const [sectorLoading, setSectorLoading] = useState(false)
  const [sectorError, setSectorError] = useState("")
  const refresh = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      setOverview(await loadMarketOverview())
    } catch (requestError) {
      const message = errorMessage(requestError)
      setError(message)
      toast.error("Market Pulse unavailable", { description: message })
    } finally {
      setLoading(false)
    }
  }, [])
  const refreshUniverseStatus = useCallback(async () => {
    try {
      setUniverse(await loadSp500UniverseStatus())
      setUniverseError("")
    } catch (requestError) {
      setUniverseError(errorMessage(requestError))
    }
  }, [])
  const refreshSector = useCallback(async (symbol: string) => {
    setSectorLoading(true)
    setSectorError("")
    try {
      setSectorData(await loadSectorConstituents(symbol))
    } catch (requestError) {
      setSectorData(null)
      setSectorError(errorMessage(requestError))
    } finally {
      setSectorLoading(false)
    }
  }, [])
  const selectSector = useCallback((symbol: string) => {
    setSelectedSector(symbol)
    if (!universe?.snapshot) {
      setSectorData(null)
      setSectorError("Download the S&P 500 research universe before opening constituent research.")
      return
    }
    void refreshSector(symbol)
  }, [refreshSector, universe?.snapshot])
  const startUniverseRefresh = useCallback(async () => {
    try {
      setUniverseError("")
      const accepted = await refreshSp500Universe()
      setUniverseJobId(accepted.jobId)
      setUniverseJob(null)
      toast.success(universe?.snapshot ? "S&P 500 refresh started" : "S&P 500 download started", { description: "The local cache continues in the background and preserves partial progress." })
    } catch (requestError) {
      const message = errorMessage(requestError)
      setUniverseError(message)
      toast.error("Universe refresh could not start", { description: message })
    }
  }, [universe?.snapshot])
  useEffect(() => { void refresh(); void refreshUniverseStatus() }, [refresh, refreshUniverseStatus])
  useEffect(() => {
    if (!universeJobId) return
    let active = true
    let timer: ReturnType<typeof setTimeout> | undefined
    const poll = async () => {
      try {
        const job = await loadUniverseJob(universeJobId)
        if (!active) return
        setUniverseJob(job)
        if (job.status === "running") {
          timer = setTimeout(() => void poll(), 900)
          return
        }
        setUniverseJobId(null)
        await refreshUniverseStatus()
        if (selectedSector) await refreshSector(selectedSector)
        const outcome = universeRefreshOutcome(job)
        if (outcome === "completed") toast.success("S&P 500 research cache updated")
        else if (outcome === "partial") toast.warning("S&P 500 cache updated with gaps", { description: "Useful records were preserved; failed or partial companies remain visible and can be retried." })
        else toast.error("S&P 500 refresh ended early", { description: job.error || `Job status: ${job.status}` })
      } catch (requestError) {
        if (!active) return
        setUniverseError(errorMessage(requestError))
        timer = setTimeout(() => void poll(), 1500)
      }
    }
    void poll()
    return () => { active = false; if (timer) clearTimeout(timer) }
  }, [refreshSector, refreshUniverseStatus, selectedSector, universeJobId])

  const breadth = useMemo(() => summarizeSectors(overview?.sectors || []), [overview?.sectors])
  const vix = overview?.macro.find((row) => row.symbol === "^VIX")
  const unavailable = [...(overview?.sectors || []), ...(overview?.macro || [])].filter((row) => !row.available)
  const generatedAt = overview?.generatedAt ? new Date(overview.generatedAt).toLocaleString() : "Waiting For Data"
  const universeRunning = Boolean(universeJobId) && (!universeJob || universeJob.status === "running")

  return <>
    <div role="region" aria-label="Market Pulse controls" className="sticky top-0 z-20 flex flex-wrap items-center gap-2 border-b bg-background/92 px-3 py-3 shadow-sm backdrop-blur sm:px-4 xl:px-6"><div className="flex items-center gap-2"><Gauge className="size-4 text-primary" /><strong className="text-sm">US Market Pulse</strong><Badge variant="outline">Public Data</Badge></div><div className="ml-0 flex w-full flex-wrap items-center justify-end gap-2 sm:ml-auto sm:w-auto"><span className="mr-auto font-mono text-[9px] text-muted-foreground sm:mr-0"><Clock3 className="mr-1 inline size-3" />Generated {generatedAt}</span><Button variant="outline" onClick={() => void startUniverseRefresh()} disabled={universeRunning}><DownloadCloud className={universeRunning ? "motion-safe:animate-pulse" : ""} />{universeRunning ? `${Math.round((universeJob?.progress || 0) * 100)}% Downloaded` : universe?.snapshot ? "Refresh S&P 500" : "Download S&P 500"}</Button>{universeRunning && universeJobId ? <Button size="icon-sm" variant="ghost" aria-label="Cancel S&P 500 refresh" onClick={() => void cancelUniverseJob(universeJobId)}><XCircle /></Button> : null}<Button onClick={() => void refresh()} disabled={loading}><RefreshCw className={loading ? "motion-safe:animate-spin" : ""} />{loading ? "Refreshing…" : "Refresh Market"}</Button></div>{universeRunning ? <div className="h-1 w-full overflow-hidden rounded bg-muted"><div className="h-full bg-primary transition-[width]" style={{ width: `${Math.max((universeJob?.progress || 0) * 100, 1)}%` }} /></div> : null}</div>
    <div className="space-y-5 p-3 sm:p-4 xl:p-6"><div className="flex flex-wrap items-end justify-between gap-3 px-1"><div><div className="mb-2 flex items-center gap-2"><Badge variant="outline" className="border-primary/30 text-primary">Market Pulse</Badge><Badge variant="secondary">Sector · Relative · Macro</Badge></div><h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Start with the market regime, then choose a symbol.</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">Sector breadth, SPY-relative strength, cross-asset proxies, source health, and observation timing remain visible before deeper research.</p></div><div className="font-mono text-[10px] text-muted-foreground"><Database className="mr-1 inline size-3" />DuckDB cache · stale fallback enabled</div></div>
      {error && <Alert variant="destructive"><AlertCircle /><AlertTitle>Market Overview Unavailable</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
      {universeError && <Alert variant="destructive"><AlertCircle /><AlertTitle>Research Universe Unavailable</AlertTitle><AlertDescription>{universeError}</AlertDescription></Alert>}
      {universe?.snapshot ? <Alert><Database /><AlertTitle>S&amp;P 500 Research Universe</AlertTitle><AlertDescription>Snapshot {universe.snapshot.version} from {universe.snapshot.source}, observed {new Date(universe.snapshot.knownAt).toLocaleString()}. {universe.cachedCount} of {universe.snapshot.constituentCount} companies are cached; {universe.partialCount} partial and {universe.failedCount} failed records remain explicit.</AlertDescription></Alert> : null}
      {unavailable.length ? <Alert><AlertCircle /><AlertTitle>Partial Public Data</AlertTitle><AlertDescription>{unavailable.map((row) => row.symbol).join(", ")} could not be refreshed. Available rows remain visible and failed rows retain their warnings.</AlertDescription></Alert> : null}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5"><Metric label="SPY" value={money(overview?.benchmark.price ?? null)} note={`${signedPercent(overview?.benchmark.changePercent ?? null)} day · ${signedPercent(overview?.benchmark.periodReturn ?? null)} 3M`} tone={(overview?.benchmark.changePercent ?? 0) > 0 ? "positive" : (overview?.benchmark.changePercent ?? 0) < 0 ? "negative" : "neutral"} /><Metric label="Sector Breadth" value={`${breadth.advancing} Up · ${breadth.declining} Down`} note={`${breadth.available} of ${overview?.sectors.length || 0} sectors available`} tone={breadth.advancing > breadth.declining ? "positive" : breadth.declining > breadth.advancing ? "negative" : "neutral"} /><Metric label="Leading Sector" value={breadth.leader?.symbol || "—"} note={breadth.leader ? `${breadth.leader.name} · ${signedPercent(breadth.leader.changePercent)}` : "Waiting for available rows"} tone="positive" /><Metric label="Lagging Sector" value={breadth.laggard?.symbol || "—"} note={breadth.laggard ? `${breadth.laggard.name} · ${signedPercent(breadth.laggard.changePercent)}` : "Waiting for available rows"} tone="negative" /><Metric label="VIX Proxy" value={money(vix?.price ?? null)} note={`${signedPercent(vix?.changePercent ?? null)} latest daily move`} tone={(vix?.changePercent ?? 0) > 0 ? "negative" : "neutral"} /></div>
      <Card className="gap-4"><CardHeader><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="mb-2 flex items-center gap-2"><Gauge className="size-4 text-primary" /><span className="font-mono text-[9px] uppercase tracking-[0.14em] text-primary">Sector Map</span></div><CardTitle>Where is participation strongest?</CardTitle><CardDescription className="mt-2">Cards show latest session movement and trailing three-month return relative to SPY. Select one to expand its current S&amp;P 500 constituents without leaving Market Pulse.</CardDescription></div><Badge variant="outline">{breadth.available} Available</Badge></div></CardHeader><CardContent className="border-t pt-5"><SectorHeatmap sectors={overview?.sectors || []} selected={selectedSector} onSelect={selectSector} /></CardContent></Card>
      <SectorConstituents data={sectorData} loading={sectorLoading} error={sectorError} onRetry={() => selectedSector && void refreshSector(selectedSector)} />
      <Card className="gap-0 overflow-hidden"><CardHeader className="border-b"><CardTitle>Sector Performance Evidence</CardTitle><CardDescription>Ranked by latest daily move; relative strength remains a separate three-month measure.</CardDescription></CardHeader><CardContent className="px-0"><SectorTable sectors={overview?.sectors || []} onSelect={selectSector} /></CardContent></Card>
      <div className="grid gap-5 2xl:grid-cols-[1.5fr_1fr]"><Card className="gap-0 overflow-hidden"><CardHeader className="border-b"><div className="flex items-center gap-2"><TrendingUp className="size-4 text-primary" /><CardTitle>Cross-Asset Macro Proxies</CardTitle></div><CardDescription>Equities, volatility, dollar, gold, oil, and the 10-year-yield proxy do not share identical market hours.</CardDescription></CardHeader><CardContent className="px-0"><MacroTable rows={overview?.macro || []} /></CardContent></Card><Card className="gap-4"><CardHeader><div className="flex items-center gap-2"><Server className="size-4 text-primary" /><CardTitle>Provider Readiness</CardTitle></div><CardDescription>Configured means the local adapter is available, not that every upstream request will succeed.</CardDescription></CardHeader><CardContent className="space-y-2 border-t pt-5">{overview?.providers.map((provider) => <div key={provider.provider} className="flex items-center justify-between gap-3 rounded-lg border bg-background/40 p-3"><div><strong className="text-sm">{provider.provider}</strong><p className="mt-1 text-[10px] text-muted-foreground">Free public-data adapter</p></div><Badge variant={provider.configured ? "outline" : "destructive"}><ShieldCheck />{provider.status}</Badge></div>) || <div className="grid h-48 place-items-center text-sm text-muted-foreground">Provider status loads with the market overview.</div>}</CardContent></Card></div>
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-dashed px-4 py-3 text-xs text-muted-foreground"><span>Observation dates and public-data status remain visible; stale rows are not silently presented as current.</span><span>No investment recommendation or brokerage execution.</span></div>
    </div>
  </>
}
