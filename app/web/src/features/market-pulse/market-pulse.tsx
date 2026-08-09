import { useCallback, useEffect, useMemo, useState } from "react"
import { AlertCircle, ArrowRight, Clock3, Database, Gauge, LineChart, RefreshCw, Server, ShieldCheck, TrendingDown, TrendingUp } from "lucide-react"
import { toast } from "sonner"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { ApiError, loadMarketOverview } from "@/lib/api"
import { labHref } from "@/lib/navigation"
import type { MarketOverviewResponse, MarketOverviewRow } from "@/lib/types"
import { cn } from "@/lib/utils"

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

function Metric({ label, value, note, tone = "neutral" }: { label: string; value: string; note: string; tone?: "positive" | "negative" | "neutral" }) {
  return <div className="rounded-lg border bg-background/45 p-4"><span className="font-mono text-[9px] uppercase tracking-[0.14em] text-muted-foreground">{label}</span><strong className={cn("mt-2 block text-xl", tone === "positive" && "text-primary", tone === "negative" && "text-destructive")}>{value}</strong><small className="mt-1 block text-[10px] text-muted-foreground">{note}</small></div>
}

function Movement({ value }: { value: number | null }) {
  if (value === null) return <span className="text-muted-foreground">—</span>
  return <span className={value > 0 ? "text-primary" : value < 0 ? "text-destructive" : "text-muted-foreground"}>{value > 0 ? <TrendingUp className="mr-1 inline size-3" /> : value < 0 ? <TrendingDown className="mr-1 inline size-3" /> : null}{signedPercent(value)}</span>
}

function SectorHeatmap({ sectors }: { sectors: MarketOverviewRow[] }) {
  return <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-6">{sectors.map((sector) => <a key={sector.symbol} href={labHref("stock", sector.symbol)} className={cn("rounded-lg border p-3 transition-colors hover:border-primary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary", sector.changePercent !== null && sector.changePercent > 0 ? "bg-primary/6" : sector.changePercent !== null && sector.changePercent < 0 ? "bg-destructive/5" : "bg-background/40")}><div className="flex items-start justify-between gap-2"><div><strong className="text-sm">{sector.symbol}</strong><p className="mt-1 text-[10px] text-muted-foreground">{sector.name}</p></div><Movement value={sector.changePercent} /></div><div className="mt-3 flex items-center justify-between font-mono text-[9px]"><span className="text-muted-foreground">RS VS SPY</span><span>{signedPercent(sector.relativeStrength)}</span></div></a>)}</div>
}

function SectorTable({ sectors }: { sectors: MarketOverviewRow[] }) {
  return <Table><TableCaption>Relative strength compares each sector ETF's visible three-month return with SPY. It is not a forward forecast.</TableCaption><TableHeader><TableRow><TableHead>Sector</TableHead><TableHead>Last</TableHead><TableHead>Day</TableHead><TableHead>3M Return</TableHead><TableHead>RS vs SPY</TableHead><TableHead>Observed</TableHead><TableHead>Status</TableHead><TableHead>Research</TableHead></TableRow></TableHeader><TableBody>{sectors.map((sector) => <TableRow key={sector.symbol}><TableCell><strong>{sector.symbol}</strong><small className="ml-2 text-muted-foreground">{sector.name}</small></TableCell><TableCell>{money(sector.price)}</TableCell><TableCell><Movement value={sector.changePercent} /></TableCell><TableCell><Movement value={sector.periodReturn} /></TableCell><TableCell><Movement value={sector.relativeStrength} /></TableCell><TableCell>{observedAt(sector)}</TableCell><TableCell><Badge variant={sector.available ? "outline" : "destructive"}>{sector.dataStatus.status || "Unknown"}</Badge></TableCell><TableCell><div className="flex gap-1"><Button asChild size="xs" variant="ghost"><a href={labHref("stock", sector.symbol)}><LineChart />Stock</a></Button><Button asChild size="xs" variant="ghost"><a href={labHref("strategy", sector.symbol)}>Strategy<ArrowRight /></a></Button></div></TableCell></TableRow>)}</TableBody></Table>
}

