import { useCallback, useEffect, useMemo, useState } from "react"
import { AlertCircle, ArrowRight, BarChart3, Database, FlaskConical, Orbit, RefreshCw, Search, Star, StarOff, Waypoints } from "lucide-react"
import { toast } from "sonner"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { MarketWorkspaceChart } from "@/features/strategy-lab/market-workspace-chart"
import { ApiError, loadOptionChain, loadStockOverview } from "@/lib/api"
import { labHref, normalizeTicker } from "@/lib/navigation"
import type { DataStatus, OptionChainContract, OptionChainResponse, StockOverviewResponse } from "@/lib/types"
import { cn } from "@/lib/utils"
import { readWatchlist, writeWatchlist } from "@/lib/watchlist"

type StockPeriod = "1mo" | "3mo" | "6mo" | "1y" | "2y"

const periodLabels: Record<StockPeriod, string> = {
  "1mo": "1 Month",
  "3mo": "3 Months",
  "6mo": "6 Months",
  "1y": "1 Year",
  "2y": "2 Years",
}

function errorMessage(error: unknown) {
  if (error instanceof ApiError || error instanceof Error) return error.message
  return "The stock-observability request failed unexpectedly."
}

function money(value: number) {
  return value.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 })
}

function compactNumber(value: number) {
  return Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(value)
}

function dateTime(value?: string) {
  if (!value) return "Not Reported"
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString()
}

function Metric({ label, value, note, negative = false }: { label: string; value: string; note: string; negative?: boolean }) {
  return <div className="rounded-lg border bg-background/45 p-4"><span className="font-mono text-[9px] uppercase tracking-[0.14em] text-muted-foreground">{label}</span><strong className={cn("mt-2 block text-xl", negative ? "text-destructive" : "")}>{value}</strong><small className="mt-1 block text-[10px] text-muted-foreground">{note}</small></div>
}

function Provenance({ status }: { status?: DataStatus }) {
  return <Card className="gap-4 py-5"><CardHeader className="px-4 sm:px-6"><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="mb-2 flex items-center gap-2"><Database className="size-4 text-primary" /><span className="font-mono text-[9px] uppercase tracking-[0.14em] text-primary">Data Provenance</span></div><CardTitle className="text-base">Know what the chart knew.</CardTitle><CardDescription className="mt-2">Public observations can be delayed, cached, or revised. Publication and retrieval context stays visible.</CardDescription></div><Badge variant="outline">{status?.status || "Unknown Status"}</Badge></div></CardHeader><CardContent className="grid gap-3 border-t px-4 pt-4 text-xs sm:grid-cols-2 sm:px-6 xl:grid-cols-4"><div><span className="text-muted-foreground">Source</span><strong className="mt-1 block">{status?.source || "Yahoo Finance"}</strong></div><div><span className="text-muted-foreground">Observation</span><strong className="mt-1 block">{dateTime(status?.observationTimestamp)}</strong></div><div><span className="text-muted-foreground">Known At</span><strong className="mt-1 block">{dateTime(status?.knownAt)}</strong></div><div><span className="text-muted-foreground">Retrieved</span><strong className="mt-1 block">{dateTime(status?.retrievedAt)}</strong></div>{status?.qualityWarnings?.length ? <div className="sm:col-span-2 xl:col-span-4"><span className="text-muted-foreground">Quality Notes</span><ul className="mt-1 space-y-1">{status.qualityWarnings.map((warning) => <li key={warning}>• {warning}</li>)}</ul></div> : null}</CardContent></Card>
}