function MacroTable({ rows }: { rows: MarketOverviewRow[] }) {
  return <Table><TableCaption>Cross-asset market proxies use delayed public daily observations with different market hours and publication conventions.</TableCaption><TableHeader><TableRow><TableHead>Proxy</TableHead><TableHead>Symbol</TableHead><TableHead>Last</TableHead><TableHead>Day</TableHead><TableHead>3M</TableHead><TableHead>Known At</TableHead><TableHead>Source</TableHead></TableRow></TableHeader><TableBody>{rows.map((row) => <TableRow key={row.symbol}><TableCell><strong>{row.name}</strong></TableCell><TableCell className="font-mono text-xs">{row.symbol}</TableCell><TableCell>{money(row.price)}</TableCell><TableCell><Movement value={row.changePercent} /></TableCell><TableCell><Movement value={row.periodReturn} /></TableCell><TableCell>{observedAt(row)}</TableCell><TableCell><Badge variant={row.available ? "outline" : "destructive"}>{row.dataStatus.source || "Unavailable"}</Badge></TableCell></TableRow>)}</TableBody></Table>
}

export function MarketPulse() {
  const [overview, setOverview] = useState<MarketOverviewResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
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
  useEffect(() => { void refresh() }, [refresh])

  const breadth = useMemo(() => summarizeSectors(overview?.sectors || []), [overview?.sectors])
  const vix = overview?.macro.find((row) => row.symbol === "^VIX")
  const unavailable = [...(overview?.sectors || []), ...(overview?.macro || [])].filter((row) => !row.available)
  const generatedAt = overview?.generatedAt ? new Date(overview.generatedAt).toLocaleString() : "Waiting For Data"

  return <>
    <div role="region" aria-label="Market Pulse controls" className="sticky top-0 z-20 flex flex-wrap items-center gap-2 border-b bg-background/92 px-3 py-3 shadow-sm backdrop-blur sm:px-4 xl:px-6"><div className="flex items-center gap-2"><Gauge className="size-4 text-primary" /><strong className="text-sm">US Market Pulse</strong><Badge variant="outline">Public Data</Badge></div><div className="ml-0 flex w-full items-center justify-between gap-2 sm:ml-auto sm:w-auto"><span className="font-mono text-[9px] text-muted-foreground"><Clock3 className="mr-1 inline size-3" />Generated {generatedAt}</span><Button onClick={() => void refresh()} disabled={loading}><RefreshCw className={loading ? "motion-safe:animate-spin" : ""} />{loading ? "Refreshing…" : "Refresh Data"}</Button></div></div>
    <div className="space-y-5 p-3 sm:p-4 xl:p-6"><div className="flex flex-wrap items-end justify-between gap-3 px-1"><div><div className="mb-2 flex items-center gap-2"><Badge variant="outline" className="border-primary/30 text-primary">Market Pulse</Badge><Badge variant="secondary">Sector · Relative · Macro</Badge></div><h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Start with the market regime, then choose a symbol.</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">Sector breadth, SPY-relative strength, cross-asset proxies, source health, and observation timing remain visible before deeper research.</p></div><div className="font-mono text-[10px] text-muted-foreground"><Database className="mr-1 inline size-3" />DuckDB cache · stale fallback enabled</div></div>
      {error && <Alert variant="destructive"><AlertCircle /><AlertTitle>Market Overview Unavailable</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>}
      {unavailable.length ? <Alert><AlertCircle /><AlertTitle>Partial Public Data</AlertTitle><AlertDescription>{unavailable.map((row) => row.symbol).join(", ")} could not be refreshed. Available rows remain visible and failed rows retain their warnings.</AlertDescription></Alert> : null}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5"><Metric label="SPY" value={money(overview?.benchmark.price ?? null)} note={`${signedPercent(overview?.benchmark.changePercent ?? null)} day · ${signedPercent(overview?.benchmark.periodReturn ?? null)} 3M`} tone={(overview?.benchmark.changePercent ?? 0) > 0 ? "positive" : (overview?.benchmark.changePercent ?? 0) < 0 ? "negative" : "neutral"} /><Metric label="Sector Breadth" value={`${breadth.advancing} Up · ${breadth.declining} Down`} note={`${breadth.available} of ${overview?.sectors.length || 0} sectors available`} tone={breadth.advancing > breadth.declining ? "positive" : breadth.declining > breadth.advancing ? "negative" : "neutral"} /><Metric label="Leading Sector" value={breadth.leader?.symbol || "—"} note={breadth.leader ? `${breadth.leader.name} · ${signedPercent(breadth.leader.changePercent)}` : "Waiting for available rows"} tone="positive" /><Metric label="Lagging Sector" value={breadth.laggard?.symbol || "—"} note={breadth.laggard ? `${breadth.laggard.name} · ${signedPercent(breadth.laggard.changePercent)}` : "Waiting for available rows"} tone="negative" /><Metric label="VIX Proxy" value={money(vix?.price ?? null)} note={`${signedPercent(vix?.changePercent ?? null)} latest daily move`} tone={(vix?.changePercent ?? 0) > 0 ? "negative" : "neutral"} /></div>
      <Card className="gap-4"><CardHeader><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="mb-2 flex items-center gap-2"><Gauge className="size-4 text-primary" /><span className="font-mono text-[9px] uppercase tracking-[0.14em] text-primary">Sector Map</span></div><CardTitle>Where is participation strongest?</CardTitle><CardDescription className="mt-2">Cards show latest session movement and trailing three-month return relative to SPY. Select one to open Stock Observatory.</CardDescription></div><Badge variant="outline">{breadth.available} Available</Badge></div></CardHeader><CardContent className="border-t pt-5"><SectorHeatmap sectors={overview?.sectors || []} /></CardContent></Card>
      <Card className="gap-0 overflow-hidden"><CardHeader className="border-b"><CardTitle>Sector Performance Evidence</CardTitle><CardDescription>Ranked by latest daily move; relative strength remains a separate three-month measure.</CardDescription></CardHeader><CardContent className="px-0"><SectorTable sectors={overview?.sectors || []} /></CardContent></Card>
      <div className="grid gap-5 2xl:grid-cols-[1.5fr_1fr]"><Card className="gap-0 overflow-hidden"><CardHeader className="border-b"><div className="flex items-center gap-2"><TrendingUp className="size-4 text-primary" /><CardTitle>Cross-Asset Macro Proxies</CardTitle></div><CardDescription>Equities, volatility, dollar, gold, oil, and the 10-year-yield proxy do not share identical market hours.</CardDescription></CardHeader><CardContent className="px-0"><MacroTable rows={overview?.macro || []} /></CardContent></Card><Card className="gap-4"><CardHeader><div className="flex items-center gap-2"><Server className="size-4 text-primary" /><CardTitle>Provider Readiness</CardTitle></div><CardDescription>Configured means the local adapter is available, not that every upstream request will succeed.</CardDescription></CardHeader><CardContent className="space-y-2 border-t pt-5">{overview?.providers.map((provider) => <div key={provider.provider} className="flex items-center justify-between gap-3 rounded-lg border bg-background/40 p-3"><div><strong className="text-sm">{provider.provider}</strong><p className="mt-1 text-[10px] text-muted-foreground">Free public-data adapter</p></div><Badge variant={provider.configured ? "outline" : "destructive"}><ShieldCheck />{provider.status}</Badge></div>) || <div className="grid h-48 place-items-center text-sm text-muted-foreground">Provider status loads with the market overview.</div>}</CardContent></Card></div>
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-dashed px-4 py-3 text-xs text-muted-foreground"><span>Observation dates and public-data status remain visible; stale rows are not silently presented as current.</span><span>No investment recommendation or brokerage execution.</span></div>
    </div>
  </>
}