function OptionContracts({ contracts }: { contracts: OptionChainContract[] }) {
  return <ScrollArea className="h-[480px]"><Table><TableCaption>Current public quotes only. Bid/ask depth and executable size are not guaranteed.</TableCaption><TableHeader><TableRow><TableHead>Contract</TableHead><TableHead>Strike</TableHead><TableHead>Last</TableHead><TableHead>Bid / Ask</TableHead><TableHead>Spread</TableHead><TableHead>Volume</TableHead><TableHead>Open Interest</TableHead><TableHead>IV</TableHead></TableRow></TableHeader><TableBody>{contracts.map((contract) => <TableRow key={contract.contract}><TableCell className="font-mono text-[10px]"><span className={contract.inTheMoney ? "text-primary" : ""}>{contract.contract}</span><small className="mt-1 block text-[8px] text-muted-foreground">{contract.quoteQuality || "Cached Quote"}</small></TableCell><TableCell>{money(contract.strike)}</TableCell><TableCell>{money(contract.last)}</TableCell><TableCell>{money(contract.bid)} / {money(contract.ask)}</TableCell><TableCell>{money(contract.spread ?? Math.max(contract.ask - contract.bid, 0))}</TableCell><TableCell>{contract.volume.toLocaleString()}</TableCell><TableCell>{contract.openInterest.toLocaleString()}</TableCell><TableCell>{contract.iv.toFixed(2)}%</TableCell></TableRow>)}</TableBody></Table></ScrollArea>
}

function OptionContext({ ticker, chain, loading, error, onLoad }: { ticker: string; chain: OptionChainResponse | null; loading: boolean; error: string; onLoad: (expiration?: string) => void }) {
  return <Card className="gap-4"><CardHeader><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="mb-2 flex items-center gap-2"><Waypoints className="size-4 text-primary" /><span className="font-mono text-[9px] uppercase tracking-[0.14em] text-primary">Current Option Context</span></div><CardTitle>Inspect expiry, liquidity, and quote width.</CardTitle><CardDescription className="mt-2">This is a current-chain snapshot, not a historical option backtest. Use Option Lab to construct and journal a paper position.</CardDescription></div><Button asChild variant="outline"><a href={labHref("options", ticker)}><Orbit />Open In Option Lab<ArrowRight /></a></Button></div></CardHeader><CardContent className="space-y-4 border-t pt-5">{chain?.expirations.length ? <div className="flex gap-2 overflow-x-auto pb-2">{chain.expirations.map((expiration) => <button type="button" key={expiration} disabled={loading} aria-pressed={expiration === chain.expiration} className={cn("shrink-0 rounded-lg border px-3 py-2 text-left transition-colors hover:border-primary/50", expiration === chain.expiration && "border-primary bg-primary/10")} onClick={() => onLoad(expiration)}><strong className="block text-xs">{expiration}</strong><small className="font-mono text-[9px] text-muted-foreground">Select Expiry</small></button>)}</div> : null}{loading ? <div className="grid h-56 place-items-center text-sm text-muted-foreground"><RefreshCw className="mr-2 inline size-4 motion-safe:animate-spin" />Loading current contracts…</div> : error ? <Alert variant="destructive"><AlertCircle /><AlertTitle>Option Context Unavailable</AlertTitle><AlertDescription>{error} Stock research remains available.</AlertDescription></Alert> : chain?.expiration ? <><div className="flex flex-wrap items-center gap-2"><Badge variant="outline">{ticker} · {chain.expiration}</Badge><Badge variant="secondary">{chain.dataStatus?.status || "Delayed"}</Badge><span className="text-[10px] text-muted-foreground">{chain.calls.length} calls · {chain.puts.length} puts</span></div><Tabs defaultValue="calls"><TabsList><TabsTrigger value="calls">Calls</TabsTrigger><TabsTrigger value="puts">Puts</TabsTrigger></TabsList><TabsContent value="calls"><OptionContracts contracts={chain.calls} /></TabsContent><TabsContent value="puts"><OptionContracts contracts={chain.puts} /></TabsContent></Tabs></> : <div className="grid h-56 place-items-center text-center text-sm text-muted-foreground"><div><p>No current contracts are loaded.</p><Button className="mt-3" variant="outline" onClick={() => onLoad()}>Load Option Context</Button></div></div>}</CardContent></Card>
}

export function StockObservatory({ initialTicker = "NVDA" }: { initialTicker?: string }) {
  const normalizedInitialTicker = normalizeTicker(initialTicker)
  const [tickerInput, setTickerInput] = useState(normalizedInitialTicker)
  const [ticker, setTicker] = useState(normalizedInitialTicker)
  const [period, setPeriod] = useState<StockPeriod>("1y")
  const [overview, setOverview] = useState<StockOverviewResponse | null>(null)
  const [chain, setChain] = useState<OptionChainResponse | null>(null)
  const [stockLoading, setStockLoading] = useState(false)
  const [chainLoading, setChainLoading] = useState(false)
  const [stockError, setStockError] = useState("")
  const [chainError, setChainError] = useState("")
  const [watchlist, setWatchlist] = useState<string[]>(() => readWatchlist())

  const loadStock = useCallback(async (symbol: string, selectedPeriod: StockPeriod) => {
    setStockLoading(true)
    setStockError("")
    try {
      const result = await loadStockOverview(symbol, selectedPeriod)
      setOverview(result)
    } catch (error) {
      const message = errorMessage(error)
      setStockError(message)
      toast.error("Stock overview unavailable", { description: message })
    } finally {
      setStockLoading(false)
    }
  }, [])

  const loadChain = useCallback(async (symbol: string, expiration?: string) => {
    setChainLoading(true)
    setChainError("")
    try {
      setChain(await loadOptionChain(symbol, expiration))
    } catch (error) {
      setChainError(errorMessage(error))
    } finally {
      setChainLoading(false)
    }
  }, [])

  const loadSymbol = useCallback(async (symbol: string, selectedPeriod: StockPeriod) => {
    const normalized = normalizeTicker(symbol, "")
    if (!normalized) {
      toast.error("Enter a supported US market symbol.")
      return
    }
    setTicker(normalized)
    setTickerInput(normalized)
    setChain(null)
    await Promise.all([loadStock(normalized, selectedPeriod), loadChain(normalized)])
  }, [loadChain, loadStock])

  useEffect(() => { void loadSymbol(normalizedInitialTicker, "1y") }, [loadSymbol, normalizedInitialTicker])

  const dailyPoints = overview?.marketChart.intervals.day || []
  const range = useMemo(() => dailyPoints.length ? { low: Math.min(...dailyPoints.map((point) => point.low)), high: Math.max(...dailyPoints.map((point) => point.high)), averageVolume: dailyPoints.reduce((total, point) => total + point.volume, 0) / dailyPoints.length } : null, [dailyPoints])
  const quote = overview?.quote
  const submitTicker = (event: React.FormEvent) => {
    event.preventDefault()
    void loadSymbol(tickerInput, period)
  }
  const toggleWatchlist = () => {
    const next = watchlist.includes(ticker) ? watchlist.filter((symbol) => symbol !== ticker) : [...watchlist, ticker]
    setWatchlist(next)
    writeWatchlist(next)
  }

  return <>
    <div role="region" aria-label="Stock Observatory controls" className="sticky top-0 z-20 flex flex-wrap items-center gap-2 border-b bg-background/92 px-3 py-3 shadow-sm backdrop-blur sm:px-4 xl:px-6"><form className="flex items-center gap-2" onSubmit={submitTicker}><Input aria-label="Stock Observatory ticker" className="w-28 font-mono font-semibold uppercase" value={tickerInput} maxLength={12} onChange={(event) => setTickerInput(event.target.value.toUpperCase())} /><Button type="submit" variant="outline" disabled={stockLoading}><Search />Load</Button></form><Select value={period} onValueChange={(value: StockPeriod) => { setPeriod(value); void loadStock(ticker, value) }}><SelectTrigger aria-label="Stock history window" className="w-36"><SelectValue /></SelectTrigger><SelectContent>{Object.entries(periodLabels).map(([value, label]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}</SelectContent></Select><div className="ml-0 flex w-full flex-wrap gap-2 sm:ml-auto sm:w-auto"><Button asChild variant="outline"><a href={labHref("strategy", ticker)}><FlaskConical />Test A Strategy</a></Button><Button asChild variant="outline"><a href={labHref("options", ticker)}><Orbit />Build An Option Position</a></Button><Button onClick={() => void loadSymbol(ticker, period)} disabled={stockLoading || chainLoading}><RefreshCw className={stockLoading || chainLoading ? "motion-safe:animate-spin" : ""} />Refresh</Button></div></div>
    <div className="space-y-5 p-3 sm:p-4 xl:p-6"><div className="flex flex-wrap items-end justify-between gap-3 px-1"><div><div className="mb-2 flex items-center gap-2"><Badge variant="outline" className="border-primary/30 text-primary">Stock Observatory</Badge><Badge variant="secondary">{periodLabels[period]}</Badge></div><h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Read {ticker} before choosing the next laboratory.</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">Price action, volume, momentum, technical context, and current option liquidity share one evidence surface.</p></div><div className="font-mono text-[10px] text-muted-foreground"><Database className="mr-1 inline size-3" />{quote?.dataStatus.source || "Yahoo Finance"} · {quote?.dataStatus.status || "Loading"}</div></div>
      {stockError && <Alert variant="destructive"><AlertCircle /><AlertTitle>Stock Data Unavailable</AlertTitle><AlertDescription>{stockError}</AlertDescription></Alert>}
      <Card className="gap-3 py-4"><CardContent className="flex flex-wrap items-center gap-2 px-4 sm:px-5"><div className="mr-2 min-w-44 flex-1"><strong className="text-sm">Local Watchlist</strong><p className="mt-1 text-[10px] text-muted-foreground">Browser-local navigation only; no account or cloud sync.</p></div>{watchlist.map((symbol) => <Button key={symbol} size="sm" variant={symbol === ticker ? "secondary" : "outline"} aria-pressed={symbol === ticker} onClick={() => void loadSymbol(symbol, period)}>{symbol}</Button>)}<Button size="sm" variant="ghost" onClick={toggleWatchlist}>{watchlist.includes(ticker) ? <StarOff /> : <Star />}{watchlist.includes(ticker) ? `Remove ${ticker}` : `Add ${ticker}`}</Button></CardContent></Card>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5"><Metric label="Last Price" value={quote ? money(quote.price) : "—"} note="Adjusted daily close" /><Metric label="Day Change" value={quote ? `${quote.change >= 0 ? "+" : ""}${money(quote.change)} · ${quote.changePercent >= 0 ? "+" : ""}${quote.changePercent.toFixed(2)}%` : "—"} note="Previous session close" negative={Boolean(quote && quote.change < 0)} /><Metric label={`${periodLabels[period]} Return`} value={quote ? `${quote.periodReturn >= 0 ? "+" : ""}${quote.periodReturn.toFixed(2)}%` : "—"} note="Price return, no dividends" negative={Boolean(quote && quote.periodReturn < 0)} /><Metric label="Observed Range" value={range ? `${money(range.low)} – ${money(range.high)}` : "—"} note="Visible daily high and low" /><Metric label="Average Volume" value={range ? compactNumber(range.averageVolume) : "—"} note="Visible daily sessions" /></div>
      <Card className="gap-0 overflow-hidden py-0"><CardHeader className="border-b py-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><div className="mb-2 flex items-center gap-2"><BarChart3 className="size-4 text-primary" /><span className="font-mono text-[9px] uppercase tracking-[0.14em] text-primary">OHLCV · Technical Context</span></div><CardTitle>{ticker} Market Replay</CardTitle><CardDescription className="mt-2">Switch day/week/month/year bars and independently inspect SMA, EMA, Bollinger, Darvas, and deterministic Fibonacci overlays.</CardDescription></div><Badge variant="outline">Candles · Volume · RSI · MACD</Badge></div></CardHeader><MarketWorkspaceChart points={[]} marketChart={overview?.marketChart || null} loading={stockLoading} symbol={ticker} showRuleOverlay={false} /></Card>
      <OptionContext ticker={ticker} chain={chain} loading={chainLoading} error={chainError} onLoad={(expiration) => void loadChain(ticker, expiration)} />
      <Provenance status={quote?.dataStatus} />
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-dashed px-4 py-3 text-xs text-muted-foreground"><span>US equity and current-option research only. Public data may be delayed or revised.</span><span>No brokerage execution.</span></div>
    </div>
  </>
}
